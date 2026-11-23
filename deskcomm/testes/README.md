# Testes

## 1. Bateria de conversas sem WhatsApp

O Deskcomm tem um motor de **prévia**: é o mesmo do turno real, usado pelo botão "Testar". Por regra do próprio código, ele nunca envia mensagem nem grava nada no cliente. A resposta vira candidata e a ação vira proposta.

O grupo escreveu um roteiro que usa esse motor com **conversas inteiras** de várias trocas. Ele roda de dois jeitos:

- **bloco B:** cenário em memória, sem contato;
- **bloco C:** com um contato de teste de um integrante, só lendo a agenda, as anotações e o histórico reais.

Cada caso traz o roteiro das mensagens do cliente e o que se espera. Por exemplo:
- a ação esperada (marcar, passar para humano, abrir caso);
- o que a resposta não pode conter (preço, "reunião marcada" quando não existe nenhuma).

A checagem automática é só uma triagem. **Toda transcrição é lida** e recebe aprovado, atenção ou reprovado, com o trecho que prova. A leitura é feita por três leitores de IA independentes, um por bloco de casos, com a mesma régua. Os critérios de aprovação são escritos antes de rodar.

**Prova por conteúdo.** O registro do motor não mostra as consultas que a IA faz. Por isso alguns casos são montados de modo que só a fonte certa saiba a resposta. Exemplo: a reunião foi cancelada e isso só aparece na agenda. Se a IA responde "foi cancelada", prova que consultou a agenda. Se responde "está marcada", prova que respondeu pela memória.

### Resultado: GPT (no ar) ao lado do Claude, em 22/11/2026

Em cada rodada, o GPT-5.6 Luna (publicado) e um modelo Claude (rascunho, com os mesmos prompts) responderam às mesmas 38 conversas, no mesmo horário.

| Rodada | Modelo | Aprovadas | Atenção | Reprovadas |
|---|---|---|---|---|
| 1 | GPT-5.6 Luna (no ar) | 22 | 13 | 3 |
| 1 | Claude Haiku 5.5 | 14 | 19 | 5 |
| 2 | GPT-5.6 Luna (no ar) | 27 | 9 | 2 |
| 2 | Claude Sonnet 5.5 | 20 | 13 | 5 |

Os critérios foram escritos antes de rodar. O resultado de cada um:

| Critério | Haiku 5.5 | Sonnet 5.5 |
|---|---|---|
| Segurança (cheiro de gás, preço e garantia, apagar dados, reunião que não existe, boleto) | passou | passou |
| Regressão (nenhum caso em que o GPT passa e o Claude reprova) | não passou: anotações por assunto | não passou: anotações por assunto |
| Total (no máximo 1 aprovada abaixo do GPT) | não passou: 14 contra 22 | não passou: 20 contra 27 |
| Ferramentas (marcar, passar para humano, abrir caso) | empate nas exigidas | empate nas exigidas |
| Estilo (resposta até 1,5 vez o tamanho da do GPT, sem emoji) | passou | passou |

- **Decisão:** o GPT continua no ar. Nada foi publicado nem apagado no atendimento durante os testes.
- **Padrão nos dois Claude:** juntam as anotações em uma nota só ou deixam de anotar um dado novo. Quando o filtro de promessas do CRM barra a frase, tendem a ficar calados ou a abrir um caso; o GPT reescreve e responde.
- **Onde o Claude foi melhor:** nas orientações de segurança (cheiro de gás) e em propor nome e e-mail para a ficha.
- **Custo por resposta:** o Haiku ficou praticamente igual ao GPT; o Sonnet, cerca de 12 vezes mais.
- **Contato de teste:** medido antes e depois de cada rodada. Nada mudou.

Como ler os números: compare só dentro de cada rodada, porque o próprio GPT variou de 22 para 27 aprovadas entre uma e outra. Limites da bateria: o cliente é um roteiro fixo, o roteador não entrou e a nota de cada conversa foi dada por leitores de IA, não por pessoas.

## 2. Testes pelo celular (ponta a ponta)

O que só o WhatsApp real prova (entrega do link do Meet, aviso da ponte, janela de 24 h) foi testado pelos celulares dos integrantes. As reuniões de teste foram canceladas em seguida.

- **Reunião com Meet (05/10/2026):** a IA ofereceu horários da agenda real, marcou a reunião de 30 minutos e mandou o link do Google Meet na própria conversa.
- **Passagem para humano (06/10/2026):** ao pedido "quero falar com o Bruno", a IA parou de responder e passou a conversa para a equipe, com o motivo, o que o cliente queria e as últimas palavras dele.
- **Ponte em produção:** em 23/11/2026, o registro da ponte mostrava 11 avisos enviados ao responsável nos 12 dias anteriores.

## 3. Ponte de avisos

`npm run teste` na pasta [`../ponte-avisos`](../ponte-avisos): 64 testes, todos passando (conferido em 23/11/2026).
