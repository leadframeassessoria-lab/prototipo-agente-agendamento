-- ════════════════════════════════════════════════════════════════════════════
-- PONTE DE AVISOS LEADFRAME — desfazer tudo o que 01-leitura-dedicada.sql criou
-- ════════════════════════════════════════════════════════════════════════════
-- Não toca em nada do Deskcomm. Depois de rodar, a senha antiga da ponte deixa
-- de existir junto com o papel.

drop function if exists leadframe_ponte.passagens_para_avisar(timestamptz, int);
drop function if exists leadframe_ponte.passagens_para_avisar(uuid, timestamptz, int);
drop function if exists leadframe_ponte.reunioes_para_avisar(uuid, timestamptz, int);
drop table if exists leadframe_ponte.orgs_permitidas;
drop schema if exists leadframe_ponte;

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'leadframe_ponte_leitor') then
    execute 'drop owned by leadframe_ponte_leitor';
    execute 'drop role leadframe_ponte_leitor';
  end if;
end
$$;
