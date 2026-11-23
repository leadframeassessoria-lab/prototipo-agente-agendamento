# Funis, etapas e campos do card

## Funis

| Funil | Etapas |
|---|---|
| **Chalés LSF** (padrão) | Novo contato → Em triagem → Qualificando → Sem resposta (frio) → Pronto para humano → Agendado → Orçamento em avaliação → Proposta (humana) → Ganho / Perdido |
| **Consultoria e Assessoria** | mesmas etapas do funil de Chalés |
| **Clientes (Pós-venda)** | Cliente novo → Em andamento → Ocorrência aberta → Aguardando cliente → Entregue / em garantia → Concluído → Encerrado |

- A IA só **avança** o card. Uma reunião confirmada leva o card para "Agendado", de qualquer etapa.
- "Proposta (humana)", "Ganho" e "Perdido" são etapas da equipe: a IA nunca faz proposta.
- Cada etapa tem um tempo esperado (por exemplo, 4 h em "Novo contato" e 72 h em "Agendado"). Passou do tempo, uma automação gera tarefa para a equipe.

## Campos que a IA preenche sozinha

A IA grava nos campos do card só o que o cliente disse, na mesma resposta, e sem deduzir nada (ferramenta `crm_update_lead`).

| Funil | Campos |
|---|---|
| Chalés LSF | cidade, uf, modelo (chalé, bangalô, loft, A-Frame, casa), terreno (tem, não tem, vai comprar), metragem, objetivo (morar, lazer, locação, investimento), prazo, fase (só ideia, tem projeto, pronto para construir) |
| Consultoria e Assessoria | empresa_segmento, desafio, momento |

Nome e e-mail do cliente **não** são gravados direto. A IA usa `crm_propose_contact_field` e uma pessoa da equipe confirma.

Além dos campos, a IA guarda **anotações por assunto** (projeto, contato e conversa) para a próxima conversa e para a pessoa da equipe que vai atender.
