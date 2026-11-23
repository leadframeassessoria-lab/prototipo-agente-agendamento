# Modelo `aviso_passagem_humano` — registro do envio à Meta

- **Enviado para análise:** 2026-10-05, pela bancada Claude Code no Chrome do operador, a pedido do operador (texto aprovado por ele no chat).
- **Conta do WhatsApp:** Leadframe Consultoria e Assessoria — WABA `100000000000001` (empresa Meta `1910000000000381`, do responsável pela conta).
- **Número que envia:** +55 00 9000-0002 (conectado, qualidade Alta em 2026-10-05).
- **Categoria:** Utilidade · tipo Padrão · idioma Português (BR) · tipo de variável: Número.
- **Validade da mensagem:** 12 horas (o padrão da Meta seria 10 minutos: com o celular do Bruno sem sinal por mais que isso, o aviso se perderia).
- **Status no envio:** Em análise.
- **Status conferido em 2026-10-05 (mesmo dia):** **Ativo — Qualidade pendente**, categoria **Utilidade** (não reclassificado).
- **ID do número que envia:** `100000000000002` (Deskcomm › Conexões › API Oficial; o Deskcomm usa Graph v22.0).

## Corpo (exatamente como enviado)

```
🔔 Atendimento para você assumir

Cliente: {{1}}
Telefone: {{2}}
Motivo: {{3}}
O que o cliente quer: {{4}}
Resumo da conversa: {{5}}
Última mensagem do cliente: {{6}}

A IA já parou de responder esse cliente. Responder aqui não chega ao cliente: use o botão abaixo.
```

## Botão

- Tipo: Acessar o site · texto **"Abrir conversa"** · URL **dinâmica**:
  `https://crm.exemplo.com.br/app/inbox/{{1}}` (o `{{1}}` é o id da conversa no Deskcomm).

## Amostras enviadas (fictícias — nenhum dado de cliente real)

| Variável | Amostra |
|---|---|
| {{1}} | Maria Souza |
| {{2}} | +55 11 98765-4321 |
| {{3}} | Pediu para falar com uma pessoa |
| {{4}} | Entender como funciona a gestão de redes sociais |
| {{5}} | Cliente perguntou sobre gestão de redes sociais e pediu para continuar com alguém da equipe. |
| {{6}} | Quero falar com um atendente, por favor. |
| botão {{1}} | https://crm.exemplo.com.br/app/inbox/3f2b8c1e-5a4d-4e7b-9c21-8d6f0a1b2c3d |

## Outros modelos que já existiam na conta (não mexidos)

- `handoff_briefing_leadframe` (Utilidade, pt_BR, ativo, 30/09/2026) — parágrafo único, sem botão; da fase Hermes.
- `handoff_interno_leadframe` (Utilidade, pt_BR, ativo, 28/09/2026) — da fase Hermes; teve envios.

## Se o texto mudar

Editar o modelo na Meta abre nova análise. O texto em `src/modelo.mjs` precisa mudar junto — `teste/estado-config-modelo.test.mjs` trava o corpo atual.
