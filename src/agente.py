"""Orquestrador do agente.

Pipeline de um turno, sempre nesta ordem:

    normalizar → portões → intenção → extração → (falta algo? pergunta)
              → consulta à API → resposta → auditoria de procedência

A última etapa é a que diferencia este protótipo de um que só parece funcionar.
`auditar()` varre a resposta pronta atrás de data, hora, protocolo e número, e
exige que cada um tenha vindo da mensagem do usuário ou de uma resposta da API.
Um valor que o agente produziu sozinho é reprovado ali, e não por convenção de
escrita, mas por verificação mecânica.
"""

from __future__ import annotations

import json
import re
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import portoes
from dialogo import Estado, pergunta_para
from nlu import (
    AGENDAR,
    CONSULTAR_STATUS,
    INDEFINIDA,
    INFORMACAO_SERVICO,
    NLULocal,
    extrair_resposta_direta,
)

# Valores que um texto em português carrega sem serem afirmação factual.
# Sem esta lista, a auditoria acusaria o "2026" de um exemplo de protocolo.
TOLERADOS_NA_AUDITORIA = {"2026", "0001", "1"}


class ChamadaAPI:
    def __init__(self, metodo, rota, status, corpo):
        self.metodo = metodo
        self.rota = rota
        self.status = status
        self.corpo = corpo

    def __repr__(self):
        return "%s %s → %s" % (self.metodo, self.rota, self.status)


class Resposta:
    def __init__(self, texto, intencao=None):
        self.texto = texto
        self.intencao = intencao
        self.portao = None
        self.pergunta = False
        self.campo_perguntado = None
        # A leitura que de fato alimentou este turno, já com a resposta seca
        # resolvida. Quem for exibir o turno deve ler daqui, e não reinterpretar
        # a mensagem por fora: reinterpretar não enxerga o contexto da pergunta
        # anterior e mostra "nada extraído" num turno que extraiu.
        self.leitura = None
        self.chamadas = []
        self.fatos_do_usuario = []
        self.auditoria = None

    def __str__(self):
        return self.texto


