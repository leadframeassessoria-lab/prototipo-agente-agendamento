# Agenda, automações e follow-up

## Agenda

- **Tipo de reunião único:** "Reunião", 30 minutos, Google Meet, 15 minutos de folga depois, pedida com pelo menos 1 hora de antecedência, até 60 dias à frente. Não precisa de confirmação manual.
- **Fonte dos horários:** a agenda do Google do responsável. A IA consulta os horários livres (`crm_find_free_slots`), oferece 2 ou 3 em dias diferentes e marca o escolhido (`crm_find_and_book_appointment`).
- **Link do Meet:** o sistema envia pelo WhatsApp logo depois da marcação. O convite por e-mail sai só quando a equipe confirma o e-mail na ficha.
- **Lembrete:** 24 h antes.
- **Regra de prompt:** "reunião marcada é só a que aparece na agenda". Antes de falar de qualquer reunião, a IA consulta a agenda, e a agenda vale mais que a anotação. Essa regra nasceu de uma falha real: a IA citou uma reunião que já tinha sido cancelada.

## Automações ativas (10)

| Gatilho | Ação |
|---|---|
| Lead novo | Responsável da equipe vira dono do card |
| 1 dia em "Pronto para humano" (Chalés e Consultoria) | Tarefa para a equipe |
| 7 dias em "Sem resposta (frio)" (Chalés e Consultoria) | Tarefa para a equipe |
| 5 dias em "Orçamento em avaliação" (Chalés e Consultoria) | Tarefa para a equipe |
| Negócio ganho | Card novo em "Clientes (Pós-venda)" |
| Reunião cancelada | Tarefa: conferir a anotação da IA e combinar novo horário |
| Reunião realizada | Tarefa de retorno ao cliente |

## Follow-up (2 fluxos ativos)

- **Retomada por silêncio:** se o cliente para de responder, o agente faz uma retomada leve dentro de 24 h. Fora das 24 h, usa um modelo de mensagem aprovado pela Meta. Depois de 7 dias no frio, manda uma reativação. O prompt proíbe culpa, urgência falsa e "não vou insistir".
- **Falta em reunião:** gera uma tarefa interna para a equipe.
