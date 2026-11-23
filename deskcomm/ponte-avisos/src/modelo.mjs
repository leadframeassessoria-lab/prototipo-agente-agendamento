/**
 * O MODELO (TEMPLATE) DA META — espelho do que foi enviado para análise.
 *
 * Enviado em 2026-10-05 na conta do WhatsApp "Leadframe Consultoria e
 * Assessoria" (WABA 100000000000001), categoria Utilidade, Português (BR),
 * validade de 12 horas. Registro completo em `meta/modelo-aviso_passagem_humano.md`.
 *
 * O envio só manda os PARÂMETROS; quem guarda o texto é a Meta. O corpo fica
 * aqui por dois motivos: a prévia mostra exatamente o que o Bruno vai ler, e o
 * limite de 1.024 caracteres da Meta vale para o corpo JÁ preenchido — sem o
 * texto fixo não dá para saber quanto sobra para o resumo.
 *
 * Mudou o texto na Meta? Muda aqui também — `teste/estado-config-modelo.test.mjs`
 * trava a forma (variáveis em ordem) para o descompasso não passar calado.
 */
export const MODELO = Object.freeze({
  nome: "aviso_passagem_humano",
  idioma: "pt_BR",
  corpo:
    "🔔 Atendimento para você assumir\n" +
    "\n" +
    "Cliente: {{1}}\n" +
    "Telefone: {{2}}\n" +
    "Motivo: {{3}}\n" +
    "O que o cliente quer: {{4}}\n" +
    "Resumo da conversa: {{5}}\n" +
    "Última mensagem do cliente: {{6}}\n" +
    "\n" +
    "A IA já parou de responder esse cliente. Responder aqui não chega ao cliente: use o botão abaixo.",
  botao: Object.freeze({
    texto: "Abrir conversa",
    /** O sufixo dinâmico ({{1}} do botão) é o id da conversa no Deskcomm. */
    urlBase: "https://crm.exemplo.com.br/app/inbox/",
  }),
  /** Limite da Meta para o corpo preenchido. */
  limiteDoCorpo: 1024,
});

/**
 * O SEGUNDO MODELO — reunião marcada pela IA. Texto aprovado pelo operador em
 * 2026-10-05 (noite); registro do envio à Meta em `meta/modelo-aviso_reuniao_marcada.md`.
 * Mesmo botão do primeiro: abre a conversa no Deskcomm.
 */
export const MODELO_REUNIAO = Object.freeze({
  nome: "aviso_reuniao_marcada",
  idioma: "pt_BR",
  corpo:
    "📅 Reunião marcada pela IA\n" +
    "\n" +
    "Cliente: {{1}}\n" +
    "Telefone: {{2}}\n" +
    "Quando: {{3}}\n" +
    "Assunto: {{4}}\n" +
    "Resumo da conversa: {{5}}\n" +
    "\n" +
    "O compromisso já está na sua agenda Google, com o link do Meet.",
  botao: MODELO.botao,
  limiteDoCorpo: 1024,
});
