# Roteiro de apresentação — do agente isolado ao contexto CRM

**Material interno para validação.** Demo local, dados fictícios, sem CRM de produção. Interface didática: não mostrar como captura do sistema real nem como prova de integração ativa.

## Preparação

1. Na pasta do projeto, execute `python demo_crm.py`.
2. Abra `http://127.0.0.1:8765` no navegador da mesma máquina.
3. Mantenha visível o aviso de simulação. Use apenas pessoas `Demo` e e-mails `example.com`.
4. Antes de cada cenário independente, reinicie a demo. Isso descarta somente o estado fictício.

## Abertura

> O protótipo anterior mostrava um agente de agendamento isolado. Nesta versão, a unidade principal é a oportunidade no CRM: funil, etapa, conversa, contexto e histórico. O agendamento é uma das operações. Tudo que veremos roda localmente; nenhuma ação atinge clientes ou o CRM real.

## 1. Registro → conversa → etapa → histórico

Selecione o funil **Consultoria e Assessoria** e a oportunidade **DEMO-001 / Pessoa Demo A**.

Envie:

```text
qual o status da minha oportunidade?
```

O assistente lê `Novo contato` do registro. Não inventa protocolo ou reunião. Pelo seletor de movimentação, altere para **Qualificando**. Consulte o status novamente e confira a mudança no registro e o evento com etapa anterior e posterior.

**Ponto de apresentação:** a conversa parte do contexto do CRM; a resposta acompanha o registro após uma ação explícita. Comentar nomes de etapas não demonstra funil comercial aprovado fora dessa configuração observada.

## 2. Mensagem completa

Reinicie e selecione DEMO-001. Envie:

```text
Sou Pessoa Demo, quero marcar uma reunião dia 03/11 às 15h sobre atendimento. Meu email é demo@example.com
```

Confira:

- Reserva identificada como **simulada**, com ID `DEMO-R...`.
- Data 03/11/2026, hora 15:00 e duração de 30 minutos na fixture.
- Oportunidade na etapa `Agendado` e eventos de reserva/movimento.
- Aviso explícito de que nenhum e-mail, Meet ou notificação foi enviado.

## 3. Mensagem incompleta e resposta curta

Reinicie e selecione DEMO-001. Envie uma mensagem de cada vez:

```text
Quero agendar uma reunião
03/11
10h
Pessoa Demo
demo@example.com
atendimento digital
```

Antes da última informação, não pode existir reserva. O assistente faz **uma pergunta por vez** e usa o contexto para entender `Pessoa Demo` como resposta ao campo nome, sem exigir “meu nome é”.

## 4. Linguagem informal — período não é horário

Reinicie e envie:

```text
eae blz qria marca um papo dia 04/11 de tarde, poe no nome de Pessoa Demo, meu email eh demo@example.com
```

Mostre que **hora ainda está faltando**. “De tarde” não vira 14:00 por suposição; apenas filtra os horários disponíveis da agenda fictícia. Continue:

```text
16h ta otimo
atendimento digital
```

Confira a reserva simulada em 04/11 às 16:00 e sua ligação com a oportunidade.

## 5. Horário ocupado

Reinicie e envie:

```text
Quero marcar reunião dia 03/11 às 14h
```

O horário vem ocupado na fixture. A demo não confirma reunião nem reserva esse horário; pede uma alternativa entre os horários locais disponíveis.

## 6. Controle humano e opt-out

Teste os casos separadamente, reiniciando antes de cada um:

```text
quero falar com uma pessoa
```

Resultado: handoff **simulado**, automação local pausada e etapa `Pronto para humano`. Não afirmar que um atendente está online ou foi notificado.

```text
não quero mais receber mensagens de vocês
```

Resultado: opt-out local; tentativa posterior de agendar não gera reserva. Não é envio real de WhatsApp nem alteração de lista de contatos real.

## 7. Funis e pós-venda

Alterne entre **Consultoria e Assessoria**, **Chalés LSF** e **Clientes (Pós-venda)**. Os nomes/etapas foram observados em consulta somente leitura de 26/10/2026. Pessoas, cards e interações são fixtures.

No pós-venda, mostre a ocorrência fictícia e a movimentação entre as etapas permitidas daquele funil. A demo não transfere oportunidades entre funis.

## Evidências técnicas

```bash
python demo_crm.py --roteiro
python -m unittest discover -s tests -v
python executar_testes.py
```

O primeiro comando gera uma execução reproduzível da nova demo. O segundo testa o CRM e HTTP local. O terceiro preserva a regressão do protótipo antigo. Relatórios, transcritos e o documento de verificação ficam em `docs/evidencias/`.

## Encerramento

> Esta entrega é uma representação local para explicar o novo contexto CRM. Não é migração, integração produtiva ou réplica completa do produto. A configuração observada foi separada das operações simuladas; a publicação da branch no GitHub e qualquer ação sobre produção são etapas fora desta execução local.
