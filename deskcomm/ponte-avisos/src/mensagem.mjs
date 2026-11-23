/**
 * A MENSAGEM DO AVISO — pura: sem banco, sem rede, sem relógio.
 *
 * Recebe uma passagem (ou uma reunião) como a função de leitura do Supabase a
 * devolve e monta os parâmetros do modelo, o sufixo do link e o texto final
 * (para a prévia).
 *
 * Três regras que valem para todo parâmetro, e o porquê de cada uma:
 *
 * 1. **Uma linha só.** A Meta recusa parâmetro com quebra de linha, tabulação ou
 *    mais de quatro espaços seguidos. Tudo vira espaço simples.
 * 2. **Sem link.** Resumo e falas vêm do cliente ou do modelo. Um link de golpe
 *    escrito pelo cliente chegaria ao Bruno pelo número oficial da própria
 *    Leadframe — e mensagem do próprio número é a que menos se desconfia. O
 *    único link da mensagem é o botão.
 * 3. **Sem sequência longa de dígitos nos textos livres.** CPF, cartão ou
 *    telefone que o cliente digitou não precisam sair do CRM. O telefone do
 *    cliente tem lugar próprio ({{2}}) e vem do cadastro, não do texto.
 *
 * O corpo inteiro precisa caber em 1.024 caracteres. Quem cede espaço é o
 * resumo, porque o link leva à conversa completa.
 */
import { MODELO, MODELO_REUNIAO } from "./modelo.mjs";

/** As frases do Deskcomm (`lib/escalacao/passagem.ts`, FRASE_DO_MOTIVO), v1.73.0. */
export const FRASE_DO_MOTIVO = Object.freeze({
  requested_human: "O cliente pediu para falar com uma pessoa",
  suspected_optout: "O cliente parece ter pedido para não receber mais mensagens",
  orcamento_de_ia: "O limite de gasto com IA foi atingido (o cliente não pediu uma pessoa)",
  low_sentiment: "O cliente demonstrou irritação na conversa",
  low_confidence: "O assistente não teve confiança suficiente para responder",
  critical_stage: "O negócio chegou a uma etapa que pede uma pessoa",
  legal_mention: "A conversa tocou em assunto jurídico",
  refund_mention: "A conversa tocou em reembolso",
  caso_escalado: "Uma pessoa da equipe escalou um atendimento",
});

/** O resumo que o Deskcomm grava quando não há contexto nenhum. */
export const PISO_DO_BRIEFING =
  "Sem resumo acumulado ainda (conversa recente) — abra a conversa no CRM para o contexto completo.";

/**
 * Blocos do resumo da passagem que JÁ têm parâmetro próprio no aviso. Repeti-los
 * no resumo gastaria o espaço que falta para o que só o resumo traz.
 */
const BLOCOS_REPETIDOS = [
  "Por que a IA passou:",
  "O que o cliente quer (segundo a IA — confira):",
  "Últimas mensagens do cliente (palavras dele):",
];
const ROTULO_DO_CONTEXTO = "Contexto acumulado (segundo a IA — confira):";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const LINK = /\b(?:https?:\/\/|www\.)\S+/giu;
const DOMINIO =
  /\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|org|br|io|app|me|ly|xyz|info|site|online|link|shop|store|co)(?:\.[a-z]{2})?(?:\/\S*)?/giu;
