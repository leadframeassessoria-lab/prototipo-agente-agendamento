/**
 * A LEITURA DAS PASSAGENS NO SUPABASE DO DESKCOMM.
 *
 * A ponte não lê tabela nenhuma do Deskcomm diretamente. Ela entra com um papel
 * próprio (`leadframe_ponte_leitor`) que só pode chamar DUAS funções
 * (`leadframe_ponte.passagens_para_avisar` e `leadframe_ponte.reunioes_para_avisar`,
 * em `sql/01-leitura-dedicada.sql`), e elas devolvem só os campos do aviso.
 * Vazou a senha? Quem a tem lê passagens e reuniões da IA das últimas 24 horas
 * da organização liberada — não contatos, não mensagens, não o resto do CRM.
 *
 * TLS: `sslmode` na URL é REMOVIDO de propósito. O `pg` deixa o que vem na URL
 * passar por cima da opção `ssl` do código, e aí a escolha de verificar ou não o
 * certificado deixaria de ser desta configuração.
 */
import { readFileSync } from "node:fs";

import pg from "pg";

function opcoesDeTls(db) {
  if (db.ssl === "desligado") return false;
  if (db.caArquivo) return { ca: readFileSync(db.caArquivo, "utf8"), rejectUnauthorized: true };
  if (db.ssl === "sem_verificar") return { rejectUnauthorized: false };
  return { rejectUnauthorized: true };
}

function semSslmode(url) {
  const u = new URL(url);
  u.searchParams.delete("sslmode");
  return u.toString();
}

const iso = (v) => (v instanceof Date ? v.toISOString() : v ?? null);

export function criarFontePostgres({ db, orgId }) {
  const pool = new pg.Pool({
    connectionString: semSslmode(db.url),
    ssl: opcoesDeTls(db),
    max: 2,
    idleTimeoutMillis: 30_000,
    connectionTimeoutMillis: 10_000,
    application_name: "leadframe-ponte-avisos",
  });
  // Conexão que cai parada no pool emite 'error' no pool; sem ouvinte, o Node
  // derruba o processo. A próxima consulta abre outra.
  pool.on("error", () => {});

  return {
    /** Passagens criadas a partir de `desde`, da mais antiga para a mais nova. */
    async passagensDesde(desde, limite = 100) {
      const { rows } = await pool.query(
        "select * from leadframe_ponte.passagens_para_avisar($1::uuid, $2::timestamptz, $3::int)",
        [orgId, desde.toISOString(), limite],
      );
      return rows.map((r) => ({ ...r, criado_em: iso(r.criado_em), reconhecido_em: iso(r.reconhecido_em) }));
    },
    /** Reuniões que a IA marcou a partir de `desde`, da mais antiga para a mais nova. */
    async reunioesDesde(desde, limite = 100) {
      const { rows } = await pool.query(
        "select * from leadframe_ponte.reunioes_para_avisar($1::uuid, $2::timestamptz, $3::int)",
        [orgId, desde.toISOString(), limite],
      );
      return rows.map((r) => ({ ...r, criado_em: iso(r.criado_em), inicia_em: iso(r.inicia_em) }));
    },
    async encerrar() {
      await pool.end();
    },
  };
}
