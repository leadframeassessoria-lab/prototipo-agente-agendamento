# Roteador "Recepção Leadframe"

O roteador é o primeiro LLM a ler cada mensagem nova. Ele escolhe **uma** das intenções abaixo pela descrição. A escolha define o agente que responde e o funil onde o card nasce. Se nenhuma intenção servir, a conversa vai para o agente padrão (SDR de Chalés).

| Intenção | Descrição usada pelo roteador | Agente |
|---|---|---|
| Novo interessado em Steel Frame | Pessoa que ainda não é cliente e quer saber sobre chalé, bangalô, loft ou outro projeto em Steel Frame: pede informação, orçamento, proposta, reunião ou avaliação do projeto. | SDR LSF (funil Chalés LSF) |
| Empresa buscando consultoria ou assessoria | Dono, gestor ou representante de uma empresa que quer consultoria ou assessoria para o próprio negócio: melhorar vendas, atendimento, processo comercial, marketing, tráfego, CRM ou uso de IA e automação. Não é projeto de construção em Steel Frame. | Consultoria e Assessoria (funil Consultoria e Assessoria) |
| Cliente com projeto em andamento | Cliente que já tem projeto ou contrato com a Leadframe e fala de andamento, entrega, solicitação, reclamação ou nova demanda sobre o que já contratou. | Atendimento e Pós-venda |
| Assunto financeiro | Qualquer assunto de pagamento: pagamento já feito, segunda via, boleto, nota fiscal, divergência de valor, cobrança, comprovante, parcelamento ou desconto. | Financeiro (triagem) |
| Suporte de uso e dúvida técnica | Dificuldade para abrir ou usar um arquivo, link ou material enviado pela equipe, ou dúvida técnica e problema da obra. Inclui relato de risco imediato. | Suporte (triagem) |

Regras do roteador: confiança mínima para trocar de agente, conversa "grudada" no agente atual enquanto o assunto continua e, se o cliente muda de produto, um segundo card no outro funil.
