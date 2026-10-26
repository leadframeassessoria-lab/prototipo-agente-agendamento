## Leadframe CRM — demonstração local para apresentação

Evolução do protótipo acadêmico de agendamento: o foco passa a ser **o registro da oportunidade no CRM**, sua etapa, a conversa e a trilha de ações. O agendamento é uma operação demonstrada dentro desse contexto, não o produto inteiro.

> **Não é o CRM de produção, não é uma cópia completa dele e não está integrado a ele.** Interface didática, contatos fictícios e reservas simuladas em memória. Nenhum e-mail, Meet, WhatsApp ou aviso a atendente é enviado.

## 📊 Status Atual

- **Testes:** 48/48 passando ✓ (27 backend + 5 regressão + 7 web + 4 documentação + 5 demo)
- **Correções P2:** 4 corrigidas e validadas
- **Interface:** Funcional com 3 funis, kanban, ficha, movimentação, conversa, disponibilidade, reservas, auditoria e reset

## Rodar a demonstração

Requisitos: **Python 3.9+**. Runtime e testes usam apenas a biblioteca-padrão. Não exige instalação de pacote, login, chave ou banco.

Na pasta do projeto:

```bash
python demo_crm.py
```

Abra **http://127.0.0.1:8765** no navegador da **mesma máquina**. Se a porta estiver ocupada:

```bash
python demo_crm.py --port 8766
```

O servidor escuta somente no loopback. Não é um serviço público. Para apresentar no computador, baixe/copie o projeto e rode nele; não abra porta da VPS para a internet. `Ctrl+C` encerra. O botão de reinício limpa somente a sessão fictícia.

Para conferir o roteiro sem navegador:

```bash
python demo_crm.py --roteiro
```

Para executar os testes do CRM e do servidor local:

```bash
python -m unittest discover -s tests -v
```

## O que mostrar

1. Escolha um dos três funis e abra uma oportunidade `DEMO-`.
2. Consulte a etapa pela conversa: `qual o status da minha oportunidade?`.
3. Mova a oportunidade pelo seletor e confira a etapa após a alteração e a trilha de eventos.
4. Simule uma reunião com mensagem completa, incompleta ou informal.
5. Peça um humano ou faça opt-out e observe o bloqueio da automação local.
6. Confira a reserva marcada como **simulada**, nunca como compromisso real.

O passo a passo com mensagens exatas está em [`docs/roteiro-apresentacao.md`](docs/roteiro-apresentacao.md). A apresentação está em [`docs/apresentacao.html`](docs/apresentacao.html), com versão PDF no mesmo diretório.

### Relógio e agenda fictícios

- Referência fixa: **02/11/2026**; não usa o dia do computador.
- Agenda disponível: **03, 04 e 05/11/2026**.
- Horários da fixture: `09:00`, `10:00`, `11:00`, `14:00`, `15:00`, `16:00`.
- Em **03/11 às 14:00**, o horário já começa ocupado para demonstrar conflito.
- Duração usada na demo: **30 minutos**.
- Sem fuso ou calendários externos; datas/horas são as do cenário didático.

## Fato observado × comportamento simulado

**Configuração observada em consulta somente leitura em 26/10/2026:**

- Funis: `Consultoria e Assessoria`, `Chalés LSF`, `Clientes (Pós-venda)`.
- Nomes de etapas desses funis.
- Tipo de evento `Reunião`, duração configurada de 30 minutos e local configurado como Google Meet.

Fonte sanitizada: [`docs/evidencias-crm-2026-10-26.json`](docs/evidencias-crm-2026-10-26.json). A consulta de configuração **não comprova integração ponta a ponta**. O cadastro de um local como Google Meet não significa que esta demonstração cria uma sala.

**Simulados aqui:** identificadores `DEMO-`, pessoas, conversas, movimentações, disponibilidade, reservas, handoff e opt-out. A interface é uma representação didática, **não uma captura ou reprodução fiel da interface de produção**. Não foram exportados clientes, conversas, fila ou indicadores comerciais. Nenhuma escrita no CRM real faz parte deste trabalho.

## Arquitetura

```text
Navegador local
    │ HTTP para 127.0.0.1
    ▼
demo_crm.py — servidor e API didáticos
    │ chamadas Python locais
    ▼
src/crm_demo.py — instância CRM em memória + lock
    ├─ snapshot sanitizado de nomes de funis/etapas
    ├─ NLULocal + normalização + portões do protótipo
    ├─ oportunidades, mensagens e campos com origem
    ├─ disponibilidade → validação → reserva simulada
    └─ histórico de movimentação, handoff e opt-out

Sem conector, credencial ou chamada ao CRM de produção.
```

