/**
 * PRÉVIA SEM BANCO E SEM REDE — mostra o aviso que sairia para cada passagem ou
 * reunião de um arquivo JSON (o padrão são os exemplos fictícios de `teste/fixtures`).
 *
 *   node scripts/previa-local.mjs [arquivo.json]
 *
 * Linha com `reuniao_id` sai no modelo da reunião; as outras, no de passagem.
 * Também imprime o pedido que iria para a Meta, com o destino mascarado e sem
 * token — é o jeito de conferir o formato antes de existir credencial.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { PASSAGENS, REUNIOES } from "../src/ciclo.mjs";
import { criarEnviadorMeta } from "../src/meta.mjs";

const fixture = (nome) => fileURLToPath(new URL(`../teste/fixtures/${nome}`, import.meta.url));
const arquivos = process.argv[2] ? [process.argv[2]] : [fixture("passagem-exemplo.json"), fixture("reuniao-exemplo.json")];
const { corpoDoPedido } = criarEnviadorMeta({
  versao: "v23.0",
  phoneNumberId: "<META_PHONE_NUMBER_ID>",
  token: "<nao-usado-na-previa>",
  destino: "55••••••••001",
  template: PASSAGENS.modelo.nome,
  idioma: PASSAGENS.modelo.idioma,
});

for (const arquivo of arquivos) {
  const linhas = JSON.parse(readFileSync(arquivo, "utf8"));
  for (const l of Array.isArray(linhas) ? linhas : [linhas]) {
    const tipo = l.reuniao_id ? REUNIOES : PASSAGENS;
    const aviso = tipo.montar(l);
    console.log(`\n════ ${tipo.nome} ${tipo.id(l)} ════\n`);
    console.log(aviso.texto);
    console.log(`\n[ ${tipo.modelo.botao.texto} ] → ${aviso.link}`);
    console.log(`(${aviso.texto.length}/${tipo.modelo.limiteDoCorpo} caracteres)\n`);
    console.log("Pedido para a Meta:");
    console.log(JSON.stringify(corpoDoPedido({ ...aviso, modelo: tipo.modelo }), null, 2));
  }
}
