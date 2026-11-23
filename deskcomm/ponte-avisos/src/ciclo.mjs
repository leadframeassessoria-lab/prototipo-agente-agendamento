/**
 * UM CICLO DA PONTE: lê os eventos recentes de UM tipo (passagens para humano ou
 * reuniões marcadas pela IA), decide quais avisar, avisa.
 *
 * Tudo que fala com o mundo entra por parâmetro (fonte, enviador, relógio,
 * espera, gravação), e é isso que deixa o ciclo inteiro testável sem banco e
 * sem Meta (`teste/ciclo.test.mjs`).
 *
 * ## Sem cursor, de propósito
 *
 * Cada ciclo relê a janela inteira (idade máxima + 10 min) e o estado diz o que
 * já foi tratado. Um cursor "último evento visto" erra de dois jeitos que esta
 * forma não erra: o evento gravado numa transação que demorou a confirmar chega
 * com horário ANTERIOR ao cursor e nunca é lido; e o evento pendente (Meta fora
 * do ar) fica para trás quando o cursor anda. O volume é de poucos eventos por
 * hora — reler a janela não custa nada.
 *
 * ## A ordem das perguntas
 *
 * 1. já tratado? → pula (é o que impede aviso repetido)
 * 2. velho demais? → ignora (aviso de uma hora atrás é ruído, não ajuda)
 * 3. o tipo manda descartar? → ignora (passagem que alguém já assumiu, reunião
 *    cancelada antes do aviso)
 * 4. só passagens: a mesma conversa já foi avisada há pouco? → ignora (o cliente
 *    que pede humano três vezes seguidas gera três passagens; o Bruno precisa de
 *    um aviso)
 * 5. monta, espaça, envia.
 *
 * ## Quando o ciclo para no meio
 *
 * Erro temporário ou de configuração interrompe o ciclo e deixa o evento
 * PENDENTE: os outros da fila iriam para o mesmo destino pelo mesmo caminho e
 * bateriam no mesmo erro. Só o erro de configuração não conta tentativa — a
 * culpa não é do evento, e ele não pode morrer por isso.
 */
import { podarEstado } from "./estado.mjs";
import { montarAviso, montarAvisoReuniao } from "./mensagem.mjs";
import { MODELO, MODELO_REUNIAO } from "./modelo.mjs";

const MARGEM_DA_JANELA_MS = 10 * 60 * 1000;
const LIMITE_DA_LEITURA = 100;

/** O que muda de um tipo de aviso para outro. O resto do ciclo é o mesmo. */
export const PASSAGENS = Object.freeze({
  nome: "passagem",
  colecao: "passagens",
  ler: (fonte, desde, limite) => fonte.passagensDesde(desde, limite),
  id: (l) => l.passagem_id,
  descartar: (l) => (l.reconhecido_em ? "ja_assumida" : null),
  reavisoPorConversa: true,
  montar: montarAviso,
  modelo: MODELO,
  motivo: (l) => l.motivo_codigo,
});

/**
 * Reunião não usa o reaviso por conversa, nem conta para ele: o cliente que
 * marca e logo depois pede uma pessoa precisa gerar os DOIS avisos.
 */
export const REUNIOES = Object.freeze({
  nome: "reuniao",
  colecao: "reunioes",
  ler: (fonte, desde, limite) => fonte.reunioesDesde(desde, limite),
  id: (l) => l.reuniao_id,
  descartar: (l) => (l.situacao === "cancelled" ? "cancelada" : null),
  reavisoPorConversa: false,
  montar: montarAvisoReuniao,
  modelo: MODELO_REUNIAO,
  motivo: () => "reuniao_marcada",
});

