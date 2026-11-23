import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  extrairResumo,
  formatarQuando,
  formatarTelefone,
  limparTexto,
  montarAviso,
  montarAvisoReuniao,
  PISO_DO_BRIEFING,
  truncar,
} from "../src/mensagem.mjs";
import { MODELO, MODELO_REUNIAO } from "../src/modelo.mjs";

const exemplos = JSON.parse(readFileSync(new URL("./fixtures/passagem-exemplo.json", import.meta.url), "utf8"));
const reuniao = JSON.parse(readFileSync(new URL("./fixtures/reuniao-exemplo.json", import.meta.url), "utf8"))[0];

test("parâmetro vira uma linha só: sem quebra, tab nem espaços em sequência", () => {
  assert.equal(limparTexto("linha 1\nlinha 2\t\tfim     de    tudo", 100), "linha 1 linha 2 fim de tudo");
});

test("separadores de linha Unicode viram espaço e nenhuma letra some", () => {
  const sep = String.fromCodePoint(0x2028) + String.fromCodePoint(0x2029);
  assert.equal(limparTexto(`abc${sep}cCc pCp {Cc}`, 80), "abc cCc pCp {Cc}");
});

test("link escrito pelo cliente não sai no aviso", () => {
  assert.equal(limparTexto("veja https://golpe.exemplo/pagar agora", 100), "veja [link removido] agora");
  assert.equal(limparTexto("acesse www.golpe-exemplo.com", 100), "acesse [link removido]");
  assert.equal(limparTexto("site golpe-exemplo.com.br/x", 100), "site [link removido]");
});

test("sequência longa de dígitos (CPF, cartão) é mascarada; número curto fica", () => {
  assert.equal(limparTexto("meu CPF 123.456.789-00", 100), "meu CPF [número removido]");
  assert.equal(limparTexto("tenho 2 lojas e 15 funcionários", 100), "tenho 2 lojas e 15 funcionários");
});

test("texto vazio ou só espaço vira null, nunca string vazia", () => {
  assert.equal(limparTexto("   \n ", 50), null);
  assert.equal(limparTexto(null, 50), null);
});

test("truncar não parte emoji ao meio e respeita o teto em UTF-16", () => {
  const t = truncar("😀".repeat(10), 7);
  assert.ok(t.length <= 7);
  assert.ok(t.endsWith("…"));
  assert.ok(!/[\uD800-\uDBFF]…$/.test(t));
});

test("telefone brasileiro sai formatado; ausente vira null", () => {
  assert.equal(formatarTelefone("+5500999990001"), "+55 00 99999-0001");
  assert.equal(formatarTelefone("+550090000002"), "+55 00 9000-0002");
  assert.equal(formatarTelefone("+14155550123"), "+14155550123");
  assert.equal(formatarTelefone(null), null);
});

test("resumo tira os blocos que já têm parâmetro e mantém o resto", () => {
  const r = extrairResumo(exemplos[0].resumo);
  assert.ok(!r.includes("Por que a IA passou"));
  assert.ok(!r.includes("O que o cliente quer"));
  assert.ok(!r.includes("Últimas mensagens do cliente"));
  assert.ok(r.includes("O que a IA já tentou: Explicou que a Leadframe faz gestão de redes sociais"));
  assert.ok(r.includes("loja de roupas em Campo Grande"));
  assert.ok(!r.includes("\n"));
});

test("resumo padrão do Deskcomm (sem contexto) conta como sem resumo", () => {
  assert.equal(extrairResumo(PISO_DO_BRIEFING), null);
});

test("aviso completo: seis parâmetros, ordem do modelo, link pela conversa", () => {
  const a = montarAviso(exemplos[0]);
  assert.equal(a.parametros.length, 6);
  assert.equal(a.parametros[0], "Maria Souza");
  assert.equal(a.parametros[1], "+55 67 99999-0000");
  assert.equal(a.parametros[2], "O cliente pediu para falar com uma pessoa");
  assert.equal(a.sufixoUrl, exemplos[0].conversation_id);
  assert.equal(a.link, MODELO.botao.urlBase + exemplos[0].conversation_id);
  assert.ok(a.texto.startsWith("🔔 Atendimento para você assumir"));
  assert.equal(a.parametros[5], "Tenho uma loja de roupas / Quero falar com um atendente, por favor");
  for (const p of a.parametros) {
    assert.ok(p.length > 0);
    assert.ok(!/[\n\t]| {5,}/.test(p));
  }
});

test("passagem sem nome, telefone nem resumo ainda gera aviso legível", () => {
  const a = montarAviso(exemplos[1]);
  assert.equal(a.parametros[0], "Sem nome cadastrado");
  assert.equal(a.parametros[1], "Não cadastrado");
  assert.equal(a.parametros[3], "Não registrado pela IA");
  assert.equal(a.parametros[4], "Sem resumo ainda; abra a conversa no CRM");
  assert.ok(a.parametros[5].includes("[número removido]"));
  assert.ok(a.parametros[5].includes("[link removido]"));
});