class ClienteAgenda:
    """Cliente HTTP do serviço de agenda. Toda consulta externa passa aqui."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.chamadas = []

    def _registrar(self, metodo, rota, status, corpo):
        chamada = ChamadaAPI(metodo, rota, status, corpo)
        self.chamadas.append(chamada)
        return chamada

    def _get(self, rota: str, parametros=None):
        url = self.base_url + rota
        if parametros:
            url += "?" + urlencode(parametros)
        try:
            with urlopen(Request(url, method="GET"), timeout=5) as resposta:
                corpo = json.loads(resposta.read().decode("utf-8"))
                self._registrar("GET", rota, resposta.status, corpo)
                return corpo
        except HTTPError as erro:
            corpo = json.loads(erro.read().decode("utf-8") or "{}")
            self._registrar("GET", rota, erro.code, corpo)
            return corpo
        except URLError as erro:
            self._registrar("GET", rota, "falha", {"erro": str(erro.reason)})
            return {"erro": "servico_indisponivel"}

    def _post(self, rota: str, payload: dict):
        url = self.base_url + rota
        dados = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        requisicao = Request(
            url, data=dados, method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        try:
            with urlopen(requisicao, timeout=5) as resposta:
                corpo = json.loads(resposta.read().decode("utf-8"))
                self._registrar("POST", rota, resposta.status, corpo)
                return corpo
        except HTTPError as erro:
            corpo = json.loads(erro.read().decode("utf-8") or "{}")
            self._registrar("POST", rota, erro.code, corpo)
            return corpo
        except URLError as erro:
            self._registrar("POST", rota, "falha", {"erro": str(erro.reason)})
            return {"erro": "servico_indisponivel"}

    def disponibilidade(self, data_iso, hora=None):
        parametros = {"data": data_iso}
        if hora:
            parametros["hora"] = hora
        return self._get("/agenda/disponibilidade", parametros)

    def reservar(self, payload):
        return self._post("/agenda/reservas", payload)

    def consultar_reserva(self, protocolo):
        return self._get("/agenda/reservas/" + protocolo)

    def servicos(self):
        return self._get("/catalogo/servicos")


def _valores_verificaveis(texto: str) -> set:
    """Extrai da resposta tudo que é afirmação sobre o mundo.

    Datas, horas, protocolos e números soltos. É o conjunto que precisa ter
    origem rastreável.
    """
    achados = set()
    achados.update(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", texto))
    achados.update(re.findall(r"\b\d{1,2}:\d{2}\b", texto))
    achados.update(re.findall(r"\bAG-\d{4}-\d{4}\b", texto))
    achados.update(re.findall(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", texto))
    achados.update(re.findall(r"\b\d+\b", texto))
    return achados


def _valores_de_origem(chamadas, fatos_do_usuario) -> set:
    """Tudo que o agente tem direito de afirmar: API + o que o usuário disse."""
    permitidos = set()

    for chamada in chamadas:
        serializado = json.dumps(chamada.corpo, ensure_ascii=False)
        permitidos.update(_valores_verificaveis(serializado))

    for fato in fatos_do_usuario:
        permitidos.update(_valores_verificaveis(str(fato)))

    return permitidos


def auditar(resposta: Resposta) -> dict:
    """Portão de realidade aplicado à saída.

    Reprova qualquer valor no texto que não apareça na resposta da API nem no
    que o usuário escreveu. É a verificação que impede a alucinação de horário
    disponível, de protocolo e de data.
    """
    afirmados = _valores_verificaveis(resposta.texto)
    permitidos = _valores_de_origem(resposta.chamadas, resposta.fatos_do_usuario)

    sem_origem = sorted(
        valor
        for valor in afirmados
        if valor not in permitidos and valor not in TOLERADOS_NA_AUDITORIA
    )
    return {
        "valores_afirmados": sorted(afirmados),
        "sem_origem": sem_origem,
        "aprovada": not sem_origem,
    }


class Agente:
    def __init__(self, cliente: ClienteAgenda, nlu=None):
        self.cliente = cliente
        self.nlu = nlu or NLULocal()

    # ------------------------------------------------------------------ turno

    def processar(self, mensagem: str, estado: Estado) -> Resposta:
        estado.historico.append(("usuario", mensagem))

        if estado.encerrada:
            resposta = Resposta("A conversa foi encerrada a seu pedido.")
            resposta.portao = "opt_out"
            return self._finalizar(resposta, estado, [])

        portao = portoes.verificar(mensagem)
        if portao.bloqueia:
            if portao.tipo == "opt_out":
                estado.encerrada = True
            resposta = Resposta(portao.resposta, estado.intencao)
            resposta.portao = "%s:%s" % (portao.tipo, portao.detalhe)
            return self._finalizar(resposta, estado, [])

        leitura = self.nlu.interpretar(mensagem, estado.hoje)

        # Se o turno anterior perguntou por um campo e a leitura normal não o
        # encontrou, relê a mensagem como resposta àquela pergunta.
        if estado.aguardando:
            campo = leitura.campos.get(estado.aguardando)
            if campo is None or not campo.ok:
                direto = extrair_resposta_direta(
                    estado.aguardando, mensagem, estado.hoje
                )
                if direto.ok:
                    leitura.campos[estado.aguardando] = direto

        if leitura.intencao != INDEFINIDA:
            estado.intencao = leitura.intencao
        estado.mesclar(leitura.campos)
        self._leitura_do_turno = leitura

        if estado.intencao is None:
            resposta = Resposta(
                "Consigo ajudar com três coisas: marcar uma reunião, consultar "
                "uma reunião já marcada pelo protocolo, ou explicar os tipos de "
                "atendimento. Qual delas você precisa?",
                INDEFINIDA,
            )
            resposta.pergunta = True
            if portao.tipo == "injecao":
                resposta.portao = "injecao:instrucao_ignorada"
            return self._finalizar(resposta, estado, [])

        antes = len(self.cliente.chamadas)

        if estado.intencao == AGENDAR:
            resposta = self._fluxo_agendamento(estado)
        elif estado.intencao == CONSULTAR_STATUS:
            resposta = self._fluxo_status(estado)
        else:
            resposta = self._fluxo_servicos(estado)

        if portao.tipo == "injecao":
            resposta.portao = "injecao:instrucao_ignorada"

        return self._finalizar(resposta, estado, self.cliente.chamadas[antes:])

    def _finalizar(self, resposta: Resposta, estado: Estado, chamadas) -> Resposta:
        resposta.chamadas = chamadas
        resposta.fatos_do_usuario = [
            campo.origem for campo in estado.campos.values() if campo.ok
        ]
        resposta.leitura = getattr(self, "_leitura_do_turno", None)
        self._leitura_do_turno = None
        resposta.auditoria = auditar(resposta)
        estado.aguardando = resposta.campo_perguntado
        estado.historico.append(("agente", resposta.texto))
        return resposta

    # ----------------------------------------------------------------- fluxos

    def _fluxo_agendamento(self, estado: Estado) -> Resposta:
        data = estado.campo("data")
        hora = estado.campo("hora")

        if not data.ok:
            resposta = Resposta(pergunta_para(data), AGENDAR)
            resposta.pergunta = True
            resposta.campo_perguntado = "data"
            return resposta

        # A partir daqui existe data: dá para consultar a agenda de verdade.
        if not hora.ok:
            disponibilidade = self.cliente.disponibilidade(data.valor)
            if not disponibilidade.get("dia_util", False):
                proximos = disponibilidade.get("proximos_dias", [])
                if proximos:
                    dias = ", ".join(item["data"] for item in proximos)
                    texto = (
                        "Em %s não temos atendimento. Os próximos dias com agenda "
                        "aberta são: %s. Qual deles serve?" % (data.valor, dias)
                    )
                else:
                    texto = (
                        "Em %s não temos atendimento e não encontrei outro dia "
                        "aberto na janela consultada." % data.valor
                    )
                resposta = Resposta(texto, AGENDAR)
                resposta.pergunta = True
                resposta.campo_perguntado = "data"
                estado.campos.pop("data", None)
                return resposta

            livres = disponibilidade.get("livres", [])
            livres_filtrados = self._filtrar_por_periodo(livres, hora.nota)
            if not livres_filtrados:
                livres_filtrados = livres

            if not livres:
                resposta = Resposta(
                    "O dia %s está sem horário livre. Quer que eu veja outro dia?"
                    % data.valor,
                    AGENDAR,
                )
                resposta.pergunta = True
                resposta.campo_perguntado = "data"
                estado.campos.pop("data", None)
                return resposta

            contexto = {"livres_no_dia": livres_filtrados, "data": data.valor}
            resposta = Resposta(pergunta_para(hora, contexto), AGENDAR)
            resposta.pergunta = True
            resposta.campo_perguntado = "hora"
            return resposta

        # Data e hora presentes: confere o horário exato antes de qualquer promessa.
        checagem = self.cliente.disponibilidade(data.valor, hora.valor)
        if not checagem.get("disponivel", False):
            alternativas = checagem.get("alternativas_no_dia", [])
            if alternativas:
                texto = (
                    "O horário %s do dia %s já está ocupado. Nesse mesmo dia estão "
                    "livres: %s. Algum desses serve?"
                    % (hora.valor, data.valor, ", ".join(alternativas))
                )
            else:
                proximos = checagem.get("proximos_dias", [])
                dias = ", ".join(item["data"] for item in proximos)
                texto = (
                    "O dia %s está totalmente ocupado. Os próximos dias com vaga "
                    "são: %s. Qual prefere?" % (data.valor, dias)
                ) if proximos else (
                    "O dia %s está totalmente ocupado e não encontrei outro dia na "
                    "janela consultada." % data.valor
                )
            resposta = Resposta(texto, AGENDAR)
            resposta.pergunta = True
            resposta.campo_perguntado = "hora"
            # O horário pedido não vale mais: volta a ser lacuna, não fica pendurado.
            estado.campos.pop("hora", None)
            return resposta

        pendentes = estado.pendentes()
        if pendentes:
            proximo = estado.campo(pendentes[0])
            resposta = Resposta(
                "O horário %s do dia %s está livre. %s"
                % (hora.valor, data.valor, pergunta_para(proximo)),
                AGENDAR,
            )
            resposta.pergunta = True
            resposta.campo_perguntado = proximo.nome
            return resposta

        reserva = self.cliente.reservar(
            {
                "nome": estado.campo("nome").valor,
                "email": estado.campo("email").valor,
                "data": data.valor,
                "hora": hora.valor,
                "assunto": estado.campo("assunto").valor,
            }
        )

        if reserva.get("erro"):
            return Resposta(
                "Não consegui concluir a reserva: o serviço devolveu %r. "
                "Prefiro não confirmar nada que não tenha sido registrado."
                % reserva["erro"],
                AGENDAR,
            )

        return Resposta(
            "Reunião confirmada.\n"
            "Protocolo: %s\n"
            "Quando: %s às %s\n"
            "Em nome de: %s\n"
            "Confirmação enviada para: %s\n"
            "Assunto: %s"
            % (
                reserva["protocolo"],
                reserva["data"],
                reserva["hora"],
                reserva["nome"],
                reserva["email"],
                reserva["assunto"],
            ),
            AGENDAR,
        )

    def _fluxo_status(self, estado: Estado) -> Resposta:
        protocolo = estado.campo("protocolo")
        if not protocolo.ok:
            resposta = Resposta(pergunta_para(protocolo), CONSULTAR_STATUS)
            resposta.pergunta = True
            resposta.campo_perguntado = "protocolo"
            return resposta

        reserva = self.cliente.consultar_reserva(protocolo.valor)
        if reserva.get("erro"):
            resposta = Resposta(
                "Não encontrei nenhuma reunião com o protocolo %s. "
                "Pode conferir o número?" % protocolo.valor,
                CONSULTAR_STATUS,
            )
            resposta.pergunta = True
            return resposta

        return Resposta(
            "Protocolo %s: reunião %s para %s às %s, em nome de %s. Assunto: %s."
            % (
                reserva["protocolo"],
                reserva["situacao"],
                reserva["data"],
                reserva["hora"],
                reserva["nome"],
                reserva["assunto"],
            ),
            CONSULTAR_STATUS,
        )

    def _fluxo_servicos(self, estado: Estado) -> Resposta:
        catalogo = self.cliente.servicos()
        itens = catalogo.get("servicos", [])
        if not itens:
            return Resposta(
                "Não consegui carregar o catálogo agora. Prefiro não descrever de "
                "memória. Tente de novo em instantes.",
                INFORMACAO_SERVICO,
            )
        linhas = [
            "- %s: %s min, %s" % (item["nome"], item["duracao_min"], item["modalidade"])
            for item in itens
        ]
        return Resposta(
            "Os tipos de atendimento disponíveis são:\n%s\n\nQuer marcar algum?"
            % "\n".join(linhas),
            INFORMACAO_SERVICO,
        )

    @staticmethod
    def _filtrar_por_periodo(livres, periodo):
        """Filtra horários reais por um período vago dito pelo usuário.

        Note que o filtro é aplicado a uma lista que **veio da API**. O período
        vago restringe o que já é verdade; ele nunca cria horário.
        """
        if not periodo:
            return livres
        faixas = {
            "manhã": lambda h: h < "12:00",
            "tarde": lambda h: "12:00" <= h < "18:00",
            "fim da tarde": lambda h: "16:00" <= h < "19:00",
            "noite": lambda h: h >= "18:00",
        }
        teste = faixas.get(periodo)
        return [h for h in livres if teste(h)] if teste else livres


def criar_estado(hoje=None) -> Estado:
    return Estado(hoje or date.today())
