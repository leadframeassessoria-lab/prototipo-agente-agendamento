"""Gerência de diálogo: o que ainda falta e qual pergunta fazer.

Duas regras herdadas da operação real e mantidas aqui:

- **Uma pergunta por mensagem.** Três perguntas numa mensagem só viram uma
  resposta, e quase sempre a menos útil.
- **A pergunta é a que destrava mais.** Sem data e hora não dá para consultar
  a agenda; sem consultar a agenda, qualquer horário que o agente citasse
  seria invenção. Então data e hora vêm antes de nome e e-mail.
"""

from __future__ import annotations

from datetime import date

from nlu import LACUNA, PARCIAL, PREENCHIDO, Campo

# Ordem = prioridade. O primeiro campo não resolvido vira a pergunta do turno.
OBRIGATORIOS = {
    "agendar_reuniao": ["data", "hora", "nome", "email", "assunto"],
    "consultar_status": ["protocolo"],
    "informacao_servico": [],
}


class Estado:
    """Memória da conversa. Sem isto o protótipo repete a mesma pergunta."""

    def __init__(self, hoje: date):
        self.hoje = hoje
        self.intencao = None
        self.campos = {}
        self.encerrada = False
        self.historico = []
        # Qual campo o turno anterior perguntou. É o que permite ler uma
        # resposta seca ("Maria Souza") como resposta àquela pergunta.
        self.aguardando = None

    def mesclar(self, campos: dict) -> None:
        """Junta a leitura do turno com o que já se sabia.

        Um valor confirmado nunca é apagado por um turno que não falou dele;
        mas um valor novo substitui o antigo, porque a pessoa tem o direito de
        se corrigir no meio da conversa.
        """
        for nome, campo in campos.items():
            atual = self.campos.get(nome)
            if campo.estado == PREENCHIDO:
                self.campos[nome] = campo
            elif campo.estado == PARCIAL and (atual is None or not atual.ok):
                self.campos[nome] = campo
            elif atual is None:
                self.campos[nome] = campo

    def campo(self, nome: str) -> Campo:
        return self.campos.get(nome) or Campo(nome)

    def pendentes(self) -> list:
        exigidos = OBRIGATORIOS.get(self.intencao, [])
        return [nome for nome in exigidos if not self.campo(nome).ok]

    def resumo_lacunas(self) -> list:
        """Lista legível do que falta, usada no relatório e não na conversa."""
        linhas = []
        for nome in OBRIGATORIOS.get(self.intencao, []):
            campo = self.campo(nome)
            if campo.ok:
                linhas.append("%s = %s (origem: %r)" % (nome, campo.valor, campo.origem))
            elif campo.estado == PARCIAL:
                linhas.append("%s = PARCIAL (%s)" % (nome, campo.nota))
            else:
                linhas.append("%s = LACUNA" % nome)
        return linhas


PERGUNTAS_BASE = {
    "data": "Para qual dia você quer marcar?",
    "hora": "Qual horário fica melhor para você?",
    "nome": "Em nome de quem eu registro?",
    "email": "Qual e-mail eu uso para enviar a confirmação?",
    "assunto": "Qual o assunto da conversa, em uma linha?",
    "protocolo": "Me passa o número do protocolo? Ele tem o formato AG-2026-0001.",
}


def pergunta_para(campo: Campo, contexto=None) -> str:
    """Monta a pergunta do turno.

    Quando há contexto vindo da API (horários realmente livres), a pergunta
    passa a oferecer opções. Quando não há, ela continua aberta, porque nunca
    sugerimos horário que não foi confirmado pela agenda.
    """
    contexto = contexto or {}

    if campo.nome == "data" and campo.estado == PARCIAL:
        return (
            "Consigo sim em %s. Me diz o dia exato, por favor, "
            "assim eu confiro a agenda antes de reservar." % campo.nota
        )

    if campo.nome == "hora":
        livres = contexto.get("livres_no_dia")
        periodo = campo.nota if campo.estado == PARCIAL else None

        if livres:
            lista = ", ".join(livres)
            if periodo:
                return (
                    "No dia %s, de %s, tenho estes horários livres: %s. "
                    "Qual deles fica melhor?" % (contexto.get("data"), periodo, lista)
                )
            return (
                "No dia %s tenho estes horários livres: %s. Qual você prefere?"
                % (contexto.get("data"), lista)
            )

        if periodo:
            return (
                "Anotei %s. Para eu conferir a agenda certo, me diz o horário. "
                "pode ser aproximado, tipo 15h." % periodo
            )

    return PERGUNTAS_BASE.get(campo.nome, "Pode me dar mais um detalhe?")
