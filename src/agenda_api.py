"""Serviço de agenda: API HTTP + SQLite.

É a *fonte de verdade externa* do protótipo. O agente não sabe nada sobre
disponibilidade: ele pergunta aqui. Tudo que o agente afirmar sobre horário
livre, horário ocupado ou reserva criada precisa ter vindo de uma resposta
deste serviço.

Sem dependência externa: `http.server` + `sqlite3` da biblioteca padrão.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

# Janela de agenda semeada. Fixa de propósito: teste que depende de "hoje"
# muda de resultado sozinho e deixa de ser teste.
INICIO_JANELA = date(2026, 9, 15)
DIAS_JANELA = 30
HORARIOS = ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00", "17:00"]

# Compromissos já ocupados na semeadura. Existem para que o agente precise
# lidar com "não tem esse horário" sem poder inventar um substituto.
OCUPADOS = {
    "2026-09-22": ["09:00", "10:00", "14:00"],
    "2026-09-23": ["14:00", "15:00"],
    "2026-09-25": ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00", "17:00"],
    "2026-09-29": ["11:00"],
}

SERVICOS = [
    {
        "codigo": "diagnostico",
        "nome": "Diagnóstico inicial",
        "duracao_min": 60,
        "modalidade": "on-line",
    },
    {
        "codigo": "acompanhamento",
        "nome": "Reunião de acompanhamento",
        "duracao_min": 30,
        "modalidade": "on-line",
    },
    {
        "codigo": "apresentacao",
        "nome": "Apresentação de escopo",
        "duracao_min": 45,
        "modalidade": "on-line ou presencial",
    },
]


def _conectar(caminho: str = ":memory:") -> sqlite3.Connection:
    conexao = sqlite3.connect(caminho, check_same_thread=False)
    conexao.row_factory = sqlite3.Row
    return conexao


def semear(conexao: sqlite3.Connection) -> None:
    """Cria e popula o banco. Determinístico: mesma entrada, mesmo banco."""
    conexao.executescript(
        """
        DROP TABLE IF EXISTS slots;
        DROP TABLE IF EXISTS reservas;
        CREATE TABLE slots (
            data TEXT NOT NULL,
            hora TEXT NOT NULL,
            livre INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (data, hora)
        );
        CREATE TABLE reservas (
            protocolo TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            email TEXT NOT NULL,
            data TEXT NOT NULL,
            hora TEXT NOT NULL,
            assunto TEXT NOT NULL,
            situacao TEXT NOT NULL DEFAULT 'confirmada',
            criada_em TEXT NOT NULL
        );
        """
    )
    for deslocamento in range(DIAS_JANELA):
        dia = INICIO_JANELA + timedelta(days=deslocamento)
        if dia.weekday() >= 5:  # agenda comercial não abre fim de semana
            continue
        iso = dia.isoformat()
        for hora in HORARIOS:
            livre = 0 if hora in OCUPADOS.get(iso, []) else 1
            conexao.execute(
                "INSERT INTO slots (data, hora, livre) VALUES (?, ?, ?)",
                (iso, hora, livre),
            )
    conexao.commit()


def _horarios_livres(conexao: sqlite3.Connection, data_iso: str) -> list:
    linhas = conexao.execute(
        "SELECT hora FROM slots WHERE data = ? AND livre = 1 ORDER BY hora",
        (data_iso,),
    ).fetchall()
    return [linha["hora"] for linha in linhas]


def _dia_existe(conexao: sqlite3.Connection, data_iso: str) -> bool:
    linha = conexao.execute(
        "SELECT COUNT(*) AS total FROM slots WHERE data = ?", (data_iso,)
    ).fetchone()
    return bool(linha["total"])


def _proximos_dias_com_vaga(
    conexao: sqlite3.Connection, a_partir_de: str, limite: int = 3
) -> list:
    linhas = conexao.execute(
        """
        SELECT data, COUNT(*) AS vagas
        FROM slots
        WHERE data > ? AND livre = 1
        GROUP BY data
        ORDER BY data
        LIMIT ?
        """,
        (a_partir_de, limite),
    ).fetchall()
    return [{"data": linha["data"], "vagas": linha["vagas"]} for linha in linhas]


def _gerar_protocolo(conexao: sqlite3.Connection) -> str:
    linha = conexao.execute("SELECT COUNT(*) AS total FROM reservas").fetchone()
    sequencial = linha["total"] + 1
    return "AG-2026-%04d" % sequencial


class ServicoAgenda:
    """Regras de negócio. Separado do HTTP para poder ser testado sozinho."""

    def __init__(self, caminho_banco: str = ":memory:") -> None:
        self.conexao = _conectar(caminho_banco)
        self.trava = threading.Lock()
        semear(self.conexao)

    def disponibilidade(self, data_iso: str, hora=None) -> dict:
        with self.trava:
            if not _dia_existe(self.conexao, data_iso):
                return {
                    "data": data_iso,
                    "dia_util": False,
                    "motivo": "fora da janela de atendimento ou fim de semana",
                    "livres": [],
                    "proximos_dias": _proximos_dias_com_vaga(self.conexao, data_iso),
                }
            livres = _horarios_livres(self.conexao, data_iso)
            corpo = {"data": data_iso, "dia_util": True, "livres": livres}
            if hora is not None:
                corpo["hora_consultada"] = hora
                corpo["disponivel"] = hora in livres
                if hora not in livres:
                    corpo["alternativas_no_dia"] = livres
                    corpo["proximos_dias"] = _proximos_dias_com_vaga(
                        self.conexao, data_iso
                    )
            return corpo

    def reservar(
        self, nome: str, email: str, data_iso: str, hora: str, assunto: str
    ) -> dict:
        with self.trava:
            livres = _horarios_livres(self.conexao, data_iso)
            if hora not in livres:
                return {
                    "erro": "horario_indisponivel",
                    "data": data_iso,
                    "hora": hora,
                    "alternativas_no_dia": livres,
                }
            protocolo = _gerar_protocolo(self.conexao)
            self.conexao.execute(
                "UPDATE slots SET livre = 0 WHERE data = ? AND hora = ?",
                (data_iso, hora),
            )
            self.conexao.execute(
                "INSERT INTO reservas "
                "(protocolo, nome, email, data, hora, assunto, situacao, criada_em) "
                "VALUES (?, ?, ?, ?, ?, ?, 'confirmada', ?)",
                (
                    protocolo,
                    nome,
                    email,
                    data_iso,
                    hora,
                    assunto,
                    datetime(2026, 9, 14, 12, 0, 0).isoformat(),
                ),
            )
            self.conexao.commit()
            return {
                "protocolo": protocolo,
                "nome": nome,
                "email": email,
                "data": data_iso,
                "hora": hora,
                "assunto": assunto,
                "situacao": "confirmada",
            }

    def consultar_reserva(self, protocolo: str):
        with self.trava:
            linha = self.conexao.execute(
                "SELECT * FROM reservas WHERE protocolo = ?", (protocolo,)
            ).fetchone()
            return dict(linha) if linha else None

    def servicos(self) -> list:
        return SERVICOS


class Manipulador(BaseHTTPRequestHandler):
    servico = None  # injetado por criar_servidor

    def _responder(self, codigo: int, corpo) -> None:
        dados = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def log_message(self, *_args) -> None:  # silencia o log padrão do http.server
        return

    def do_GET(self) -> None:  # noqa: N802 (nome exigido pela classe base)
        url = urlparse(self.path)
        parametros = parse_qs(url.query)

        if url.path == "/saude":
            return self._responder(200, {"situacao": "ok"})

        if url.path == "/catalogo/servicos":
            return self._responder(200, {"servicos": self.servico.servicos()})

        if url.path == "/agenda/disponibilidade":
            data_iso = (parametros.get("data") or [""])[0]
            if not data_iso:
                return self._responder(400, {"erro": "parametro_data_obrigatorio"})
            hora = (parametros.get("hora") or [None])[0]
            return self._responder(200, self.servico.disponibilidade(data_iso, hora))

        if url.path.startswith("/agenda/reservas/"):
            protocolo = url.path.rsplit("/", 1)[-1]
            reserva = self.servico.consultar_reserva(protocolo)
            if reserva is None:
                return self._responder(404, {"erro": "protocolo_nao_encontrado"})
            return self._responder(200, reserva)

        self._responder(404, {"erro": "rota_desconhecida"})

    def do_POST(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        if url.path != "/agenda/reservas":
            return self._responder(404, {"erro": "rota_desconhecida"})

        tamanho = int(self.headers.get("Content-Length", 0))
        try:
            corpo = json.loads(self.rfile.read(tamanho) or b"{}")
        except json.JSONDecodeError:
            return self._responder(400, {"erro": "json_invalido"})

        faltando = [
            campo
            for campo in ("nome", "email", "data", "hora", "assunto")
            if not corpo.get(campo)
        ]
        if faltando:
            return self._responder(
                400, {"erro": "campos_obrigatorios_ausentes", "campos": faltando}
            )

        resultado = self.servico.reservar(
            corpo["nome"],
            corpo["email"],
            corpo["data"],
            corpo["hora"],
            corpo["assunto"],
        )
        codigo = 409 if resultado.get("erro") else 201
        self._responder(codigo, resultado)


def criar_servidor(porta: int = 0):
    """Sobe o servidor. Porta 0 = o sistema escolhe uma livre (bom para teste)."""
    servico = ServicoAgenda()
    classe = type("ManipuladorLigado", (Manipulador,), {"servico": servico})
    servidor = ThreadingHTTPServer(("127.0.0.1", porta), classe)
    return servidor, servidor.server_address[1]


if __name__ == "__main__":
    import sys

    porta_escolhida = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    servidor_http, porta_ativa = criar_servidor(porta_escolhida)
    print("Serviço de agenda em http://127.0.0.1:%d" % porta_ativa)
    print("Rotas: /saude  /agenda/disponibilidade  /agenda/reservas  /catalogo/servicos")
    try:
        servidor_http.serve_forever()
    except KeyboardInterrupt:
        print("\nencerrado")
