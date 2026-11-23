# Ponte de avisos

Código do grupo. Quando um agente do Deskcomm **passa uma conversa para humano** ou **marca uma reunião**, a ponte manda na hora uma mensagem ao WhatsApp do responsável da equipe. A mensagem traz nome, motivo, o que o cliente quer, resumo, última mensagem e um botão "Abrir conversa".

**Por que existe:** no Deskcomm, a passagem para humano só gera alerta dentro do painel, e o aviso nativo por WhatsApp não funciona com a API oficial da Meta. Sem a ponte, o responsável só saberia da passagem se estivesse com o CRM aberto.

## Como funciona

```text
PostgreSQL do CRM ──(leitura, usuário só-leitura)──▶ ciclo a cada N s ──▶ monta a mensagem
                                                                              │
WhatsApp do responsável ◀── modelo aprovado pela Meta ◀── Graph API (Meta) ◀──┘
```

- `src/fonte-postgres.mjs`: lê as passagens e reuniões novas, por um usuário de banco **só leitura** (`sql/01-leitura-dedicada.sql`).
- `src/ciclo.mjs`: não repete aviso para a mesma conversa em menos de 30 min e não reenvia depois de reiniciar (`src/estado.mjs`).
- `src/mensagem.mjs` e `src/modelo.mjs`: montam o modelo de mensagem aprovado (`meta/`).
- `src/meta.mjs`: envia pela API oficial e classifica os erros sem nunca registrar o token.
- `src/saude.mjs`: o contêiner fica *unhealthy* se a configuração quebrar (token vencido, modelo pausado).

## Rodar os testes e a prévia (sem credenciais)

```bash
npm ci
npm run teste          # 64 testes
npm run previa-local   # mostra a mensagem que seria enviada, sem enviar
```

Em produção roda em Docker (`docker compose up -d`), com as variáveis de `.env.example`. Os valores reais (token, senha do banco, números) ficam só no servidor.

> Nesta cópia pública, telefones, IDs da conta da Meta, ID da organização e endereço do banco foram trocados por marcadores.
