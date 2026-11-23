import assert from "node:assert/strict";
import { test } from "node:test";

import { classificarErro, criarEnviadorMeta } from "../src/meta.mjs";

const TOKEN = "EAAG-token-de-teste-que-nao-pode-vazar-0123456789";

function enviadorCom(resposta, capturas = []) {
  const fetchImpl = async (url, init) => {
    capturas.push({ url, init });
    if (resposta instanceof Error) throw resposta;
    return {
      ok: resposta.status >= 200 && resposta.status < 300,
      status: resposta.status,
      json: async () => resposta.json,
    };
  };
  return criarEnviadorMeta({
    versao: "v23.0",
    phoneNumberId: "123456789012345",
    token: TOKEN,
    destino: "5500999990001",
    template: "aviso_passagem_humano",
    idioma: "pt_BR",
    fetchImpl,
  });
}

const aviso = { parametros: ["a", "b", "c", "d", "e", "f"], sufixoUrl: "3f2b8c1e-5a4d-4e7b-9c21-8d6f0a1b2c3d" };

test("pedido no formato da Cloud API: modelo, idioma, 6 parâmetros e botão de URL", async () => {
  const capturas = [];
  await enviadorCom({ status: 200, json: { messages: [{ id: "wamid.X" }] } }, capturas).enviarAviso(aviso);
  const { url, init } = capturas[0];
  assert.equal(url, "https://graph.facebook.com/v23.0/123456789012345/messages");
  assert.equal(init.headers.Authorization, `Bearer ${TOKEN}`);
  const corpo = JSON.parse(init.body);
  assert.equal(corpo.to, "5500999990001");
  assert.equal(corpo.template.name, "aviso_passagem_humano");
  assert.equal(corpo.template.language.code, "pt_BR");
  assert.deepEqual(
    corpo.template.components[0].parameters.map((p) => p.text),
    ["a", "b", "c", "d", "e", "f"],
  );
  assert.deepEqual(corpo.template.components[1], {
    type: "button",
    sub_type: "url",
    index: "0",
    parameters: [{ type: "text", text: aviso.sufixoUrl }],
  });
});

test("sucesso devolve o id da mensagem", async () => {
  const r = await enviadorCom({ status: 200, json: { messages: [{ id: "wamid.ABC", message_status: "accepted" }] } }).enviarAviso(aviso);
  assert.deepEqual(r, { ok: true, wamid: "wamid.ABC", situacao: "accepted" });
});

test("rede fora do ar é temporária e não lança", async () => {
  const r = await enviadorCom(new TypeError("fetch failed")).enviarAviso(aviso);
  assert.equal(r.ok, false);
  assert.equal(r.tipo, "temporaria");
});

test("classificação dos erros da Meta", () => {
  assert.equal(classificarErro(429, 130429), "temporaria");
  assert.equal(classificarErro(400, 131056), "temporaria"); // ritmo por destinatário
  assert.equal(classificarErro(500, null), "temporaria");
  assert.equal(classificarErro(401, 190), "configuracao"); // token vencido
  assert.equal(classificarErro(404, 132001), "configuracao"); // modelo não existe / não aprovado
  assert.equal(classificarErro(400, 131030), "configuracao"); // destino fora da lista permitida
  assert.equal(classificarErro(400, 132015), "configuracao"); // modelo pausado
  assert.equal(classificarErro(400, 131042), "configuracao"); // sem forma de pagamento na conta
  assert.equal(classificarErro(400, 131026), "permanente"); // destinatário não recebe
  assert.equal(classificarErro(400, 132012), "permanente"); // parâmetro deste aviso
  assert.equal(classificarErro(400, null), "permanente");
});

test("erro da Meta volta com código e rastreio, e nunca com o token", async () => {
  const r = await enviadorCom({
    status: 401,
    json: { error: { code: 190, message: `Invalid token ${TOKEN}`, fbtrace_id: "Abc123" } },
  }).enviarAviso(aviso);
  assert.equal(r.tipo, "configuracao");
  assert.equal(r.codigo, 190);
  assert.equal(r.fbtrace, "Abc123");
  assert.ok(!JSON.stringify(r).includes(TOKEN));
});

test("resposta 200 sem id não é tratada como enviada", async () => {
  const r = await enviadorCom({ status: 200, json: {} }).enviarAviso(aviso);
  assert.equal(r.ok, false);
  assert.equal(r.tipo, "temporaria");
});

test("modelo por aviso: troca nome e idioma só daquele pedido", () => {
  const e = enviadorCom({ status: 200, json: {} });
  const outro = e.corpoDoPedido({ ...aviso, modelo: { nome: "aviso_reuniao_marcada", idioma: "pt_BR" } });
  assert.equal(outro.template.name, "aviso_reuniao_marcada");
  assert.equal(e.corpoDoPedido(aviso).template.name, "aviso_passagem_humano");
});