test("motivo desconhecido não quebra o aviso", () => {
  const a = montarAviso({ ...exemplos[0], motivo_codigo: "motivo_novo_do_deskcomm" });
  assert.equal(a.parametros[2], "Motivo não identificado pelo sistema");
});

test("textos enormes cabem no limite de 1.024 caracteres da Meta", () => {
  const enorme = "palavra ".repeat(2000);
  const a = montarAviso({
    ...exemplos[0],
    contato_nome: enorme,
    o_que_quer: enorme,
    resumo: enorme,
    ultimas_palavras: enorme,
  });
  assert.ok(a.texto.length <= MODELO.limiteDoCorpo, `tamanho ${a.texto.length}`);
  assert.ok(a.parametros[4].length >= 40);
});

test("id de conversa que não é uuid é recusado (vira URL no botão)", () => {
  assert.throws(() => montarAviso({ ...exemplos[0], conversation_id: "../../admin" }), { codigo: "conversa_invalida" });
});

// ── reunião marcada pela IA ─────────────────────────────────────────────────

test("quando sai no fuso em que a reunião foi marcada, com dia da semana", () => {
  assert.equal(formatarQuando("2026-10-07T12:30:00.000Z", "America/Sao_Paulo"), "quarta-feira, 07/10 às 9h30");
  assert.equal(formatarQuando("2026-10-06T12:00:00.000Z", "America/Sao_Paulo"), "terça-feira, 06/10 às 9h");
  assert.equal(formatarQuando("2026-10-07T12:30:00.000Z", null), "quarta-feira, 07/10 às 9h30");
  assert.equal(formatarQuando("não é data", "America/Sao_Paulo"), null);
  assert.equal(formatarQuando("2026-10-07T12:30:00.000Z", "Fuso/Inexistente"), null);
});

test("aviso de reunião: cinco parâmetros na ordem do modelo e link pela conversa", () => {
  const a = montarAvisoReuniao(reuniao);
  assert.deepEqual(a.parametros.slice(0, 4), [
    "Maria Souza",
    "+55 67 99999-0000",
    "quarta-feira, 07/10 às 9h30",
    "Reunião sobre chalé em Cuiabá",
  ]);
  assert.equal(a.parametros.length, 5);
  assert.equal(a.link, MODELO_REUNIAO.botao.urlBase + reuniao.conversation_id);
  assert.ok(a.texto.startsWith("📅 Reunião marcada pela IA"));
  for (const p of a.parametros) assert.ok(p.length > 0 && !/[\n\t]| {5,}/.test(p));
});

test("aviso de reunião mantém o e-mail do cliente (o Bruno confere o domínio)", () => {
  const a = montarAvisoReuniao(reuniao);
  assert.ok(a.parametros[4].includes("cliente.teste@gmai.com"), a.parametros[4]);
});

test("aviso de reunião ainda tira link e número longo do resumo", () => {
  const a = montarAvisoReuniao({
    ...reuniao,
    notas: "pague em www.golpe-exemplo.com, CPF 123.456.789-00, e-mail joao@empresa.com.br",
  });
  // O filtro de link leva junto a pontuação colada no endereço (a vírgula).
  assert.equal(a.parametros[4], "pague em [link removido] CPF [número removido], e-mail joao@empresa.com.br");
});

test("limparTexto sem manterEmails continua tirando o domínio do e-mail", () => {
  assert.equal(limparTexto("escreva para joao@golpe.com", 100), "escreva para joao@[link removido]");
});

test("aviso de reunião sem nome, sem título e sem notas ainda é legível", () => {
  const a = montarAvisoReuniao({ ...reuniao, contato_nome: null, contato_telefone: null, titulo: null, notas: null });
  assert.deepEqual(
    [a.parametros[0], a.parametros[1], a.parametros[3], a.parametros[4]],
    ["Sem nome cadastrado", "Não cadastrado", "Reunião", "Sem resumo; abra a conversa no CRM"],
  );
});

test("aviso de reunião: textos enormes cabem no limite da Meta", () => {
  const enorme = "palavra ".repeat(2000);
  const a = montarAvisoReuniao({ ...reuniao, contato_nome: enorme, titulo: enorme, notas: enorme });
  assert.ok(a.texto.length <= MODELO_REUNIAO.limiteDoCorpo, `tamanho ${a.texto.length}`);
  assert.ok(a.parametros[4].length >= 40);
});

test("aviso de reunião recusa conversa que não é uuid e horário inválido", () => {
  assert.throws(() => montarAvisoReuniao({ ...reuniao, conversation_id: null }), { codigo: "conversa_invalida" });
  assert.throws(() => montarAvisoReuniao({ ...reuniao, inicia_em: "x" }), { codigo: "horario_invalido" });
});