const NUMERO_LONGO = /\+?\d[\d\s().\-/]{6,}\d/g;
const EMAIL = /[a-z0-9._%+-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+/giu;
/** Marcadores da área de uso privado: não existem em texto de cliente e não são controle. */
const GUARDA_ABRE = String.fromCharCode(0xe000);
const GUARDA_FECHA = String.fromCharCode(0xe001);
const GUARDADO = new RegExp(`${GUARDA_ABRE}(\\d+)${GUARDA_FECHA}`, "g");
/**
 * Troca por espaço os caracteres de controle (C0, DEL, C1) e os dois separadores
 * de linha Unicode (U+2028/U+2029). Função e não expressão regular: os
 * separadores, escritos crus num literal, quebram o próprio literal.
 */
function semControles(texto) {
  let saida = "";
  for (const ch of texto) {
    const c = ch.codePointAt(0);
    const controle = c < 0x20 || (c >= 0x7f && c <= 0x9f) || c === 0x2028 || c === 0x2029;
    saida += controle ? " " : ch;
  }
  return saida;
}

export class ErroDeAviso extends Error {
  constructor(codigo) {
    super(codigo);
    this.name = "ErroDeAviso";
    this.codigo = codigo;
  }
}

/**
 * Corta em `max` unidades de UTF-16 (a medida mais conservadora do limite da
 * Meta) sem partir emoji ao meio, e sinaliza o corte com reticências.
 */
export function truncar(texto, max) {
  if (texto.length <= max) return texto;
  let saida = "";
  for (const ch of texto) {
    if (saida.length + ch.length > max - 1) break;
    saida += ch;
  }
  return saida.trimEnd() + "…";
}

/**
 * Limpa um texto livre para virar parâmetro. `null` quando nada sobra — nunca
 * string vazia, que a Meta recusa.
 */
export function limparTexto(bruto, max, { mascararNumeros = true, manterEmails = false } = {}) {
  if (typeof bruto !== "string") return null;
  let t = semControles(bruto);
  // O e-mail que o cliente deu é o que o Bruno precisa conferir (um "@gmai.com"
  // sem convite do Google). Sem esta guarda, o domínio dele viraria "[link removido]".
  const emails = [];
  if (manterEmails) {
    t = t.replace(EMAIL, (e) => `${GUARDA_ABRE}${emails.push(e) - 1}${GUARDA_FECHA}`);
  }
  t = t.replace(LINK, "[link removido]").replace(DOMINIO, "[link removido]");
  if (manterEmails) t = t.replace(GUARDADO, (_, i) => emails[Number(i)]);
  if (mascararNumeros) {
    t = t.replace(NUMERO_LONGO, (trecho) =>
      trecho.replace(/\D/g, "").length >= 8 ? "[número removido]" : trecho,
    );
  }
  t = t.replace(/\s+/gu, " ").trim();
  if (t === "") return null;
  return truncar(t, max);
}

/** `+5500999990001` → `+55 00 99999-0001`. Fora do Brasil, `+` e dígitos. */
export function formatarTelefone(bruto) {
  if (typeof bruto !== "string") return null;
  const d = bruto.replace(/\D/g, "");
  if (d.length < 8) return null;
  if (d.startsWith("55") && d.length === 13) return `+55 ${d.slice(2, 4)} ${d.slice(4, 9)}-${d.slice(9)}`;
  if (d.startsWith("55") && d.length === 12) return `+55 ${d.slice(2, 4)} ${d.slice(4, 8)}-${d.slice(8)}`;
  return `+${d}`;
}

/**
 * Tira do resumo da passagem os blocos que já têm parâmetro e junta o resto numa
 * linha. Linha desconhecida FICA: um bloco novo do Deskcomm aparece no aviso em
 * vez de sumir.
 */
export function extrairResumo(body) {
  if (typeof body !== "string") return null;
  if (body.trim() === PISO_DO_BRIEFING) return null;
  let saida = "";
  for (const crua of body.split(/\r?\n/)) {
    let linha = crua.trim();
    if (linha === "") continue;
    if (BLOCOS_REPETIDOS.some((r) => linha.startsWith(r))) continue;
    if (linha.startsWith(ROTULO_DO_CONTEXTO)) {
      linha = linha.slice(ROTULO_DO_CONTEXTO.length).trim();
      if (linha === "") continue;
    }
    linha = linha.replace(/^[-•*]\s+/, "");
    if (saida === "") saida = linha;
    else saida += saida.endsWith(":") ? ` ${linha}` : ` · ${linha}`;
  }
  return saida === "" ? null : saida;
}

/**
 * As últimas falas do cliente chegam uma por linha. Juntadas só com espaço,
 * duas mensagens viram uma frase que ninguém disse; " / " mantém a fronteira.
 */
function separarFalas(notes) {
  if (typeof notes !== "string") return notes;
  return notes
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean)
    .join(" / ");
}

/** O corpo do modelo com os parâmetros no lugar — o que o Bruno lê. */
export function renderizar(parametros, modelo = MODELO) {
  return modelo.corpo.replace(/\{\{(\d+)\}\}/g, (_, n) => parametros[Number(n) - 1] ?? "");
}

const TAMANHO_FIXO = MODELO.corpo.replace(/\{\{\d+\}\}/g, "").length;
/** Folga para diferenças de contagem entre nós e a Meta. */
const FOLGA = 24;

/**
 * Monta o aviso de uma passagem.
 *
 * @param {object} p linha de `leadframe_ponte.passagens_para_avisar`
 * @returns {{ parametros: string[], sufixoUrl: string, texto: string, link: string }}
 */