A intenção aprofundada continua sendo `agendar_reuniao`, agora ligada à oportunidade. `consultar_status` lê a **etapa da oportunidade**. Handoff e opt-out são controles locais. Movimentar etapa exige ação explícita no formulário; uma instrução embutida na conversa não move o card.

Não há chamada a LLM na demonstração. O extrator é determinístico. [`prompts/crm-demo.md`](prompts/crm-demo.md) documenta o contrato e as regras de interpretação; é uma referência para apresentação, não um prompt enviado a um provedor. O prompt do adaptador LLM legado permanece em [`prompts/sistema.md`](prompts/sistema.md).

## Os cinco entregáveis do briefing

- **1. Repositório e execução:** este README, `demo_crm.py`, `web/`, `src/crm_demo.py` e o snapshot sanitizado. A mudança foi preparada em branch local; o link remoto não passa a conter estes arquivos sem publicação autorizada.
- **2. Intenção e prompt:** arquitetura acima e [`prompts/crm-demo.md`](prompts/crm-demo.md), com a distinção entre contrato documentado e runtime sem LLM.
- **3. Demonstração funcionando:** interface interativa, `--roteiro` e [`docs/roteiro-apresentacao.md`](docs/roteiro-apresentacao.md).
- **4. Resultados dos testes:** cenários automatizados em `tests/`, transcritos e relatórios reais em `docs/evidencias/`. O relatório de verificação identifica o que foi efetivamente executado.
- **5. Dificuldades e melhorias:** [`docs/dificuldades-e-melhorias.md`](docs/dificuldades-e-melhorias.md).

## Evidências e limites

- O estado é isolado por processo, mas compartilhado pelas abas conectadas à mesma execução local; não há login, usuários ou isolamento multi-tenant.
- Reiniciar o servidor ou a demo descarta as fixtures em memória; não há persistência nem recuperação de produção.
- O lock impede duas reservas locais simultâneas no mesmo horário dentro do processo. Isso não substitui transação de banco distribuída.
- A NLU cobre um domínio fechado. Ambiguidade gera pergunta; não promete compreender qualquer frase.
- Os portões reconhecem padrões de dado sensível e instrução embutida, mas **não são um detector universal de dados pessoais**. Não insira informações reais.
- A trilha registra ações locais em memória; não é auditoria imutável, certificação ou log do CRM real.
- O servidor tem proteções de entrada e restringe-se a loopback; não foi projetado para exposição pública.
- O botão de reset é exclusivo desta demo. Não existe chamada de exclusão ao CRM real.

## Correções validadas

As correções P2 identificadas pela revisão independente foram implementadas e testadas:

| ID | Problema | Status | Evidência |
|---|---|---|---|
| sensivel-optout | Detecta dados sensíveis mesmo com opt-out | ✅ Corrigido | `docs/evidencias/revisao-sensivel-green.txt` |
| coleta-obsoleta | Correção de data não limpava coleta antiga | ✅ Corrigido | `docs/evidencias/revisao-reserva-green.txt` |
| correcao-assunto | Data alterada podia gerar reserva indevida | ✅ Corrigido | `docs/evidencias/revisao-assunto-green.txt` |
| hora-impossivel | Regex "às 15:99" não invalidava minutos | ✅ Corrigido | `docs/evidencias/revisao-hora-green.txt` |

## Legado preservado

Os arquivos e comandos originais de agendamento continuam disponíveis; não representam a integração atual do CRM:

```bash
python executar_testes.py
python demo_conversa.py
python src/agenda_api.py 8000
```

O README original foi arquivado em [`docs/legado-agendamento.md`](docs/legado-agendamento.md), ajustando somente os destinos dos links relativos à nova pasta. Saídas legadas que dizem "confirmação enviada" pertencem ao antigo simulador: **não comprovam envio de e-mail real e não são usadas como confirmação na nova demo**.

## Publicação

Branch de trabalho: `feat/proex-crm-atual`. Nenhum push, PR, merge, deploy ou alteração de produção é necessário para testar localmente. Publicar a atualização no GitHub é uma etapa separada, dependente de autorização humana.