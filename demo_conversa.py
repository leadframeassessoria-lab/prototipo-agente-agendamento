"""Conversa interativa com o agente, para demonstrar ao vivo.

    python demo_conversa.py            # extrator determinístico (padrão, offline)
    python demo_conversa.py --llm      # extrator por modelo (precisa de chave)
    python demo_conversa.py --debug    # mostra intenção, campos, API e auditoria

Comandos dentro da conversa: `/estado` mostra o que o agente sabe até agora,
`/reset` começa de novo, `/sair` encerra.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agente import Agente, ClienteAgenda  # noqa: E402
from agenda_api import criar_servidor  # noqa: E402
from dialogo import Estado  # noqa: E402

HOJE = date(2026, 9, 14)


def main() -> int:
    usar_llm = "--llm" in sys.argv
    debug = "--debug" in sys.argv

    servidor, porta = criar_servidor(0)
    import threading

    threading.Thread(target=servidor.serve_forever, daemon=True).start()

    if usar_llm:
        from nlu_llm import NLULLM

        nlu = NLULLM()
    else:
        nlu = None

    agente = Agente(ClienteAgenda("http://127.0.0.1:%d" % porta), nlu)
    estado = Estado(HOJE)

    print("Agente de agendamento | extrator: %s" % agente.nlu.nome)
    print("Data de referência: %s | agenda em http://127.0.0.1:%d" % (HOJE, porta))
    print("Comandos: /estado  /reset  /sair\n")

    while True:
        try:
            mensagem = input("você> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        # Quando a entrada vem de um arquivo ou de um pipe, o terminal não
        # ecoa o que foi digitado e o transcrito sai só com um lado da
        # conversa. Ecoar aqui é o que torna a sessão gravada legível.
        if not sys.stdin.isatty():
            print(mensagem)

        if not mensagem:
            continue
        if mensagem == "/sair":
            break
        if mensagem == "/reset":
            estado = Estado(HOJE)
            print("(conversa reiniciada)\n")
            continue
        if mensagem == "/estado":
            print("  intenção: %s" % estado.intencao)
            for linha in estado.resumo_lacunas():
                print("  %s" % linha)
            print()
            continue

        resposta = agente.processar(mensagem, estado)

        if debug:
            if resposta.portao:
                print("  [portão] %s" % resposta.portao)
            for chamada in resposta.chamadas:
                print("  [api] %s" % chamada)
            print("  [auditoria] %s | sem origem: %s" % (
                "aprovada" if resposta.auditoria["aprovada"] else "REPROVADA",
                resposta.auditoria["sem_origem"] or "nenhum",
            ))

        print("agente> %s\n" % resposta.texto.replace("\n", "\n        "))

    servidor.shutdown()
    print("até mais.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