export async function rodarCiclo({
  fonte,
  enviador,
  estado,
  config,
  log,
  salvar,
  dormir,
  relogio = () => new Date(),
  tipo = PASSAGENS,
}) {
  const agora = relogio();
  const tratados = (estado[tipo.colecao] ??= {});
  // O marco zero das passagens é o da ponte; o de outro tipo nasce no primeiro
  // ciclo dele, para que ligá-lo depois não avise o que aconteceu antes.
  const inicio = tipo === PASSAGENS ? estado.inicio : ((estado.marcos ??= {})[tipo.colecao] ??= agora.toISOString());
  const inicioMs = Date.parse(inicio);
  const janelaMs = config.idadeMaximaMs + MARGEM_DA_JANELA_MS;
  const desde = new Date(Math.max(agora.getTime() - janelaMs, inicioMs));

  const linhas = await tipo.ler(fonte, desde, LIMITE_DA_LEITURA);
  const resumo = {
    tipo: tipo.nome,
    lidas: linhas.length,
    enviadas: 0,
    simuladas: 0,
    ignoradas: 0,
    falhas: 0,
    pendentes: 0,
    interrompido: null,
  };

  const marcar = (id, situacao, extra = {}) => {
    tratados[id] = { ...tratados[id], ...extra, situacao, em: relogio().toISOString() };
  };
  const ignorar = (l, motivo) => {
    marcar(tipo.id(l), "ignorado", { motivo });
    resumo.ignoradas++;
    log.info("aviso_ignorado", { [tipo.nome]: tipo.id(l), conversa: l.conversation_id, motivo });
  };

  for (const l of linhas) {
    const id = tipo.id(l);
    const criadoMs = Date.parse(l.criado_em);
    if (!(criadoMs >= inicioMs)) continue;

    const registro = tratados[id];
    if (registro && registro.situacao !== "pendente") continue;

    const agoraMs = relogio().getTime();
    if (agoraMs - criadoMs > config.idadeMaximaMs) {
      ignorar(l, "velha");
      continue;
    }
    const descarte = tipo.descartar(l);
    if (descarte) {
      ignorar(l, descarte);
      continue;
    }
    const ultimoAviso = estado.conversas[l.conversation_id];
    if (
      tipo.reavisoPorConversa &&
      config.reavisoMs > 0 &&
      ultimoAviso &&
      agoraMs - Date.parse(ultimoAviso) < config.reavisoMs
    ) {
      ignorar(l, "conversa_avisada_ha_pouco");
      continue;
    }

    let aviso;
    try {
      aviso = tipo.montar(l);
    } catch (erro) {
      marcar(id, "falhou", { motivo: erro?.codigo ?? "montagem" });
      resumo.falhas++;
      log.erro("aviso_nao_montado", {
        [tipo.nome]: id,
        conversa: l.conversation_id,
        motivo: erro?.codigo ?? "montagem",
      });
      continue;
    }

    if (config.modo === "teste") {
      marcar(id, "simulado");
      if (tipo.reavisoPorConversa) estado.conversas[l.conversation_id] = relogio().toISOString();
      resumo.simuladas++;
      log.info("aviso_simulado", {
        [tipo.nome]: id,
        conversa: l.conversation_id,
        motivo: tipo.motivo(l),
        caracteres: aviso.texto.length,
      });
      await salvar(estado);
      continue;
    }

    if (estado.ultimoEnvioEm) {
      const espera = config.espacamentoMs - (relogio().getTime() - Date.parse(estado.ultimoEnvioEm));
      if (espera > 0) await dormir(espera);
    }

    const r = await enviador.enviarAviso({
      parametros: aviso.parametros,
      sufixoUrl: aviso.sufixoUrl,
      modelo: tipo.modelo,
    });
    estado.ultimoEnvioEm = relogio().toISOString();
    const tentativas = (registro?.tentativas ?? 0) + 1;

    if (r.ok) {
      marcar(id, "enviado", { tentativas, wamid: r.wamid });
      if (tipo.reavisoPorConversa) estado.conversas[l.conversation_id] = relogio().toISOString();
      resumo.enviadas++;
      log.info("aviso_enviado", {
        [tipo.nome]: id,
        conversa: l.conversation_id,
        motivo: tipo.motivo(l),
        wamid: r.wamid,
      });
      await salvar(estado);
      continue;
    }

    const falha = { codigo: r.codigo, status: r.status, detalhe: r.detalhe, fbtrace: r.fbtrace ?? null };
    if (r.tipo === "configuracao") {
      marcar(id, "pendente", { tentativas: registro?.tentativas ?? 0, ultimoErro: r.codigo });
      resumo.pendentes++;
      resumo.interrompido = "configuracao";
      log.erro("envio_bloqueado_por_configuracao", { [tipo.nome]: id, ...falha });
      await salvar(estado);
      break;
    }
    if (r.tipo === "temporaria") {
      if (tentativas >= config.maxTentativas) {
        marcar(id, "falhou", { tentativas, ultimoErro: r.codigo });
        resumo.falhas++;
        log.erro("aviso_desistido", { [tipo.nome]: id, tentativas, ...falha });
      } else {
        marcar(id, "pendente", { tentativas, ultimoErro: r.codigo });
        resumo.pendentes++;
        log.aviso("aviso_adiado", { [tipo.nome]: id, tentativas, ...falha });
      }
      resumo.interrompido = "temporaria";
      await salvar(estado);
      break;
    }
    marcar(id, "falhou", { tentativas, ultimoErro: r.codigo });
    resumo.falhas++;
    log.erro("aviso_recusado", { [tipo.nome]: id, ...falha });
    await salvar(estado);
  }

  podarEstado(estado, agora, Math.max(2 * janelaMs, 24 * 60 * 60 * 1000));
  await salvar(estado);
  return resumo;
}
