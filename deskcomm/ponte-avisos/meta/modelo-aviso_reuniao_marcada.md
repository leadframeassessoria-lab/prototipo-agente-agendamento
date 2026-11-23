# Modelo `aviso_reuniao_marcada` — registro do envio à Meta

- **Texto aprovado pelo operador:** 2026-10-05, ~22:45 UTC, no chat do Claude Code ("Aprovo este texto").
- **Conta do WhatsApp:** Leadframe Consultoria e Assessoria — WABA `100000000000001`.
- **Número que envia:** +55 00 9000-0002 (ID `100000000000002`).
- **Categoria:** Utilidade · tipo Padrão · idioma Português (BR) · tipo de variável: Número.
- **Validade da mensagem:** 12 horas (mesma escolha do `aviso_passagem_humano`).
- **Enviado para análise:** 2026-10-05 ~23:00 UTC, pela bancada Claude Code no Chrome do operador ("Browser 1"), com o texto aprovado por ele. A Meta confirmou: "Seu modelo de mensagem foi enviado para análise."
- **Status conferido logo depois:** **Em análise** (lista de modelos do Gerenciador do WhatsApp).
- **Aprovado:** conferido em 2026-10-06 ~00:08 UTC, **Ativo**, categoria Utilidade (não reclassificado).
- **Aviso de teste** fictício enviado ao Bruno em 2026-10-06 ~00:09 UTC (accepted). `PONTE_REUNIOES=ligado` desde 00:09:55 UTC (marco zero das reuniões).
- Pegadinha do formulário: o editor completa `{{` sozinho para `{{n}}`. Digitar `{{1}}` inteiro vira `{{1}}1}}`. O exemplo do link do botão só aparece depois de sair do campo de URL.

## Corpo (exatamente como deve ser enviado)

```
📅 Reunião marcada pela IA

Cliente: {{1}}
Telefone: {{2}}
Quando: {{3}}
Assunto: {{4}}
Resumo da conversa: {{5}}

O compromisso já está na sua agenda Google, com o link do Meet.
```

## Botão

- Tipo: Acessar o site · texto **"Abrir conversa"** · URL **dinâmica**:
  `https://crm.exemplo.com.br/app/inbox/{{1}}` (o `{{1}}` é o id da conversa no Deskcomm).

## Amostras para a análise (fictícias — nenhum dado de cliente real)

| Variável | Amostra |
|---|---|
| {{1}} | Maria Souza |
| {{2}} | +55 11 98765-4321 |
| {{3}} | quarta-feira, 07/10 às 9h30 |
| {{4}} | Reunião sobre chalé em Steel Frame |
| {{5}} | Cliente quer construir um chalé em Cuiabá, já tem terreno e ainda não tem projeto. |
| botão {{1}} | https://crm.exemplo.com.br/app/inbox/3f2b8c1e-5a4d-4e7b-9c21-8d6f0a1b2c3d |

## Depois da aprovação

`PONTE_REUNIOES=ligado` no `.env` da VPS e `docker compose up -d`. Antes disso a ponte não lê reuniões.
Prova isolada do modelo: `docker compose exec ponte-avisos sh -c "PONTE_MODO=envio node scripts/enviar-teste.mjs --reuniao --confirmo-envio"`.

## Se o texto mudar

Editar o modelo na Meta abre nova análise. O texto em `src/modelo.mjs` (`MODELO_REUNIAO`) precisa mudar junto — `teste/estado-config-modelo.test.mjs` trava o corpo atual.
