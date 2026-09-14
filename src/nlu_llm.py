"""Adaptador de LLM com a mesma interface do `NLULocal`.

Troca só a camada de interpretação. Portões, diálogo, consulta à agenda e
auditoria de procedência continuam idênticos, porque o modelo **não escreve a
resposta final**. Ele preenche um formulário de seis campos.

Opcional por projeto: o protótipo roda por padrão sem chave, sem rede e sem
custo. Este arquivo existe para mostrar que a arquitetura não depende de qual
das duas implementações está plugada.

Uso:

    pip install anthropic
    export ANTHROPIC_API_KEY=...        # ou `ant auth login`
    python demo_conversa.py --llm
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from nlu import LACUNA, PARCIAL, PREENCHIDO, Campo, Interpretacao

MODELO = "claude-opus-5"

CAMPOS = ["nome", "email", "data", "hora", "assunto", "protocolo"]

_ESQUEMA_CAMPO = {
    "type": "object",
    "properties": {
        "estado": {"type": "string", "enum": [PREENCHIDO, LACUNA, PARCIAL]},
        "valor": {"type": ["string", "null"]},
        "origem": {"type": ["string", "null"]},
        "nota": {"type": ["string", "null"]},
    },
    "required": ["estado", "valor", "origem", "nota"],
    "additionalProperties": False,
}

ESQUEMA = {
    "type": "object",
    "properties": {
        "intencao": {
            "type": "string",
            "enum": [
                "agendar_reuniao",
                "consultar_status",
                "informacao_servico",
                "indefinida",
            ],
        },
        "confianca": {"type": "number"},
        "instrucao_embutida": {"type": "boolean"},
        "campos": {
            "type": "object",
            "properties": {nome: _ESQUEMA_CAMPO for nome in CAMPOS},
            "required": CAMPOS,
            "additionalProperties": False,
        },
    },
    "required": ["intencao", "confianca", "instrucao_embutida", "campos"],
    "additionalProperties": False,
}


def carregar_prompt(caminho=None) -> str:
    """Lê o prompt do arquivo, não de uma string no código.

    O prompt é um artefato revisável: quem for auditar o projeto lê
    `prompts/sistema.md` e vê exatamente o que o modelo recebe.
    """
    caminho = caminho or Path(__file__).parent.parent / "prompts" / "sistema.md"
    texto = Path(caminho).read_text(encoding="utf-8")
    bloco = re.search(r"````text\n(.*?)\n````", texto, re.S)
    if not bloco:
        raise ValueError("bloco do prompt não encontrado em %s" % caminho)
    return bloco.group(1).strip()


class NLULLM:
    """Interpretação por modelo, com saída forçada a esquema JSON."""

    nome = "claude-opus-5"

    def __init__(self, cliente=None, modelo: str = MODELO):
        if cliente is None:
            try:
                import anthropic
            except ImportError as erro:  # pragma: no cover - caminho opcional
                raise RuntimeError(
                    "o adaptador de LLM precisa do pacote `anthropic`: "
                    "pip install anthropic. Ou rode o protótipo no modo padrão, "
                    "que não usa modelo nenhum"
                ) from erro
            cliente = anthropic.Anthropic()
        self.cliente = cliente
        self.modelo = modelo
        self.prompt = carregar_prompt()

    def interpretar(self, mensagem: str, hoje: date) -> Interpretacao:
        resposta = self.cliente.messages.create(
            model=self.modelo,
            max_tokens=2000,
            system=self.prompt,
            messages=[
                {
                    "role": "user",
                    "content": "HOJE: %s\n\nMensagem:\n%s" % (hoje.isoformat(), mensagem),
                }
            ],
            output_config={
                "effort": "low",  # extração é tarefa curta; effort alto só encarece
                "format": {"type": "json_schema", "schema": ESQUEMA},
            },
        )

        texto = next(bloco.text for bloco in resposta.content if bloco.type == "text")
        dados = json.loads(texto)

        campos = {}
        for nome in CAMPOS:
            bruto = dados["campos"][nome]
            estado = bruto["estado"]
            # Defesa contra saída inconsistente: estado "preenchido" sem valor ou
            # sem origem é rebaixado a lacuna. A regra 2 do prompt exige origem;
            # se ela não veio, o campo não tem procedência e não pode ser usado.
            if estado == PREENCHIDO and (not bruto.get("valor") or not bruto.get("origem")):
                estado = LACUNA
            campos[nome] = Campo(
                nome,
                valor=bruto.get("valor") if estado == PREENCHIDO else None,
                origem=bruto.get("origem"),
                estado=estado,
                nota=bruto.get("nota"),
            )

        evidencias = {"instrucao_embutida": dados.get("instrucao_embutida", False)}
        return Interpretacao(
            dados["intencao"], float(dados["confianca"]), campos, evidencias
        )
