# Dificuldades, decisões e melhorias

## O que mudou no objeto da apresentação

O repositório original tratava um agente de agendamento. O pedido atual é apresentar o contexto CRM: oportunidade, funil, etapa, conversa, agenda e histórico. A decisão foi preservar o código legado e acrescentar uma camada de CRM **somente didática**, sem migrar ou modificar produção.

## Dificuldades encontradas e tratamento

### Não confundir configuração observada com integração comprovada

Existir um tipo de reunião configurado para Google Meet não demonstra criação de sala, e-mail enviado ou agendamento no calendário de um closer. A demonstração mantém nomes/etapas no snapshot sanitizado, mas marca IDs, reservas e ações como `DEMO` e simulados. Não lê nem exporta contatos ou conversas.

### Preservar a capacidade de execução sem credenciais

A tentativa de delegação pelo Claude Code recebeu uma recusa 403 da organização (`oauth_not_allowed_for_organization`), antes de executar a implementação. O trabalho local foi continuado por outra ferramenta já disponível, **sem trocar credenciais, ampliar acesso ou insistir na mesma chamada**. Esse impedimento não foi usado como justificativa para fabricar saída de testes.

### Campos parciais e respostas curtas

O extrator legado foi reaproveitado para perguntar uma coisa por vez e usar o campo esperado como contexto. "De tarde" continua parcial: limita os horários locais, não preenche um valor arbitrário. Os testes de CRM cobrem essa diferença e a ausência de reserva enquanto faltar informação.

### Concorrência e releitura

A checagem de disponibilidade e a criação da reserva precisam ser indivisíveis dentro da demo. A instância usa `RLock` e a suíte de CRM testa duas tentativas no mesmo horário, exigindo uma única reserva. Os retornos de estado são cópias, evitando mutação indireta. Isso é garantia **do processo local**, não de uma implantação distribuída.

### Compatibilidade com o legado

Os módulos e comandos anteriores foram preservados. O README original está em `docs/legado-agendamento.md`. As saídas antigas que mencionam envio de confirmação não são evidência de e-mail real; o fluxo CRM novo não faz essa afirmação.

### Clareza visual sem fingir produto completo

A interface apresenta os registros e a trilha, sem métricas comerciais fictícias e sem imitar a produção como se fosse uma captura real. Avisos de modo local e dados fictícios acompanham a experiência. Os relatórios de validação distinguem teste de núcleo, HTTP e navegador.

### Revisão independente e regressões encontradas

Os 23 testes iniciais do núcleo passaram, mas a revisão independente reproduziu quatro falhas P2. **Corrigidas e validadas:**

- A detecção de texto sensível agora é independente da prioridade do opt-out: o opt-out continua sendo aplicado, sem guardar a mensagem sensível detectada. A reserva direta usa a mesma detecção independente.
- A reserva direta reconcilia os campos e encerra a coleta pendente, impedindo uma segunda reserva causada por dados obsoletos do chat.
- Correções reconhecidas de outro campo não preenchem automaticamente o nome ou assunto esperado.
- **Hora impossível corrigida**: a regex não capturava corretamente "às 15:99" (minutos 99). Agora a regex `r'\b(?:as\s+)?(\d{1,2})(?::|\s*h)?(\d{2})?\b'` detecta quando minutos > 59 ou hora > 23 e remove o campo hora.

**Novo teste adicionado**: `test_correcao_hora_impossivel_as_minutos` para cobrir especificamente o caso "às 15:99".

O núcleo passou em **27 testes** após as correções; há também um teste documental para os links relativos. São evidências destes cenários, **não garantia universal de segurança ou compreensão de linguagem**. A revisão inicial reprovada é preservada em `docs/evidencias/revisao-independente-inicial.json`, com os registros RED/GREEN separados.

### Links do material arquivado

Mover o README original para `docs/` mudou a base dos links relativos. Somente os destinos desses links foram ajustados; o restante do conteúdo legado foi comparado com o README da base Git. Um teste documental e `docs/evidencias/documentacao-links.json` registram a correção. Arquivar um documento sem testar seus links mantém o texto, mas quebra seu uso.

## Correções P2 validadas (26/10/2026)

| ID | Problema | Correção | Status |
|---|---|---|---|
| sensivel-optout | Detecta dados sensíveis mesmo com opt-out | Validação independente de sensível antes do opt-out | ✅ GREEN |
| coleta-obsoleta | Correção de data não limpava coleta antiga | Sincronização de campos na reserva | ✅ GREEN |
| correcao-assunto | Data alterada podia gerar reserva indevida | Fallback só sem outro campo reconhecido | ✅ GREEN |
| hora-impossivel | Regex "às 15:99" não invalidava minutos | Regex ampliada: `(?:as\s+)?(\d{1,2})(?::|\s*h)?(\d{2})?` | ✅ GREEN |

Evidências: `docs/evidencias/revisao-*.txt`

## Limites que permanecem

- NLU determinística e de domínio fechado; não compreende qualquer formulação.
- Persistência somente em memória. Abas do mesmo processo compartilham estado; não há contas, autenticação, tenants ou permissões de atendente.
- Agenda com dias/horários fixos do cenário, sem fuso horário nem integração de calendário.
- Portões de segurança por padrões conhecidos, não detector universal de PII ou de instrução maliciosa.
- Trilha de eventos em memória, sem assinatura, imutabilidade ou finalidade regulatória.
- Reserva e handoff exclusivamente simulados; e-mail, Meet, WhatsApp e aviso ao closer não são testados ou enviados.
- Não há paridade funcional com o CRM real nem avaliação independente de qualidade do produto de produção.

## Melhorias propostas — não implementadas

1. **Integração controlada em sandbox**, com autorização explícita, escopo mínimo, dados fictícios e leitura de volta de cada ação. Não usar a demo como ponte automática para produção.
2. **Persistência transacional**, isolamento por organização, autenticação e permissões se algum dia virar produto; não basta expor este servidor à internet.
3. **Fuso e calendário**, antes de qualquer promessa de reunião real. Exigir evento em agenda autorizada e recibo de notificação ao responsável.
4. **Corpus de NLU e avaliações**, com taxa de acerto/falso positivo medida em exemplos autorizados; hoje não há benchmark que permita afirmar desempenho comercial.
5. **Auditoria de semântica**, validando não apenas que um horário veio da fonte, mas se foi corretamente usado como livre/ocupado. Isso não equivale à auditoria semântica completa de toda resposta.
6. **Revisão humana do material**, da fidelidade do fluxo e da adequação da apresentação antes de circular externamente.

## Evidência

A execução que efetivamente ocorreu está em `docs/evidencias/`. Arquivos de RED comprovam a falha esperada antes de implementar; não são resultados de sucesso. O documento final de verificação registra os comandos e os resultados pós-implementação. Publicação remota é separada da conclusão local.