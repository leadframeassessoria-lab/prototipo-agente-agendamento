"""Normalização de português informal.

Mensagem real não chega escrita como no conjunto de teste: chega sem acento,
abreviada, com erro de digitação. Esta camada existe para que a classificação
de intenção não dependa de o usuário escrever certo.

Regra que vale para o módulo inteiro: normalizar serve para **encontrar**,
nunca para **exibir**. O texto original é sempre preservado, porque o que o
usuário escreveu é a fonte do nome, do e-mail e do assunto.
"""

from __future__ import annotations

import re
import unicodedata

# Vocabulário informal de português brasileiro. Cada linha é um caso que
# apareceu em teste, não uma lista genérica copiada de dicionário.
GIRIAS = {
    "vc": "voce",
    "vcs": "voces",
    "vcês": "voces",
    "qria": "queria",
    "qro": "quero",
    "qdo": "quando",
    "qnta": "quinta",
    "qnt": "quanta",
    "pfv": "por favor",
    "pfvr": "por favor",
    "blz": "beleza",
    "eae": "e ai",
    "eai": "e ai",
    "hj": "hoje",
    "amanha": "amanha",
    "amnh": "amanha",
    "tb": "tambem",
    "tbm": "tambem",
    "pq": "porque",
    "eh": "e",
    "ta": "esta",
    "tá": "esta",
    "to": "estou",
    "msg": "mensagem",
    "reuniao": "reuniao",
    "reuniaum": "reuniao",
    "mkt": "marketing",
    "add": "adicionar",
    "flw": "falou",
    "vlw": "valeu",
    "obg": "obrigado",
    "n": "nao",
    "naum": "nao",
    "ngm": "ninguem",
    "cmg": "comigo",
    "atd": "atendimento",
    "hr": "hora",
    "hrs": "horas",
    "dps": "depois",
    "agnd": "agendar",
    "agnda": "agenda",
}

# Erros de digitação frequentes que a distância de edição sozinha resolveria
# errado, porque a forma errada está perto de mais de uma palavra válida.
CORRECOES_DIRETAS = {
    "marca": "marcar",
    "agenda": "agendar",
    "agendamento": "agendar",
    "remarcar": "remarcar",
    "conversar": "conversar",
    "papo": "conversa",
}


def remover_acentos(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


def normalizar(texto: str) -> str:
    """Devolve a forma usada para *busca*. Nunca use para exibir ao usuário."""
    base = remover_acentos(texto.lower())
    base = re.sub(r"[^\w@.:/\-]+", " ", base)
    base = re.sub(r"\s+", " ", base).strip()

    palavras = []
    for palavra in base.split(" "):
        expandida = GIRIAS.get(palavra, palavra)
        palavras.append(CORRECOES_DIRETAS.get(expandida, expandida))
    return " ".join(palavras)


def distancia_edicao(a: str, b: str) -> int:
    """Levenshtein iterativo. Curto de propósito: é usado em palavra, não em texto."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    anterior = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        atual = [i]
        for j, char_b in enumerate(b, start=1):
            custo = 0 if char_a == char_b else 1
            atual.append(
                min(anterior[j] + 1, atual[j - 1] + 1, anterior[j - 1] + custo)
            )
        anterior = atual
    return anterior[-1]


def _tolerancia(alvo: str) -> int:
    """Palavra curta não aceita erro; palavra longa aceita mais.

    Sem isto, `nao` casaria com `mao`, `pao` e `dao`, e a classificação viraria
    sorteio. O limite por tamanho é o que separa tolerância de ruído.
    """
    if len(alvo) <= 4:
        return 0
    if len(alvo) <= 7:
        return 1
    return 2


def parecido(palavra: str, alvo: str) -> bool:
    return distancia_edicao(palavra, alvo) <= _tolerancia(alvo)


def contem_termo(texto_normalizado: str, termo: str) -> bool:
    """Casa termo de uma ou mais palavras, tolerando erro de digitação.

    Termo com espaço é procurado como sequência; termo de uma palavra é
    procurado token a token. Os dois toleram erro proporcional ao tamanho.
    """
    tokens = texto_normalizado.split(" ")
    partes = termo.split(" ")

    if len(partes) == 1:
        return any(parecido(token, termo) for token in tokens)

    for inicio in range(len(tokens) - len(partes) + 1):
        janela = tokens[inicio : inicio + len(partes)]
        if all(parecido(t, p) for t, p in zip(janela, partes)):
            return True
    return False
