# Atendimento inteligente da Leadframe no Deskcomm CRM (entrega final)

Esta pasta guarda a **entrega final** do projeto *Assistente de atendimento contextualizado por oportunidades de CRM* (LLM Projects). O que está no resto do repositório (protótipo de agendamento e demonstração local do CRM) foi a etapa de validação da ideia.

> **O que é nosso e o que é da plataforma.** O Deskcomm é um CRM de terceiros, instalado por nós num servidor próprio (VPS Ubuntu com Docker, versão 1.104). O motor de conversa, o quadro de funis e as integrações nativas são da plataforma. O que o grupo fez está aqui: o desenho do atendimento, a configuração (agentes, prompts, roteador, funis, campos, agenda, automações, follow-up), os testes e uma integração própria, a [ponte de avisos](ponte-avisos/).

## O problema

A Leadframe vende chalés, bangalôs e lofts em Light Steel Frame e consultoria em IA e automação para empresas. Quase todo contato chega pelo WhatsApp, a qualquer hora, e uma única pessoa da equipe atende. A resposta demora, o interessado esfria e ninguém sabe em que etapa cada pessoa está.

## O fluxo, em 4 passos

```text
 Cliente no WhatsApp
        │  mensagem
        ▼
 ┌──────────────────┐   5 intenções   ┌─────────────────────────────────────────┐
 │ 1. Roteador (LLM)│ ──────────────▶ │ Agente certo: SDR Chalés · Consultoria · │
 └──────────────────┘                 │ Pós-venda · Financeiro · Suporte (LLM)   │
                                      └───────────────┬─────────────────────────┘
                     ┌────────────────────────────────┼───────────────────────────┐
                     ▼                                ▼                           ▼
        2. Card no funil                 3. Reunião com Meet           4. Passagem para humano
        cria, move a etapa,              consulta horários livres,     a IA para de responder;
        preenche cidade, modelo,         marca no Google Agenda,       a ponte avisa o Bruno
        metragem, prazo...               link do Meet no WhatsApp      no WhatsApp dele
```

1. **Conversa e roteador.** O roteador lê a mensagem e escolhe uma de 5 intenções; cada uma chama um agente. Ver [configuracao/roteador.md](configuracao/roteador.md).
2. **Card no funil.** O agente cria a oportunidade no funil certo, move a etapa e grava os dados do projeto nos campos do card. Ver [configuracao/funis-e-campos.md](configuracao/funis-e-campos.md).
3. **Reunião com Meet.** O agente consulta os horários livres na agenda real, marca a reunião de 30 minutos e o sistema manda o link do Google Meet. Ver [configuracao/agenda-automacoes-followup.md](configuracao/agenda-automacoes-followup.md).
4. **Passagem para humano.** Quando o cliente pede uma pessoa, a IA para de responder e a [ponte de avisos](ponte-avisos/) manda um aviso ao WhatsApp do responsável.

## Onde entra o LLM

| | Quem decide |
|---|---|
| Qual intenção a mensagem tem, qual agente atende | **LLM** (roteador) |
| O que responder, que pergunta fazer, que dado extrair para o card, quando consultar a agenda, que horário propor, quando passar para humano, o que anotar | **LLM** (agente) |
| Quais horários estão livres; criar a reunião e o link do Meet | **Sistema** (Google Agenda) |
| Não enviar depois da passagem, para quem pediu para parar, ou fora da janela de 24 h da Meta | **Sistema** (travas de código) |
| Nome e e-mail do cliente entrarem na ficha | **Pessoa da equipe** (a IA só propõe) |

Modelo e ferramentas de cada agente: [configuracao/agentes.md](configuracao/agentes.md).

## Integrações

- **WhatsApp Business Platform** (API oficial da Meta): mensagens do número oficial e modelos de mensagem aprovados.
- **Google Agenda e Google Meet**: horários livres, reunião e link.
- **API de LLM** (OpenAI): GPT-5.6 Luna nos 5 agentes e GPT-5.6 Terra no roteador. A API da Anthropic (Claude) também foi ligada, para os testes de troca de modelo. Ver [testes/README.md](testes/README.md).
- **PostgreSQL (Supabase) e Redis**: dados do CRM e fila de mensagens.
- **Ponte de avisos** (código nosso, Node.js + PostgreSQL, Docker).

## Testes

Ver [testes/README.md](testes/README.md).

## Como ver funcionando

O atendimento roda em produção no número oficial de WhatsApp da Leadframe, informado na apresentação. Basta mandar uma mensagem como "quero saber sobre um chalé" e acompanhar, no CRM, o card sendo criado e preenchido. O CRM é privado (tem login), por isso a demonstração do painel é feita ao vivo na apresentação.

Para rodar a **ponte de avisos** localmente, sem credenciais, ver [ponte-avisos/README.md](ponte-avisos/README.md). Para a demonstração local da etapa anterior, ver o [README principal](../README.md).

## O que ficou de fora deste repositório (público) e por quê

- **Prompts completos dos agentes:** só trechos, para não expor como contornar o atendimento.
- **Telefones, IDs da conta da Meta, IDs da organização, endereço do servidor e do banco:** trocados por marcadores.
- **Senhas, tokens e chaves:** nunca estiveram no código; ficam no `.env` do servidor.
- **Conversas e dados de clientes:** nenhum.
