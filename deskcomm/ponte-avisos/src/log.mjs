/**
 * O LOG — uma linha JSON por evento, na saída padrão (o Docker guarda e gira).
 *
 * CONTRATO: nome, telefone e texto de cliente NUNCA entram aqui. O log fica no
 * disco da VPS, fora da anonimização do Deskcomm, e ninguém o expurga. O que
 * identifica um evento são os ids da passagem e da conversa — com eles, quem
 * precisa do resto abre o CRM com a permissão que tem.
 */
export function criarLog(saida = process.stdout) {
  const escrever = (nivel, evento, campos = {}) => {
    saida.write(`${JSON.stringify({ em: new Date().toISOString(), nivel, evento, ...campos })}\n`);
  };
  return {
    info: (evento, campos) => escrever("info", evento, campos),
    aviso: (evento, campos) => escrever("aviso", evento, campos),
    erro: (evento, campos) => escrever("erro", evento, campos),
  };
}

/** Um erro reduzido ao que serve para diagnóstico, sem pilha nem payload. */
export function resumoDoErro(erro) {
  return { nome: erro?.name ?? "Error", codigo: erro?.code ?? null, mensagem: String(erro?.message ?? erro) };
}
