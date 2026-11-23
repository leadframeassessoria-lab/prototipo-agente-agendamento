/**
 * VERIFICAÇÃO DE SAÚDE DO DOCKER — sai com 0 se o último ciclo bom é recente.
 *
 * O batimento só é gravado quando o ciclo leu o banco E não foi barrado por
 * configuração (token vencido, modelo pausado). Então "unhealthy" no
 * `docker ps` quer dizer: a ponte está viva, mas nenhum aviso está saindo.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

const dir = process.env.PONTE_DIR_ESTADO || "./dados";
const intervaloMs = Number(process.env.PONTE_INTERVALO_S || 30) * 1000;
const toleranciaMs = Math.max(3 * intervaloMs, 180_000);

try {
  const ultimo = Date.parse(readFileSync(join(dir, "batimento"), "utf8").trim());
  process.exit(Date.now() - ultimo <= toleranciaMs ? 0 : 1);
} catch {
  process.exit(1);
}
