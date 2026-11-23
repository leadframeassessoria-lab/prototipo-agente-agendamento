/**
 * A CONFIGURAÇÃO — lida do ambiente uma vez, validada inteira, congelada.
 *
 * Duas regras:
 *
 * - **O padrão é não enviar.** `PONTE_MODO` ausente vale `teste`: a ponte lê,
 *   monta e registra, mas não chama a Meta. Mandar de verdade exige escrever
 *   `envio` de propósito.
 * - **Erro de configuração nunca ecoa o valor.** A mensagem diz QUAL variável
 *   está errada, nunca o que estava nela — o token e a senha do banco moram
 *   nessas variáveis, e a mensagem de erro vai para o log.
 */

export class ErroDeConfiguracao extends Error {
  constructor(problemas) {
    super(`Configuração inválida:\n- ${problemas.join("\n- ")}`);
    this.name = "ErroDeConfiguracao";
    this.problemas = problemas;
  }
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function inteiro(bruto, padrao, min, max, nome, problemas) {
  if (bruto === undefined || String(bruto).trim() === "") return padrao;
  const n = Number(String(bruto).trim());
  if (!Number.isInteger(n) || n < min || n > max) {
    problemas.push(`${nome} deve ser um inteiro entre ${min} e ${max}`);
    return padrao;
  }
  return n;
}

const texto = (v) => (typeof v === "string" ? v.trim() : "");

/**
 * @param {Record<string, string|undefined>} env
 * @param {{ exigirBanco?: boolean }} opcoes `exigirBanco: false` para os scripts
 *   que não leem o Supabase (prévia local, envio de teste).
 */
export function lerConfig(env = process.env, { exigirBanco = true } = {}) {
  const problemas = [];

  const modo = texto(env.PONTE_MODO) || "teste";
  if (modo !== "teste" && modo !== "envio") problemas.push('PONTE_MODO deve ser "teste" ou "envio"');

  // Desligado por padrão: o modelo da reunião passa por análise na Meta, e ligar
  // antes da aprovação só trocaria avisos por erro 132001 no log.
  const reunioes = texto(env.PONTE_REUNIOES) || "desligado";
  if (reunioes !== "ligado" && reunioes !== "desligado") {
    problemas.push('PONTE_REUNIOES deve ser "ligado" ou "desligado"');
  }

  const orgId = texto(env.PONTE_ORG_ID);
  const dbUrl = texto(env.PONTE_DB_URL);
  const dbSsl = texto(env.PONTE_DB_SSL) || "verificar";
  const dbCaArquivo = texto(env.PONTE_DB_CA_ARQUIVO) || null;
  if (exigirBanco) {
    if (!UUID.test(orgId)) problemas.push("PONTE_ORG_ID ausente ou inválido (uuid da organização no Deskcomm)");
    if (!/^postgres(ql)?:\/\//.test(dbUrl)) problemas.push("PONTE_DB_URL ausente ou fora do formato postgresql://...");
    if (!["verificar", "sem_verificar", "desligado"].includes(dbSsl)) {
      problemas.push('PONTE_DB_SSL deve ser "verificar", "sem_verificar" ou "desligado"');
    }
  }

  const intervaloS = inteiro(env.PONTE_INTERVALO_S, 30, 10, 600, "PONTE_INTERVALO_S", problemas);
  const idadeMaximaMin = inteiro(env.PONTE_IDADE_MAXIMA_MIN, 60, 5, 720, "PONTE_IDADE_MAXIMA_MIN", problemas);
  const reavisoMin = inteiro(
    env.PONTE_REAVISO_MESMA_CONVERSA_MIN,
    30,
    0,
    1440,
    "PONTE_REAVISO_MESMA_CONVERSA_MIN",
    problemas,
  );
  const maxTentativas = inteiro(env.PONTE_MAX_TENTATIVAS, 5, 1, 20, "PONTE_MAX_TENTATIVAS", problemas);
  const espacamentoS = inteiro(env.PONTE_ESPACAMENTO_S, 7, 0, 60, "PONTE_ESPACAMENTO_S", problemas);

  const versao = texto(env.META_GRAPH_VERSION) || "v23.0";
  if (!/^v\d+\.\d+$/.test(versao)) problemas.push('META_GRAPH_VERSION deve ter a forma "v23.0"');
  const phoneNumberId = texto(env.META_PHONE_NUMBER_ID);
  const token = texto(env.META_TOKEN);
  const destino = texto(env.AVISO_DESTINO).replace(/\D/g, "");

  if (modo === "envio") {
    if (!/^\d{5,20}$/.test(phoneNumberId)) {
      problemas.push("META_PHONE_NUMBER_ID ausente ou inválido (só dígitos — o ID do número, não o telefone)");
    }
    if (token.length < 20) problemas.push("META_TOKEN ausente ou curto demais");
    if (!/^\d{10,15}$/.test(destino)) problemas.push("AVISO_DESTINO ausente ou inválido (ex.: +5500999990001)");
  }

  if (problemas.length > 0) throw new ErroDeConfiguracao(problemas);

  return Object.freeze({
    modo,
    reunioes: reunioes === "ligado",
    orgId,
    db: Object.freeze({ url: dbUrl, ssl: dbSsl, caArquivo: dbCaArquivo }),
    intervaloMs: intervaloS * 1000,
    idadeMaximaMs: idadeMaximaMin * 60 * 1000,
    reavisoMs: reavisoMin * 60 * 1000,
    maxTentativas,
    espacamentoMs: espacamentoS * 1000,
    dirEstado: texto(env.PONTE_DIR_ESTADO) || "./dados",
    meta: Object.freeze({ versao, phoneNumberId, token }),
    destino,
  });
}
