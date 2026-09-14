# Protótipo de agente de agendamento por linguagem natural

Recebe uma mensagem escrita como gente escreve, identifica a intenção, extrai o
que precisa, consulta um serviço de agenda, pergunta o que faltou e responde
**sem inventar dado**.

A última parte não é promessa. É uma verificação que roda a cada turno e
reprova a resposta se ela contiver um valor que nenhuma fonte devolveu.

---

## Rodar

Precisa de **Python 3.9+** e mais nada. Nenhuma biblioteca externa, nenhuma
chave de API, nenhum banco para instalar.

```bash
python executar_testes.py
```

Isso sobe o serviço de agenda numa porta livre, roda os oito testes e imprime o
transcrito completo: mensagem, intenção, campos extraídos, chamadas HTTP,
resposta e resultado da auditoria. A saída gravada está em
[`docs/resultado-dos-testes.txt`](docs/resultado-dos-testes.txt).

Para conversar ao vivo:

```bash
python demo_conversa.py
```

`--debug` mostra os bastidores de cada turno; `/estado` dentro da conversa
mostra o que o agente sabe até ali. Para subir só a API e consultá-la na mão:

```bash
python src/agenda_api.py 8000
```

```bash
curl "http://127.0.0.1:8000/agenda/disponibilidade?data=2026-09-22"
```

---

## Evidências no repositório

| Arquivo | O que contém |
|---|---|
| [`docs/resultado-dos-testes.txt`](docs/resultado-dos-testes.txt) | Saída completa dos oito testes, turno a turno |
| [`docs/demonstracao.txt`](docs/demonstracao.txt) | Uma sessão real de conversa, do primeiro turno à confirmação |
| [`prompts/sistema.md`](prompts/sistema.md) | O prompt usado pelo adaptador de modelo |

Os dois arquivos de saída são gerados pelos comandos acima.

---

## A intenção escolhida

Definimos três intenções e implementamos uma:

| Intenção | Estado |
|---|---|
| **`agendar_reuniao`** | **implementada** |
| `consultar_status` | implementada (menor, consulta por protocolo) |
| `informacao_servico` | implementada (menor, catálogo) |

`agendar_reuniao` foi a escolha porque é a única das três que exercita os seis
requisitos de uma vez: precisa de cinco campos distintos, precisa consultar a
agenda antes de responder, tem um caminho de falha honesta (o horário pedido
está ocupado) e tem um caso em que a informação parece existir mas não existe
("de tarde" não é um horário). As outras duas ficaram implementadas em forma
mínima porque a classificação precisa de mais de uma opção para poder errar.

O prompt está em [`prompts/sistema.md`](prompts/sistema.md).

---

## Como funciona

```
mensagem
   │
   ├─▶ normalização      remove acento, expande gíria, tolera erro de digitação
   │
   ├─▶ PORTÕES           opt-out · dado sensível · escalonamento · injeção
   │                     verificados ANTES de interpretar; vencem tudo
   │
   ├─▶ intenção          três intenções + "indefinida" abaixo do limiar
   │
   ├─▶ extração          cada campo com procedência e um de três estados:
   │                     preenchido · lacuna · PARCIAL
   │
   ├─▶ falta algo?  ──▶  UMA pergunta, a que destrava mais
   │
   ├─▶ consulta HTTP     GET disponibilidade · POST reserva
   │
   ├─▶ resposta          montada só com o que o usuário disse + o que a API devolveu
   │
   └─▶ AUDITORIA         varre a resposta pronta; todo número, data, hora e
                         protocolo precisa ter origem rastreável, ou reprova
```

### As três decisões que sustentam o resto

**1. `PARCIAL` é um estado, não um valor vazio.** Quando alguém escreve "de
tarde", o campo `hora` não fica vazio nem fica com um chute: fica marcado como
parcial, com a nota `tarde`. O agente então consulta a agenda daquele dia,
filtra os horários **que a API devolveu** pela faixa da tarde, e devolve só
esses. O período restringe o que já é verdade; nunca cria horário.

**2. O modelo preenche formulário, não escreve resposta.** No modo com LLM
([`src/nlu_llm.py`](src/nlu_llm.py)), o modelo devolve JSON com seis campos e
nada mais. Quem redige a resposta é código, a partir do retorno da API. Um
modelo que não tem campo para "horário disponível" na saída não tem como
alucinar um.

**3. A auditoria precisa poder reprovar.** O teste 8 existe só para isso: a
mesma função recebe uma resposta honesta e uma com um horário inventado, e tem
que separar as duas. Se aprovasse as duas, os quinze "APROVADA" dos testes
anteriores não significariam nada.

---

## Arquivos

```
├── executar_testes.py      os 8 testes, de ponta a ponta
├── demo_conversa.py        conversa interativa
├── prompts/sistema.md      o prompt (e por que ele não escreve a resposta)
├── src/
│   ├── agenda_api.py       serviço HTTP + SQLite, a fonte de verdade externa
│   ├── normalizacao.py     português informal em forma buscável
│   ├── nlu.py              intenção + extração com procedência (determinístico)
│   ├── nlu_llm.py          mesma interface, via modelo (opcional)
│   ├── portoes.py          os quatro portões duros
│   ├── dialogo.py          o que falta e qual pergunta fazer
│   └── agente.py           orquestração + cliente HTTP + auditoria
└── docs/
    └── resultado-dos-testes.txt
```

---

## A API

Serviço local, semeado de forma determinística: janela de 30 dias a partir de
2026-09-15, dias úteis, sete horários por dia, com alguns já ocupados para que
o caminho de indisponibilidade seja alcançável.

| Rota | O que faz |
|---|---|
| `GET /agenda/disponibilidade?data=` | horários livres do dia |
| `GET /agenda/disponibilidade?data=&hora=` | aquele horário está livre? + alternativas |
| `POST /agenda/reservas` | cria a reserva, devolve protocolo |
| `GET /agenda/reservas/<protocolo>` | consulta uma reserva |
| `GET /catalogo/servicos` | tipos de atendimento |

---

## Limites conhecidos

- **A extração determinística é de domínio fechado.** Ela cobre bem as formas
  de escrever data, hora e nome que aparecem nos testes. Uma frase construída
  de outro jeito ("pode ser no mesmo horário da semana passada") não é
  entendida. Por projeto, isso vira lacuna e pergunta, não um chute.
- **Não há fuso horário.** Tudo é hora local do serviço.
- **O banco é em memória.** Ele é recriado a cada execução. As reservas
  persistem durante a sessão. Por isso o teste 6 mostra 23/09 já sem o horário
  que o teste 2 reservou, o que é a prova de que o `POST` gravou de verdade.
- **A auditoria verifica procedência, não veracidade.** Ela garante que todo
  valor afirmado veio da API ou do usuário. Ela não sabe se a API está certa.
