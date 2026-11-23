/**
 * O ENVIO PELA API OFICIAL DO WHATSAPP (Cloud API da Meta).
 *
 * Um método só, `enviarAviso`, que NUNCA lança: todo desfecho volta como valor,
 * porque quem chama precisa decidir entre três caminhos bem diferentes:
 *
 * - `temporaria` — rede, limite de ritmo, Meta instável. Tenta de novo no
 *   próximo ciclo, contando tentativa.
 * - `configuracao` — token vencido, modelo inexistente ou pausado, número fora
 *   da lista permitida. Nenhum aviso vai sair até alguém consertar; insistir só
 *   gasta tentativas de passagens que não têm culpa. Quem chama para o ciclo e
 *   deixa a passagem pendente.
 * - `permanente` — o problema é DESTE aviso (parâmetro recusado, destinatário
 *   que não recebe). Marca falha e segue para o próximo.
 *
 * O token só vive no cabeçalho. Nenhuma mensagem de erro deste módulo o contém,
 * e o corpo do pedido (com nome e telefone do cliente) nunca é registrado.
 *
 * Códigos: https://developers.facebook.com/docs/whatsapp/cloud-api/support/error-codes
 */

const TEMPORARIOS = new Set([1, 2, 4, 17, 32, 341, 613, 80007, 130429, 131000, 131016, 131048, 131056, 133004]);
// 131042 = problema de pagamento da conta do WhatsApp (sem forma de pagamento
// cadastrada, ou recusada): nenhum modelo sai até alguém resolver na Meta.
const DE_CONFIGURACAO = new Set([
  0, 3, 10, 190, 200, 368, 131005, 131030, 131031, 131042, 132000, 132001, 132015, 132016, 132068, 132069,
  133010,
]);

export function classificarErro(status, codigo) {
  if (codigo !== null && TEMPORARIOS.has(codigo)) return "temporaria";
  if (codigo !== null && DE_CONFIGURACAO.has(codigo)) return "configuracao";
  if (status === 401 || status === 403) return "configuracao";
  if (status === 429 || status >= 500) return "temporaria";
  return "permanente";
}

/**
 * @param {{ versao: string, phoneNumberId: string, token: string, destino: string,
 *           template: string, idioma: string, fetchImpl?: typeof fetch, timeoutMs?: number }} opcoes
 */
export function criarEnviadorMeta({
  versao,
  phoneNumberId,
  token,
  destino,
  template,
  idioma,
  fetchImpl = globalThis.fetch,
  timeoutMs = 15_000,
}) {
  const url = `https://graph.facebook.com/${versao}/${phoneNumberId}/messages`;
  /** O texto de erro vem de fora e vai para o log: o token sai dele, se aparecer. */
  const semToken = (s) => (typeof s === "string" && token ? s.split(token).join("[token]") : s ?? null);

  /** `modelo` ({ nome, idioma }) troca o modelo só deste aviso; sem ele, vale o da criação. */
  function corpoDoPedido({ parametros, sufixoUrl, modelo }) {
    return {
      messaging_product: "whatsapp",
      recipient_type: "individual",
      to: destino,
      type: "template",
      template: {
        name: modelo?.nome ?? template,
        language: { code: modelo?.idioma ?? idioma },
        components: [
          { type: "body", parameters: parametros.map((text) => ({ type: "text", text })) },
          { type: "button", sub_type: "url", index: "0", parameters: [{ type: "text", text: sufixoUrl }] },
        ],
      },
    };
  }

  async function enviarAviso(aviso) {
    const controle = new AbortController();
    const relogio = setTimeout(() => controle.abort(), timeoutMs);
    let resposta;
    try {
      resposta = await fetchImpl(url, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(corpoDoPedido(aviso)),
        signal: controle.signal,
      });
    } catch (erro) {
      const motivo = erro?.name === "AbortError" ? "tempo_esgotado" : "rede";
      return { ok: false, tipo: "temporaria", codigo: null, status: null, detalhe: motivo };
    } finally {
      clearTimeout(relogio);
    }

    let json = null;
    try {
      json = await resposta.json();
    } catch {
      json = null;
    }

    if (resposta.ok) {
      const wamid = json?.messages?.[0]?.id ?? null;
      if (wamid) return { ok: true, wamid, situacao: json.messages[0].message_status ?? null };
      return { ok: false, tipo: "temporaria", codigo: null, status: resposta.status, detalhe: "resposta_sem_id" };
    }

    const erro = json?.error ?? {};
    const codigo = Number.isInteger(erro.code) ? erro.code : null;
    return {
      ok: false,
      tipo: classificarErro(resposta.status, codigo),
      codigo,
      status: resposta.status,
      detalhe: semToken(typeof erro.error_data?.details === "string" ? erro.error_data.details : erro.message),
      fbtrace: erro.fbtrace_id ?? null,
    };
  }

  return { enviarAviso, corpoDoPedido };
}
