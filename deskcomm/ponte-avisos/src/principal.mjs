/**
 * PONTO DE ENTRADA DA PONTE DE AVISOS.
 *
 *   node --env-file=.env src/principal.mjs            roda em laço (o que o Docker faz)
 *   node --env-file=.env src/principal.mjs --uma-vez  um ciclo só, e sai
 *   node --env-file=.env src/principal.mjs --previa   lê o banco e IMPRIME os avisos
 *                                                     da janela; não envia, não grava
 *
 * ⚠️ `--previa` imprime nome, telefone e resumo de clientes reais na tela. É para
 * o operador conferir o formato, no terminal — não redirecione para arquivo.
 */
import { setTimeout as esperar } from "node:timers/promises";

import { PASSAGENS, REUNIOES, rodarCiclo } from "./ciclo.mjs";
import { lerConfig, ErroDeConfiguracao } from "./config.mjs";
import { carregarEstado, registrarBatimento, salvarEstado } from "./estado.mjs";
import { criarFontePostgres } from "./fonte-postgres.mjs";
import { criarLog, resumoDoErro } from "./log.mjs";
import { criarEnviadorMeta } from "./meta.mjs";
import { MODELO } from "./modelo.mjs";

const log = criarLog();
const args = new Set(process.argv.slice(2));

let config;
try {
  config = lerConfig(process.env);
} catch (erro) {
  if (erro instanceof ErroDeConfiguracao) {
    log.erro("configuracao_invalida", { problemas: erro.problemas });
    process.exit(2);
  }
  throw erro;
}

const fonte = criarFontePostgres({ db: config.db, orgId: config.orgId });

async function previa() {
  const desde = new Date(Date.now() - config.idadeMaximaMs);
  const minutos = config.idadeMaximaMs / 60000;
  const tipos = config.reunioes ? [PASSAGENS, REUNIOES] : [PASSAGENS];
  for (const tipo of tipos) {
    const linhas = await tipo.ler(fonte, desde, 20);
    if (linhas.length === 0) console.log(`Nenhum evento de ${tipo.colecao} nos últimos ${minutos} minutos.`);
    for (const l of linhas) {
      const aviso = tipo.montar(l);
      console.log(`\n──── ${tipo.nome} ${tipo.id(l)} (${l.criado_em}) ────`);
      console.log(aviso.texto);
      console.log(`[${tipo.modelo.botao.texto}] ${aviso.link}`);
      console.log(`(${aviso.texto.length}/${tipo.modelo.limiteDoCorpo} caracteres)`);
    }
  }
}

async function laco() {
  const estado = await carregarEstado(config.dirEstado, new Date(), log);
  const enviador =
    config.modo === "envio"
      ? criarEnviadorMeta({
          versao: config.meta.versao,
          phoneNumberId: config.meta.phoneNumberId,
          token: config.meta.token,
          destino: config.destino,
          template: MODELO.nome,
          idioma: MODELO.idioma,
        })
      : null;
  const salvar = (e) => salvarEstado(config.dirEstado, e);

  let parar = false;
  const pararComCalma = () => {
    parar = true;
  };
  process.on("SIGTERM", pararComCalma);
  process.on("SIGINT", pararComCalma);

  log.info("ponte_iniciada", {
    modo: config.modo,
    reunioes: config.reunioes ? "ligado" : "desligado",
    intervalo_s: config.intervaloMs / 1000,
    idade_maxima_min: config.idadeMaximaMs / 60000,
    marco_zero: estado.inicio,
  });

  // Passagem primeiro: cliente esperando uma pessoa é mais urgente que reunião marcada.
  const tipos = config.reunioes ? [PASSAGENS, REUNIOES] : [PASSAGENS];
  while (!parar) {
    // Um tipo que falha não impede o outro; o batimento só sai se TODOS fecharam
    // o ciclo sem erro de configuração nem exceção.
    let saudavel = true;
    for (const tipo of tipos) {
      try {
        const resumo = await rodarCiclo({
          fonte,
          enviador,
          estado,
          config,
          log,
          salvar,
          dormir: (ms) => esperar(ms),
          tipo,
        });
        if (resumo.interrompido === "configuracao") saudavel = false;
        if (resumo.enviadas || resumo.simuladas || resumo.falhas || resumo.pendentes || resumo.interrompido) {
          log.info("ciclo", resumo);
        }
      } catch (erro) {
        saudavel = false;
        log.erro("ciclo_falhou", { tipo: tipo.nome, ...resumoDoErro(erro) });
      }
    }
    if (saudavel) await registrarBatimento(config.dirEstado, new Date());
    if (args.has("--uma-vez")) break;
    for (let passado = 0; passado < config.intervaloMs && !parar; passado += 1000) await esperar(1000);
  }
  log.info("ponte_parada");
}

try {
  if (args.has("--previa")) await previa();
  else await laco();
} finally {
  await fonte.encerrar();
}