export function montarAviso(p) {
  const conversa = String(p?.conversation_id ?? "");
  // O sufixo vira URL no botão: só um uuid passa, nada que mude o caminho.
  if (!UUID.test(conversa)) throw new ErroDeAviso("conversa_invalida");

  const nome = limparTexto(p.contato_nome, 60) ?? "Sem nome cadastrado";
  const telefone = formatarTelefone(p.contato_telefone) ?? "Não cadastrado";
  const motivo = FRASE_DO_MOTIVO[p.motivo_codigo] ?? "Motivo não identificado pelo sistema";
  const resumoBruto = extrairResumo(p.resumo);

  let tetoDasFalas = 200;
  let quer;
  let ultima;
  let espaco;
  for (;;) {
    quer = limparTexto(p.o_que_quer, tetoDasFalas) ?? "Não registrado pela IA";
    ultima = limparTexto(separarFalas(p.ultimas_palavras), tetoDasFalas) ?? "Não registrada";
    espaco =
      MODELO.limiteDoCorpo -
      FOLGA -
      TAMANHO_FIXO -
      nome.length -
      telefone.length -
      motivo.length -
      quer.length -
      ultima.length;
    if (espaco >= 150 || tetoDasFalas <= 100) break;
    tetoDasFalas = 100;
  }
  const resumo =
    limparTexto(resumoBruto, Math.max(espaco, 40)) ?? "Sem resumo ainda; abra a conversa no CRM";

  const parametros = [nome, telefone, motivo, quer, resumo, ultima];
  const texto = renderizar(parametros);
  if (texto.length > MODELO.limiteDoCorpo) throw new ErroDeAviso("corpo_grande_demais");
  return { parametros, sufixoUrl: conversa, texto, link: MODELO.botao.urlBase + conversa };
}

/**
 * "quarta-feira, 07/10 às 9h30" no fuso em que a reunião foi MARCADA — o
 * instante UTC sozinho erraria a hora que o cliente combinou. `null` se o
 * horário ou o fuso não prestam.
 */
export function formatarQuando(inicio, fuso) {
  const instante = new Date(inicio);
  if (Number.isNaN(instante.getTime())) return null;
  let partes;
  try {
    partes = new Intl.DateTimeFormat("pt-BR", {
      timeZone: fuso || "America/Sao_Paulo",
      weekday: "long",
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).formatToParts(instante);
  } catch {
    return null;
  }
  const v = Object.fromEntries(partes.map((p) => [p.type, p.value]));
  const hora = `${Number(v.hour)}h${v.minute === "00" ? "" : v.minute}`;
  return `${v.weekday}, ${v.day}/${v.month} às ${hora}`;
}

const TAMANHO_FIXO_REUNIAO = MODELO_REUNIAO.corpo.replace(/\{\{\d+\}\}/g, "").length;

/**
 * Monta o aviso de uma reunião marcada pela IA.
 *
 * @param {object} r linha de `leadframe_ponte.reunioes_para_avisar`
 * @returns {{ parametros: string[], sufixoUrl: string, texto: string, link: string }}
 */
export function montarAvisoReuniao(r) {
  const conversa = String(r?.conversation_id ?? "");
  if (!UUID.test(conversa)) throw new ErroDeAviso("conversa_invalida");

  const quando = formatarQuando(r.inicia_em, r.fuso);
  if (!quando) throw new ErroDeAviso("horario_invalido");
  const nome = limparTexto(r.contato_nome, 60) ?? "Sem nome cadastrado";
  const telefone = formatarTelefone(r.contato_telefone) ?? "Não cadastrado";
  const assunto = limparTexto(r.titulo, 120) ?? "Reunião";
  const espaco =
    MODELO_REUNIAO.limiteDoCorpo - FOLGA - TAMANHO_FIXO_REUNIAO - nome.length - telefone.length - quando.length - assunto.length;
  const resumo =
    limparTexto(r.notas, Math.max(espaco, 40), { manterEmails: true }) ?? "Sem resumo; abra a conversa no CRM";

  const parametros = [nome, telefone, quando, assunto, resumo];
  const texto = renderizar(parametros, MODELO_REUNIAO);
  if (texto.length > MODELO_REUNIAO.limiteDoCorpo) throw new ErroDeAviso("corpo_grande_demais");
  return { parametros, sufixoUrl: conversa, texto, link: MODELO_REUNIAO.botao.urlBase + conversa };
}
