-- ════════════════════════════════════════════════════════════════════════════
-- PONTE DE AVISOS LEADFRAME — leitura dedicada no Supabase do DeskcommCRM
-- ════════════════════════════════════════════════════════════════════════════
--
-- O que este arquivo cria (e só isso):
--   · schema   leadframe_ponte                      — separado do Deskcomm
--   · tabela   leadframe_ponte.orgs_permitidas      — quais organizações a ponte lê
--   · função   leadframe_ponte.passagens_para_avisar — porta de leitura 1 (pedido de humano)
--   · função   leadframe_ponte.reunioes_para_avisar  — porta de leitura 2 (reunião marcada pela IA)
--   · papel    leadframe_ponte_leitor               — login da ponte; só executa as duas funções
--   · a liberação da organização da Leadframe (já com o id dela, no fim)
--
-- O que ele NÃO faz: não cria trigger, não altera tabela do Deskcomm, não dá
-- SELECT em tabela nenhuma. Se a ponte cair, o Deskcomm não percebe.
--
-- Por que funções e não um GRANT SELECT: cada uma devolve só os campos do
-- aviso, só da organização liberada e só das últimas 24 horas. Quem tiver a
-- senha da ponte não lê contatos, mensagens, negócios nem nada além disso.
--
-- Nome do cliente: `contacts.name` só é preenchido quando uma pessoa confirma a
-- ficha (a IA propõe, não grava). Sem ele, vale o nome do perfil do WhatsApp
-- (`display_name`) — senão quase todo aviso chegaria "Sem nome cadastrado".
--
-- Como rodar: Supabase › SQL Editor (como `postgres`), colar e executar.
-- Idempotente: pode rodar de novo sem duplicar nada.
-- Depois, UM passo à mão: definir a senha da ponte, com a linha que o
-- `scripts/configurar-segredos.sh` imprime na VPS. A senha NUNCA vai para este
-- arquivo nem para o chat.
--
-- Desfazer tudo: sql/99-desfazer.sql
-- Conferido contra o schema do DeskcommCRM v1.73.0 (passagens_de_atendimento,
-- calendar_appointments, contacts.name, contacts.display_name, contacts.phone_number).
-- ════════════════════════════════════════════════════════════════════════════

create schema if not exists leadframe_ponte;
revoke all on schema leadframe_ponte from public;

create table if not exists leadframe_ponte.orgs_permitidas (
  organization_id uuid primary key references public.organizations(id) on delete cascade,
  criado_em       timestamptz not null default now()
);
revoke all on table leadframe_ponte.orgs_permitidas from public;

create or replace function leadframe_ponte.passagens_para_avisar(
  p_org    uuid,
  p_desde  timestamptz,
  p_limite int default 50
)
returns table (
  passagem_id      uuid,
  conversation_id  uuid,
  criado_em        timestamptz,
  origem           text,
  motivo_codigo    text,
  o_que_quer       text,
  resumo           text,
  ultimas_palavras text,
  reconhecido_em   timestamptz,
  contato_nome     text,
  contato_telefone text
)
language sql
stable
security definer
set search_path = ''
as $$
  select p.id,
         p.conversation_id,
         p.criado_em,
         p.origem,
         p.motivo_codigo,
         p.title,
         p.body,
         p.notes,
         p.reconhecido_em,
         coalesce(nullif(btrim(c.name), ''), c.display_name),
         c.phone_number
    from public.passagens_de_atendimento p
    join public.contacts c
      on c.id = p.contact_id
     and c.organization_id = p.organization_id
   where p.organization_id = p_org
     and exists (select 1 from leadframe_ponte.orgs_permitidas o where o.organization_id = p_org)
     and p.criado_em >= greatest(p_desde, now() - interval '1 day')
   order by p.criado_em asc
   limit least(greatest(coalesce(p_limite, 50), 1), 200)
$$;

-- Só reunião que a IA marcou (`created_by_kind = 'ai'`): a que o Bruno marca
-- ele mesmo não precisa de aviso. Remarcação mantém `created_at` e não gera
-- aviso novo — o Google Agenda do Bruno já mostra o horário novo.
create or replace function leadframe_ponte.reunioes_para_avisar(
  p_org    uuid,
  p_desde  timestamptz,
  p_limite int default 50
)
returns table (
  reuniao_id       uuid,
  conversation_id  uuid,
  criado_em        timestamptz,
  inicia_em        timestamptz,
  fuso             text,
  titulo           text,
  notas            text,
  situacao         text,
  contato_nome     text,
  contato_telefone text
)
language sql
stable
security definer
set search_path = ''
as $$
  select a.id,
         a.conversation_id,
         a.created_at,
         a.starts_at,
         a.time_zone,
         a.title,
         a.notes,
         a.status,
         coalesce(nullif(btrim(c.name), ''), c.display_name),
         c.phone_number
    from public.calendar_appointments a
    left join public.contacts c
      on c.id = a.contact_id
     and c.organization_id = a.organization_id
   where a.organization_id = p_org
     and a.created_by_kind = 'ai'
     and exists (select 1 from leadframe_ponte.orgs_permitidas o where o.organization_id = p_org)
     and a.created_at >= greatest(p_desde, now() - interval '1 day')
   order by a.created_at asc
   limit least(greatest(coalesce(p_limite, 50), 1), 200)
$$;

-- Função nova nasce executável por PUBLIC; no Supabase, anon/authenticated
-- também herdam. Fecha tudo e abre só para a ponte.
revoke execute on function leadframe_ponte.passagens_para_avisar(uuid, timestamptz, int)
  from public, anon, authenticated, service_role;
revoke execute on function leadframe_ponte.reunioes_para_avisar(uuid, timestamptz, int)
  from public, anon, authenticated, service_role;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'leadframe_ponte_leitor') then
    create role leadframe_ponte_leitor login noinherit;
  end if;
end
$$;

grant usage on schema leadframe_ponte to leadframe_ponte_leitor;
grant execute on function leadframe_ponte.passagens_para_avisar(uuid, timestamptz, int)
  to leadframe_ponte_leitor;
grant execute on function leadframe_ponte.reunioes_para_avisar(uuid, timestamptz, int)
  to leadframe_ponte_leitor;
alter role leadframe_ponte_leitor set statement_timeout = '10s';
alter role leadframe_ponte_leitor set idle_in_transaction_session_timeout = '30s';

-- ── Liberar a organização da Leadframe ──────────────────────────────────────
-- Id lido no Deskcomm em 2026-10-05 (não é segredo). Se este insert der erro de
-- chave estrangeira, o id mudou: confira com  select id, name from public.organizations;
insert into leadframe_ponte.orgs_permitidas (organization_id)
values ('00000000-0000-0000-0000-000000000001')
on conflict do nothing;

-- ── Conferência (deve devolver 0 linhas: ninguém além da ponte executa) ──────
-- select grantee, privilege_type
--   from information_schema.routine_privileges
--  where routine_schema = 'leadframe_ponte'
--    and grantee in ('PUBLIC', 'anon', 'authenticated', 'service_role');

-- ════════════════════════════════════════════════════════════════════════════
-- PASSO MANUAL — senha da ponte (feito pela pessoa, direto no SQL Editor)
--   Rode a linha `alter role leadframe_ponte_leitor with password '...';` que o
--   scripts/configurar-segredos.sh imprime na VPS. A mesma senha fica SÓ no .env
--   da ponte (PONTE_DB_URL).
-- ════════════════════════════════════════════════════════════════════════════
