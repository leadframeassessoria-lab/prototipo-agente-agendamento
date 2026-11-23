import assert from "node:assert/strict";
import { test } from "node:test";

import { PASSAGENS, REUNIOES, rodarCiclo } from "../src/ciclo.mjs";
import { estadoNovo } from "../src/estado.mjs";

const MIN = 60 * 1000;
const T0 = Date.parse("2026-10-05T20:00:00.000Z");

const config = {
  modo: "envio",
  idadeMaximaMs: 60 * MIN,
  reavisoMs: 30 * MIN,
  maxTentativas: 3,
  espacamentoMs: 7000,
};

let seq = 0;
function passagem(minutosDepoisDeT0, extra = {}) {
  seq++;
  const hex = seq.toString(16).padStart(12, "0");
  return {
    passagem_id: `00000000-0000-4000-8000-${hex}`,
    conversation_id: `11111111-1111-4111-8111-${hex}`,
    criado_em: new Date(T0 + minutosDepoisDeT0 * MIN).toISOString(),
    origem: "pedido_explicito",
    motivo_codigo: "requested_human",
    o_que_quer: "Quer falar com alguém",
    resumo: "Contexto acumulado (segundo a IA — confira):\nCliente quer orçamento.",
    ultimas_palavras: "Quero falar com um atendente",
    reconhecido_em: null,
    contato_nome: "Cliente Fictício",
    contato_telefone: "+5567999990000",
    ...extra,
  };
}

function cenario({ linhas, respostas = [], agoraMin = 5, estado, cfg = config }) {
  let agora = T0 + agoraMin * MIN;
  const enviados = [];
  const esperas = [];
  const logs = [];
  const salvos = [];
  const deps = {
    fonte: { passagensDesde: async () => linhas },
    enviador: {
      enviarAviso: async (aviso) => {
        enviados.push(aviso);
        return respostas.length ? respostas.shift() : { ok: true, wamid: `wamid.${enviados.length}` };
      },
    },
    estado: estado ?? estadoNovo(new Date(T0)),
    config: cfg,
    log: {
      info: (e, c) => logs.push(["info", e, c]),
      aviso: (e, c) => logs.push(["aviso", e, c]),
      erro: (e, c) => logs.push(["erro", e, c]),
    },
    salvar: async (e) => salvos.push(structuredClone(e)),
    dormir: async (ms) => {
      esperas.push(ms);
      agora += ms;
    },
    relogio: () => new Date(agora),
  };
  return { deps, enviados, esperas, logs, salvos, avancar: (min) => (agora += min * MIN) };
}

test("passagem nova é avisada uma vez só, mesmo relendo a janela", async () => {
  const linhas = [passagem(1)];
  const c = cenario({ linhas });
  const r1 = await rodarCiclo(c.deps);
  const r2 = await rodarCiclo(c.deps);
  assert.equal(r1.enviadas, 1);
  assert.equal(r2.enviadas, 0);
  assert.equal(c.enviados.length, 1);
  assert.equal(c.deps.estado.passagens[linhas[0].passagem_id].situacao, "enviado");
  assert.equal(c.deps.estado.passagens[linhas[0].passagem_id].wamid, "wamid.1");
});

test("passagem anterior ao marco zero da ponte nunca é avisada", async () => {
  const c = cenario({ linhas: [passagem(-5)] });
  const r = await rodarCiclo(c.deps);
  assert.equal(r.enviadas, 0);
  assert.equal(c.enviados.length, 0);
});

test("passagem velha demais é ignorada, não enviada", async () => {
  const c = cenario({ linhas: [passagem(1)], agoraMin: 90 });
  const r = await rodarCiclo(c.deps);
  assert.equal(r.ignoradas, 1);
  assert.equal(c.enviados.length, 0);
});

test("passagem que alguém já assumiu não gera aviso", async () => {
  const c = cenario({ linhas: [passagem(1, { reconhecido_em: new Date(T0 + 2 * MIN).toISOString() })] });
  await rodarCiclo(c.deps);
  assert.equal(c.enviados.length, 0);
});

test("a mesma conversa não é avisada de novo dentro da janela de reaviso", async () => {
  const a = passagem(1);
  const b = { ...passagem(2), conversation_id: a.conversation_id };
  const c = cenario({ linhas: [a, b] });
  const r = await rodarCiclo(c.deps);
  assert.equal(r.enviadas, 1);
  assert.equal(r.ignoradas, 1);
  assert.equal(c.deps.estado.passagens[b.passagem_id].motivo, "conversa_avisada_ha_pouco");
});

