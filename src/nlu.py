"""Interpretação: classificação de intenção + extração de informação.

Duas decisões de projeto sustentam o resto do protótipo:

**1. Todo campo carrega procedência.** Um `Campo` nunca é só um valor: ele diz
de onde o valor veio (`origem`) e em que estado está. São três estados, não
dois, e o terceiro é o que impede o protótipo de inventar dado:

- `PREENCHIDO`: valor extraído, com o trecho de origem guardado
- `LACUNA`:     não foi dito; é ausência declarada, não campo vazio
- `PARCIAL`:    foi dito algo que *não chega* a ser o valor ("de tarde" não é
                 um horário). Vira pergunta, nunca vira chute.

**2. Confiança baixa não é intenção.** Abaixo do limiar, a intenção é
`INDEFINIDA` e o agente pergunta, em vez de escolher a hipótese mais provável.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from normalizacao import contem_termo, normalizar

PREENCHIDO = "preenchido"
LACUNA = "lacuna"
PARCIAL = "parcial"

AGENDAR = "agendar_reuniao"
CONSULTAR_STATUS = "consultar_status"
INFORMACAO_SERVICO = "informacao_servico"
INDEFINIDA = "indefinida"

LIMIAR_CONFIANCA = 0.34

# Peso por termo: termo que só aparece numa intenção vale mais que termo que
# aparece em várias. "protocolo" decide sozinho; "reuniao" não.
PESOS_INTENCAO = {
    AGENDAR: [
        ("agendar", 3),
        ("marcar", 3),
        ("marcar reuniao", 4),
        ("remarcar", 3),
        ("reuniao", 2),
        ("conversa", 1),
        ("horario", 2),
        ("disponibilidade", 2),
        ("agenda", 2),
        ("encontro", 2),
    ],
    CONSULTAR_STATUS: [
        ("protocolo", 4),
        ("status", 3),
        ("situacao", 2),
        ("consultar", 2),
        ("confirmada", 2),
        ("minha reuniao", 3),
        ("ja agendei", 3),
    ],
    INFORMACAO_SERVICO: [
        ("quais servicos", 4),
        ("o que voces fazem", 4),
        ("como funciona", 3),
        ("servicos", 2),
        ("duracao", 2),
        ("modalidade", 2),
        ("informacao", 1),
    ],
}

MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11,
    "dezembro": 12,
}

DIAS_SEMANA = {
    "segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4,
    "sabado": 5, "domingo": 6,
}

# Expressões que parecem horário e não são. Existem para virar `PARCIAL`.
PERIODOS_VAGOS = {
    "de manha": "manhã",
    "pela manha": "manhã",
    "de tarde": "tarde",
    "a tarde": "tarde",
    "pela tarde": "tarde",
    "fim da tarde": "fim da tarde",
    "de noite": "noite",
}

PADRAO_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PADRAO_PROTOCOLO = re.compile(r"\bAG-\d{4}-\d{4}\b", re.I)

# A introdução ("meu nome é", "poe no nome de") é casada sem diferenciar
# maiúscula; o **nome capturado**, não. É essa assimetria que faz a captura
# parar sozinha na primeira palavra minúscula seguinte. Sem ela, "poe no nome
# de Joao Pedro meu email eh ..." viraria um nome de quatro palavras.
PADROES_NOME = [
    re.compile(r"(?i:meu nome (?:é|eh|e)|me chamo)\s+([A-ZÀ-Ý][\wÀ-ÿ]+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ]+){0,2})"),
    re.compile(r"(?i:sou)\s+(?i:a|o)?\s*([A-ZÀ-Ý][\wÀ-ÿ]+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ]+){0,2})"),
    re.compile(r"(?i:no nome de|em nome de|p[oó]e no nome de)\s+([A-ZÀ-Ý][\wÀ-ÿ]+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ]+){0,2})"),
    re.compile(r"(?i:aqui (?:é|eh|e))\s+([A-ZÀ-Ý][\wÀ-ÿ]+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ]+){0,2})"),
]

PADROES_ASSUNTO = [
    re.compile(r"(?:sobre|a respeito de|assunto[:\s]|para (?:falar|tratar) (?:de|sobre)|pra (?:falar|tratar) (?:de|sobre))\s+(.{3,60}?)(?:[.,;!?]|$)", re.I),
]


class Campo:
    """Um valor com procedência. Nunca só o valor."""

    def __init__(self, nome: str, valor=None, origem=None, estado: str = LACUNA, nota=None):
        self.nome = nome
        self.valor = valor
        self.origem = origem
        self.estado = estado
        self.nota = nota

    @property
    def ok(self) -> bool:
        return self.estado == PREENCHIDO

    def __repr__(self) -> str:
        if self.estado == PREENCHIDO:
            return "Campo(%s=%r ← %r)" % (self.nome, self.valor, self.origem)
        if self.estado == PARCIAL:
            return "Campo(%s=PARCIAL %r)" % (self.nome, self.nota)
        return "Campo(%s=LACUNA)" % self.nome


class Interpretacao:
    def __init__(self, intencao, confianca, campos, evidencias):
        self.intencao = intencao
        self.confianca = confianca
        self.campos = campos
        self.evidencias = evidencias


def classificar(texto_normalizado: str):
    """Devolve (intencao, confianca, evidencias).

    A confiança é a fatia do peso total que a intenção vencedora levou. Isso
    torna "empate entre duas intenções" um número baixo, não um desempate
    arbitrário, e empate baixo vira pergunta.
    """
    pontos = {}
    evidencias = {}
    for intencao, termos in PESOS_INTENCAO.items():
        soma = 0
        achados = []
        for termo, peso in termos:
            if contem_termo(texto_normalizado, termo):
                soma += peso
                achados.append(termo)
        pontos[intencao] = soma
        evidencias[intencao] = achados

    total = sum(pontos.values())
    if total == 0:
        return INDEFINIDA, 0.0, {}

    vencedora = max(pontos, key=lambda chave: pontos[chave])
    confianca = pontos[vencedora] / total
    if confianca < LIMIAR_CONFIANCA:
        return INDEFINIDA, confianca, evidencias

    return vencedora, confianca, {"termos": evidencias[vencedora]}


def extrair_data(texto_normalizado: str, hoje: date) -> Campo:
    # 1. Data explícita: 22/09, 22/09/2026, 22-09
    achado = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", texto_normalizado)
    if achado:
        dia, mes = int(achado.group(1)), int(achado.group(2))
        ano = int(achado.group(3)) if achado.group(3) else hoje.year
        if ano < 100:
            ano += 2000
        try:
            valor = date(ano, mes, dia)
        except ValueError:
            return Campo("data", estado=PARCIAL, nota="data inválida: %s" % achado.group(0))
        return Campo("data", valor.isoformat(), achado.group(0), PREENCHIDO)

    # 2. "dia 22 de setembro" ou "dia 22"
    achado = re.search(r"\bdia (\d{1,2})(?:\s+de\s+(\w+))?\b", texto_normalizado)
    if achado:
        dia = int(achado.group(1))
        mes = MESES.get(achado.group(2) or "", hoje.month)
        try:
            valor = date(hoje.year, mes, dia)
        except ValueError:
            return Campo("data", estado=PARCIAL, nota="data inválida: %s" % achado.group(0))
        return Campo("data", valor.isoformat(), achado.group(0), PREENCHIDO)

    # 3. Relativas
    if contem_termo(texto_normalizado, "depois de amanha"):
        return Campo("data", (hoje + timedelta(days=2)).isoformat(), "depois de amanhã", PREENCHIDO)
    if contem_termo(texto_normalizado, "amanha"):
        return Campo("data", (hoje + timedelta(days=1)).isoformat(), "amanhã", PREENCHIDO)
    if contem_termo(texto_normalizado, "hoje"):
        return Campo("data", hoje.isoformat(), "hoje", PREENCHIDO)

    # 4. Dia da semana → próxima ocorrência estritamente futura
    for nome, indice in DIAS_SEMANA.items():
        if contem_termo(texto_normalizado, nome):
            adiante = (indice - hoje.weekday()) % 7 or 7
            return Campo("data", (hoje + timedelta(days=adiante)).isoformat(), nome, PREENCHIDO)

    # 5. "semana que vem": período, não data. Vira pergunta.
    if contem_termo(texto_normalizado, "semana que vem") or contem_termo(
        texto_normalizado, "proxima semana"
    ):
        return Campo("data", estado=PARCIAL, nota="semana que vem")

    return Campo("data")


def extrair_hora(texto_normalizado: str) -> Campo:
    # 14:00 / 14h30 / 14h / às 14
    achado = re.search(r"\b(\d{1,2})\s*(?::|h)\s*(\d{2})?\b", texto_normalizado)
    if achado:
        hora = int(achado.group(1))
        minuto = int(achado.group(2) or 0)
        if 0 <= hora <= 23 and 0 <= minuto <= 59:
            return Campo("hora", "%02d:%02d" % (hora, minuto), achado.group(0).strip(), PREENCHIDO)

    achado = re.search(r"\b(?:as|às)\s+(\d{1,2})\b", texto_normalizado)
    if achado:
        hora = int(achado.group(1))
        if 0 <= hora <= 23:
            return Campo("hora", "%02d:00" % hora, achado.group(0), PREENCHIDO)

    # Período vago: foi dito algo, mas não é horário. Este é o caso que mais
    # importa: o protótipo sabe que sabe *menos* do que parece.
    for termo, rotulo in PERIODOS_VAGOS.items():
        if contem_termo(texto_normalizado, termo):
            return Campo("hora", estado=PARCIAL, nota=rotulo)

    return Campo("hora")


def extrair_nome(texto_original: str) -> Campo:
    for padrao in PADROES_NOME:
        achado = padrao.search(texto_original)
        if achado:
            bruto = achado.group(1).strip(" .,;")
            # Descarta captura que pegou palavra funcional em vez de nome.
            if bruto.lower() in {"o", "a", "um", "uma", "de", "da", "do"}:
                continue
            return Campo("nome", bruto, achado.group(0).strip(), PREENCHIDO)
    return Campo("nome")


def extrair_email(texto_original: str) -> Campo:
    achado = PADRAO_EMAIL.search(texto_original)
    if achado:
        return Campo("email", achado.group(0), achado.group(0), PREENCHIDO)
    return Campo("email")


def extrair_assunto(texto_original: str) -> Campo:
    for padrao in PADROES_ASSUNTO:
        achado = padrao.search(texto_original)
        if achado:
            bruto = achado.group(1).strip(" .,;")
            if len(bruto) < 3:
                continue
            return Campo("assunto", bruto, achado.group(0).strip(), PREENCHIDO)
    return Campo("assunto")


def extrair_resposta_direta(campo_esperado: str, texto_original: str, hoje: date) -> Campo:
    """Lê uma mensagem como resposta à pergunta que o agente acabou de fazer.

    Os extratores acima precisam de uma introdução ("meu nome é X", "sobre Y").
    Isso funciona numa mensagem que a pessoa escreve por conta própria e falha
    no caso mais comum de todos: perguntada "em nome de quem eu registro?", ela
    responde "Maria Souza" e mais nada.

    Sem esta função o agente repete a mesma pergunta para sempre. Ela só é
    chamada quando o turno anterior perguntou por um campo específico, então o
    contexto que autoriza a leitura é o próprio turno.
    """
    texto = texto_original.strip()
    if not texto or texto.startswith("/"):
        return Campo(campo_esperado)

    normalizado = normalizar(texto)

    if campo_esperado == "nome":
        # Uma data ou hora solta não é nome, mesmo que a pergunta tenha sido
        # sobre nome. Quem responde "quinta" está corrigindo o dia, não se
        # apresentando.
        if extrair_data(normalizado, hoje).ok or extrair_hora(normalizado).ok:
            return Campo("nome")
        if PADRAO_EMAIL.search(texto):
            return Campo("nome")
        partes = texto.strip(" .,;!?").split()
        if not 1 <= len(partes) <= 4:
            return Campo("nome")
        if not all(re.fullmatch(r"[A-Za-zÀ-ÿ'\-]+", parte) for parte in partes):
            return Campo("nome")
        return Campo("nome", " ".join(partes), texto, PREENCHIDO)

    if campo_esperado == "assunto":
        limpo = texto.strip(" .,;!?")
        if len(limpo) < 3 or len(limpo) > 120:
            return Campo("assunto")
        if PADRAO_EMAIL.search(texto):
            return Campo("assunto")
        return Campo("assunto", limpo, texto, PREENCHIDO)

    return Campo(campo_esperado)


def extrair_protocolo(texto_original: str) -> Campo:
    achado = PADRAO_PROTOCOLO.search(texto_original)
    if achado:
        return Campo("protocolo", achado.group(0).upper(), achado.group(0), PREENCHIDO)
    return Campo("protocolo")


class NLULocal:
    """Interpretador determinístico. Roda offline, sem chave e sem rede.

    É o padrão do protótipo por um motivo prático: um avaliador precisa
    conseguir rodar o teste. O adaptador de LLM em `nlu_llm.py` implementa a
    mesma interface e usa o prompt de `prompts/sistema.md`.
    """

    nome = "local-deterministico"

    def interpretar(self, mensagem: str, hoje: date) -> Interpretacao:
        texto = normalizar(mensagem)
        intencao, confianca, evidencias = classificar(texto)

        campos = {
            "nome": extrair_nome(mensagem),
            "email": extrair_email(mensagem),
            "data": extrair_data(texto, hoje),
            "hora": extrair_hora(texto),
            "assunto": extrair_assunto(mensagem),
            "protocolo": extrair_protocolo(mensagem),
        }
        return Interpretacao(intencao, confianca, campos, evidencias)
