import assert from "node:assert/strict";
import { mkdtemp, readdir, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { ErroDeConfiguracao, lerConfig } from "../src/config.mjs";
import { carregarEstado, estadoNovo, podarEstado, salvarEstado } from "../src/estado.mjs";
import { MODELO, MODELO_REUNIAO } from "../src/modelo.mjs";

const pastaTemporaria = () => mkdtemp(join(tmpdir(), "ponte-avisos-"));

// ── estado ──────────────────────────────────────────────────────────────────

test("estado: grava e lê de volta igual", async () => {
  const dir = await pastaTemporaria();
  const e = estadoNovo(new Date("2026-10-05T20:00:00Z"));
  e.passagens.x = { situacao: "enviado", em: "2026-10-05T20:01:00.000Z" };
  await salvarEstado(dir, e);
  assert.deepEqual(await carregarEstado(dir, new Date()), e);
});

test("estado: sem arquivo começa com marco zero agora", async () => {
  const dir = await pastaTemporaria();
  const agora = new Date("2026-10-05T20:00:00Z");
  const e = await carregarEstado(dir, agora);
  assert.equal(e.inicio, agora.toISOString());
});

test("estado: arquivo corrompido é guardado e a ponte recomeça", async () => {
  const dir = await pastaTemporaria();
  await writeFile(join(dir, "estado.json"), "{ isto não é json", "utf8");
  const avisos = [];
  const e = await carregarEstado(dir, new Date("2026-10-05T20:00:00Z"), { aviso: (ev) => avisos.push(ev) });
  assert.deepEqual(e.passagens, {});
  assert.deepEqual(avisos, ["estado_corrompido_guardado"]);
  assert.ok((await readdir(dir)).some((f) => f.startsWith("estado.corrompido-")));
});

test("estado: arquivo de antes das reuniões ganha as coleções novas vazias", async () => {
  const dir = await pastaTemporaria();
  const antigo = { versao: 1, inicio: "2026-10-05T20:00:00.000Z", ultimoEnvioEm: null, passagens: {}, conversas: {} };
  await writeFile(join(dir, "estado.json"), JSON.stringify(antigo), "utf8");
  const e = await carregarEstado(dir, new Date("2026-10-05T21:00:00Z"));
  assert.deepEqual(e.reunioes, {});
  assert.deepEqual(e.marcos, {});
  assert.equal(e.inicio, antigo.inicio);
});

test("estado: poda também esquece reuniões velhas", () => {
  const e = estadoNovo(new Date("2026-10-01T00:00:00Z"));
  e.reunioes.velha = { situacao: "enviado", em: "2026-10-01T00:00:00.000Z" };
  e.reunioes.nova = { situacao: "enviado", em: "2026-10-05T19:00:00.000Z" };
  podarEstado(e, new Date("2026-10-05T20:00:00Z"), 24 * 60 * 60 * 1000);
  assert.deepEqual(Object.keys(e.reunioes), ["nova"]);
});

test("estado: poda esquece o que passou da retenção", () => {
  const e = estadoNovo(new Date("2026-10-01T00:00:00Z"));
  e.passagens.velha = { situacao: "enviado", em: "2026-10-01T00:00:00.000Z" };
  e.passagens.nova = { situacao: "enviado", em: "2026-10-05T19:00:00.000Z" };
  e.conversas.c1 = "2026-10-01T00:00:00.000Z";
  podarEstado(e, new Date("2026-10-05T20:00:00Z"), 24 * 60 * 60 * 1000);
  assert.deepEqual(Object.keys(e.passagens), ["nova"]);
  assert.deepEqual(e.conversas, {});
});

test("estado: escrita não deixa .tmp para trás", async () => {
  const dir = await pastaTemporaria();
  await salvarEstado(dir, estadoNovo(new Date()));
  assert.deepEqual(await readdir(dir), ["estado.json"]);
  JSON.parse(await readFile(join(dir, "estado.json"), "utf8"));
});

// ── configuração ────────────────────────────────────────────────────────────

const BASE = {
  PONTE_ORG_ID: "6d0c8a2e-1b3f-4c5d-9e7f-0a1b2c3d4e5f",
  PONTE_DB_URL: "postgresql://leadframe_ponte_leitor.ref:senha@host:5432/postgres",
};

test("config: sem PONTE_MODO o padrão é teste (não envia)", () => {
  assert.equal(lerConfig(BASE).modo, "teste");
});

test("config: modo envio exige número, token e destino", () => {
  assert.throws(() => lerConfig({ ...BASE, PONTE_MODO: "envio" }), (e) => {
    assert.ok(e instanceof ErroDeConfiguracao);
    assert.equal(e.problemas.length, 3);
    return true;
  });
});

test("config: destino aceita +55 com pontuação e vira só dígitos", () => {
  const c = lerConfig({
    ...BASE,
    PONTE_MODO: "envio",
    META_PHONE_NUMBER_ID: "123456789012345",
    META_TOKEN: "x".repeat(40),
    AVISO_DESTINO: "+55 (00) 99999-0001",
  });
  assert.equal(c.destino, "5500999990001");
});

test("config: erro nunca repete o valor de segredo", () => {
  const segredo = "SEGREDO-curto";
  try {
    lerConfig({ ...BASE, PONTE_MODO: "envio", META_TOKEN: segredo, PONTE_DB_URL: `mysql://${segredo}` });
    assert.fail("devia lançar");
  } catch (e) {
    assert.ok(!e.message.includes(segredo));
  }
});

test("config: aviso de reunião começa desligado e só aceita ligado/desligado", () => {
  assert.equal(lerConfig(BASE).reunioes, false);
  assert.equal(lerConfig({ ...BASE, PONTE_REUNIOES: "ligado" }).reunioes, true);
  assert.throws(() => lerConfig({ ...BASE, PONTE_REUNIOES: "sim" }), ErroDeConfiguracao);
});

test("config: scripts sem banco não exigem org nem URL", () => {
  assert.equal(lerConfig({}, { exigirBanco: false }).modo, "teste");
});

// ── modelo ──────────────────────────────────────────────────────────────────

test("modelo: seis variáveis, em ordem, cada uma uma vez", () => {
  const vars = [...MODELO.corpo.matchAll(/\{\{(\d+)\}\}/g)].map((m) => Number(m[1]));
  assert.deepEqual(vars, [1, 2, 3, 4, 5, 6]);
});

test("modelo: texto idêntico ao enviado para a Meta em 2026-10-05", () => {
  assert.equal(
    MODELO.corpo,
    "🔔 Atendimento para você assumir\n\nCliente: {{1}}\nTelefone: {{2}}\nMotivo: {{3}}\n" +
      "O que o cliente quer: {{4}}\nResumo da conversa: {{5}}\nÚltima mensagem do cliente: {{6}}\n\n" +
      "A IA já parou de responder esse cliente. Responder aqui não chega ao cliente: use o botão abaixo.",
  );
  assert.equal(MODELO.nome, "aviso_passagem_humano");
  assert.equal(MODELO.botao.urlBase, "https://crm.exemplo.com.br/app/inbox/");
});

test("modelo de reunião: cinco variáveis em ordem e texto aprovado pelo operador", () => {
  const vars = [...MODELO_REUNIAO.corpo.matchAll(/\{\{(\d+)\}\}/g)].map((m) => Number(m[1]));
  assert.deepEqual(vars, [1, 2, 3, 4, 5]);
  assert.equal(
    MODELO_REUNIAO.corpo,
    "📅 Reunião marcada pela IA\n\nCliente: {{1}}\nTelefone: {{2}}\nQuando: {{3}}\nAssunto: {{4}}\n" +
      "Resumo da conversa: {{5}}\n\nO compromisso já está na sua agenda Google, com o link do Meet.",
  );
  assert.equal(MODELO_REUNIAO.nome, "aviso_reuniao_marcada");
  assert.equal(MODELO_REUNIAO.botao.urlBase, "https://crm.exemplo.com.br/app/inbox/");
});