test("dois avisos seguidos respeitam o espaçamento", async () => {
  const c = cenario({ linhas: [passagem(1), passagem(2)] });
  await rodarCiclo(c.deps);
  assert.equal(c.enviados.length, 2);
  assert.deepEqual(c.esperas, [7000]);
});

test("modo teste nunca chama a Meta, mas registra para não repetir", async () => {
  const linhas = [passagem(1)];
  const c = cenario({ linhas, cfg: { ...config, modo: "teste" } });
  const r = await rodarCiclo(c.deps);
  await rodarCiclo(c.deps);
  assert.equal(r.simuladas, 1);
  assert.equal(c.enviados.length, 0);
  assert.equal(c.deps.estado.passagens[linhas[0].passagem_id].situacao, "simulado");
});

test("erro temporário deixa pendente, tenta de novo e desiste no teto", async () => {
  const linhas = [passagem(1)];
  const temporaria = { ok: false, tipo: "temporaria", codigo: 130429, status: 429 };
  const c = cenario({ linhas, respostas: [temporaria, temporaria, temporaria] });
  const id = linhas[0].passagem_id;

  await rodarCiclo(c.deps);
  assert.equal(c.deps.estado.passagens[id].situacao, "pendente");
  assert.equal(c.deps.estado.passagens[id].tentativas, 1);
  await rodarCiclo(c.deps);
  assert.equal(c.deps.estado.passagens[id].tentativas, 2);
  const r3 = await rodarCiclo(c.deps);
  assert.equal(c.deps.estado.passagens[id].situacao, "falhou");
  assert.equal(r3.falhas, 1);
  await rodarCiclo(c.deps);
  assert.equal(c.enviados.length, 3);
});

test("erro de configuração para o ciclo e não gasta tentativa da passagem", async () => {
  const linhas = [passagem(1), passagem(2)];
  const configuracao = { ok: false, tipo: "configuracao", codigo: 190, status: 401 };
  const c = cenario({ linhas, respostas: [configuracao, configuracao, configuracao, configuracao] });
  for (let i = 0; i < 4; i++) {
    const r = await rodarCiclo(c.deps);
    assert.equal(r.interrompido, "configuracao");
  }
  const reg = c.deps.estado.passagens[linhas[0].passagem_id];
  assert.equal(reg.situacao, "pendente");
  assert.equal(reg.tentativas, 0);
  assert.equal(c.deps.estado.passagens[linhas[1].passagem_id], undefined);
  assert.equal(c.enviados.length, 4);

  // Consertado o token, a passagem que esperava sai.
  const r = await rodarCiclo(c.deps);
  assert.equal(r.enviadas, 2);
});

test("recusa permanente marca falha e segue para a próxima passagem", async () => {
  const linhas = [passagem(1), passagem(2)];
  const c = cenario({ linhas, respostas: [{ ok: false, tipo: "permanente", codigo: 131026, status: 400 }] });
  const r = await rodarCiclo(c.deps);
  assert.equal(r.falhas, 1);
  assert.equal(r.enviadas, 1);
});

test("o log não leva nome, telefone nem texto do cliente", async () => {
  const c = cenario({
    linhas: [passagem(1)],
    respostas: [{ ok: false, tipo: "permanente", codigo: 131026, status: 400, detalhe: "x" }],
  });
  await rodarCiclo(c.deps);
  const tudo = JSON.stringify(c.logs);
  assert.ok(!tudo.includes("Cliente Fictício"));
  assert.ok(!tudo.includes("99999"));
  assert.ok(!tudo.includes("Quero falar com um atendente"));
});

test("o estado é gravado logo depois de cada envio (queda não reenvia)", async () => {
  const c = cenario({ linhas: [passagem(1)] });
  await rodarCiclo(c.deps);
  const primeiroSalvo = c.salvos[0];
  assert.equal(Object.values(primeiroSalvo.passagens)[0].situacao, "enviado");
});

// ── reuniões marcadas pela IA ───────────────────────────────────────────────

function reuniao(minutosDepoisDeT0, extra = {}) {
  seq++;
  const hex = seq.toString(16).padStart(12, "0");
  return {
    reuniao_id: `22222222-2222-4222-8222-${hex}`,
    conversation_id: `11111111-1111-4111-8111-${hex}`,
    criado_em: new Date(T0 + minutosDepoisDeT0 * MIN).toISOString(),
    inicia_em: "2026-10-07T12:30:00.000Z",
    fuso: "America/Sao_Paulo",
    titulo: "Reunião sobre chalé",
    notas: "Conversa para avaliar o projeto.",
    situacao: "confirmed",
    contato_nome: "Cliente Fictício",
    contato_telefone: "+5567999990000",
    ...extra,
  };
}

