/**
 * A MEMÓRIA DA PONTE — um arquivo JSON no volume `/data`.
 *
 * Responde uma pergunta só: "esta passagem já foi tratada?". É o que impede o
 * Bruno de receber o mesmo aviso duas vezes quando a ponte reinicia.
 *
 * - **Escrita atômica.** Grava num `.tmp` e renomeia: uma queda no meio da
 *   escrita deixa o arquivo anterior inteiro, nunca meio arquivo.
 * - **`inicio` é o marco zero.** Passagem criada antes de a ponte existir não é
 *   avisada. Sem isso, o primeiro ciclo mandaria de uma vez tudo o que estivesse
 *   na janela — no celular de quem já viu aqueles atendimentos.
 * - **Arquivo corrompido não derruba a ponte.** Ele é guardado com outro nome
 *   (para alguém olhar) e a ponte recomeça com marco zero AGORA: perde-se no
 *   máximo o que caiu na janela, e nada é reenviado.
 */
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { join } from "node:path";

const ARQUIVO = "estado.json";

/**
 * `reunioes` guarda as reuniões já tratadas; `marcos` o marco zero de cada tipo
 * ligado DEPOIS da primeira subida (o de passagens é `inicio`) — ligar o aviso de
 * reunião numa ponte que já roda não pode avisar as reuniões de antes.
 */
export function estadoNovo(agora) {
  return {
    versao: 1,
    inicio: agora.toISOString(),
    ultimoEnvioEm: null,
    passagens: {},
    conversas: {},
    reunioes: {},
    marcos: {},
  };
}

export async function carregarEstado(dir, agora, log) {
  await mkdir(dir, { recursive: true });
  const caminho = join(dir, ARQUIVO);
  let bruto;
  try {
    bruto = await readFile(caminho, "utf8");
  } catch (erro) {
    if (erro.code === "ENOENT") return estadoNovo(agora);
    throw erro;
  }
  try {
    const estado = JSON.parse(bruto);
    if (estado?.versao !== 1 || typeof estado.inicio !== "string") throw new Error("forma_desconhecida");
    estado.passagens ??= {};
    estado.conversas ??= {};
    estado.reunioes ??= {};
    estado.marcos ??= {};
    estado.ultimoEnvioEm ??= null;
    return estado;
  } catch {
    const guardado = join(dir, `estado.corrompido-${agora.getTime()}.json`);
    await rename(caminho, guardado);
    log?.aviso("estado_corrompido_guardado", { arquivo: guardado });
    return estadoNovo(agora);
  }
}

export async function salvarEstado(dir, estado) {
  const caminho = join(dir, ARQUIVO);
  const temporario = `${caminho}.tmp`;
  await writeFile(temporario, JSON.stringify(estado, null, 2), "utf8");
  await rename(temporario, caminho);
}

/** Esquece o que já não pode voltar da consulta — a janela é que manda. */
export function podarEstado(estado, agora, retencaoMs) {
  const limite = agora.getTime() - retencaoMs;
  for (const colecao of [estado.passagens, estado.reunioes ?? {}]) {
    for (const [id, reg] of Object.entries(colecao)) {
      if (Date.parse(reg.em) < limite) delete colecao[id];
    }
  }
  for (const [conversa, quando] of Object.entries(estado.conversas)) {
    if (Date.parse(quando) < limite) delete estado.conversas[conversa];
  }
}

export async function registrarBatimento(dir, agora) {
  await writeFile(join(dir, "batimento"), agora.toISOString(), "utf8");
}
