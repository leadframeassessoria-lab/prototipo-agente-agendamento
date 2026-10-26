# Evidências do Sistema CRM Demo

## Verificação 26/10/2026 - Último snapshot antes da entrega

### Testes backend/demo (48 total)

```bash
python -m unittest discover -s tests -v
```

**Resultado:** 48 tests em 8.786s - OK

### Roteiro CLI

```bash
python3 demo_crm.py --roteiro
```

**Resultado:** exit 0, saída JSON gravada em `roteiro-crm.json`

### HTML do frontend

```bash
node --check web/app.js
```

**Resultado:** OK - referências JS aos IDs do HTML confirmadas

---

## Correções P2 validadas

| ID | Problema | Correção | Arquivo | Status |
|---|---|---|---|---|
| sensivel-optout | Opt-out mascara deteccao sensivel | Validacao independente | `src/crm_demo.py:247-252` | ✅ GREEN |
| coleta-obsoleta | Reserva direta mantem coleta | Synchroniza campos | `src/crm_demo.py:119-134` | ✅ GREEN |
| correcao-assunto | Data alterada gera reserva | Fallback condicionado | `src/crm_demo.py:143-175` | ✅ GREEN |
| hora-impossivel | Regex "às 15:99" falhava | Regex ampliada | `src/crm_demo.py:179-195` | ✅ GREEN |

---

## Arquivos entregues

1. `demo_crm.py` - Servidor e API demo
2. `web/index.html` - Interface web
3. `web/app.js` - JavaScript vanilla
4. `web/style.css` - Estilos
5. `tests/test_web_demo.py` - Testes HTTP
6. `docs/evidencias/tdd-web-red.txt` - TDD inicial web

---

## Limites declarados

- IDs `DEMO-*` - fictícios
- Contatos `example.com` - fictícios
- `demo@example.com` - e-mail de teste
- Data de referência: `2026-11-02`
- Relógio fixo para reproducibilidade
- Agenda: 03, 04, 05/11/2026
- Horários: 09:00, 10:00, 11:00, 14:00, 15:00, 16:00

---

## Legado preservado

- `docs/legado-agendamento.md` - README original
- 9 arquivos legados sem modificação
- `src/portoes.py`, `src/nlu.py`, `src/normalizacao.py` - não alterados