/** Estado em que o tipo reunião já rodou desde T0 (marco zero em T0). */
function estadoComReunioesDesdeT0() {
  const e = estadoNovo(new Date(T0));
  e.marcos.reunioes = new Date(T0).toISOString();
  return e;
}

test("reunião nova é avisada uma vez só, pelo modelo da reunião", async () => {
  const linhas = [reuniao(1)];
  const c = cenario({ linhas, estado: estadoComReunioesDesdeT0() });
  c.deps.fonte = { reunioesDesde: async () => linhas };
  const r1 = await rodarCiclo({ ...c.deps, tipo: REUNIOES });
  const r2 = await rodarCiclo({ ...c.deps, tipo: REUNIOES });
  assert.equal(r1.enviadas, 1);
  assert.equal(r2.enviadas, 0);
  assert.equal(c.enviados.length, 1);
  assert.equal(c.enviados[0].modelo.nome, "aviso_reuniao_marcada");
  assert.equal(c.enviados[0].parametros[2], "quarta-feira, 07/10 às 9h30");
  assert.equal(c.deps.estado.reunioes[linhas[0].reuniao_id].situacao, "enviado");
  assert.deepEqual(c.deps.estado.passagens, {});
});

test("passagem sai pelo modelo de passagem", async () => {
  const c = cenario({ linhas: [passagem(1)] });
  await rodarCiclo({ ...c.deps, tipo: PASSAGENS });
  assert.equal(c.enviados[0].modelo.nome, "aviso_passagem_humano");
});

test("reunião cancelada antes do aviso não é avisada", async () => {
  const linhas = [reuniao(1, { situacao: "cancelled" })];
  const c = cenario({ linhas, estado: estadoComReunioesDesdeT0() });
  c.deps.fonte = { reunioesDesde: async () => linhas };
  const r = await rodarCiclo({ ...c.deps, tipo: REUNIOES });
  assert.equal(r.ignoradas, 1);
  assert.equal(c.enviados.length, 0);
  assert.equal(c.deps.estado.reunioes[linhas[0].reuniao_id].motivo, "cancelada");
});

test("ligar o aviso de reunião depois não avisa as reuniões de antes", async () => {
  const linhas = [reuniao(1)];
  const c = cenario({ linhas, agoraMin: 5 });
  c.deps.fonte = { reunioesDesde: async () => linhas };
  const r = await rodarCiclo({ ...c.deps, tipo: REUNIOES });
  assert.equal(r.enviadas, 0);
  assert.equal(c.deps.estado.marcos.reunioes, new Date(T0 + 5 * MIN).toISOString());
});

test("cliente que marca e logo pede uma pessoa gera os dois avisos", async () => {
  const r = reuniao(1);
  const p = { ...passagem(2), conversation_id: r.conversation_id };
  const c = cenario({ linhas: [p], estado: estadoComReunioesDesdeT0() });
  c.deps.fonte = { reunioesDesde: async () => [r], passagensDesde: async () => [p] };
  await rodarCiclo({ ...c.deps, tipo: REUNIOES });
  await rodarCiclo({ ...c.deps, tipo: PASSAGENS });
  assert.deepEqual(
    c.enviados.map((a) => a.modelo.nome),
    ["aviso_reuniao_marcada", "aviso_passagem_humano"],
  );
});

test("modelo de reunião ainda não aprovado para só as reuniões, sem gastar tentativa", async () => {
  const linhas = [reuniao(1)];
  const naoAprovado = { ok: false, tipo: "configuracao", codigo: 132001, status: 404 };
  const c = cenario({ linhas, estado: estadoComReunioesDesdeT0(), respostas: [naoAprovado] });
  c.deps.fonte = { reunioesDesde: async () => linhas };
  const r = await rodarCiclo({ ...c.deps, tipo: REUNIOES });
  assert.equal(r.interrompido, "configuracao");
  const reg = c.deps.estado.reunioes[linhas[0].reuniao_id];
  assert.equal(reg.situacao, "pendente");
  assert.equal(reg.tentativas, 0);
});

test("o log da reunião não leva nome, telefone nem texto do cliente", async () => {
  const linhas = [reuniao(1)];
  const c = cenario({ linhas, estado: estadoComReunioesDesdeT0() });
  c.deps.fonte = { reunioesDesde: async () => linhas };
  await rodarCiclo({ ...c.deps, tipo: REUNIOES });
  const tudo = JSON.stringify(c.logs);
  assert.ok(!tudo.includes("Cliente Fictício"));
  assert.ok(!tudo.includes("99999"));
  assert.ok(!tudo.includes("chalé"));
  assert.ok(tudo.includes(linhas[0].reuniao_id));
});
