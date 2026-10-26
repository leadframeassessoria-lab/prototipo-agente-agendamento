#!/usr/bin/env python3
"""Demonstração CRM exclusivamente local, stdlib, sem conectores de produção.

Política HTTP: Host obrigatório e Origin, quando presente, devem ser uma das
origens HTTP loopback na porta efetivamente aberta. POST exige Origin inclusive
para clientes CLI: enviar explicitamente http://127.0.0.1:PORTA. GET sem Origin
permite carregar a página. Nenhum CORS, cookie ou acesso fora da allowlist.
Isso mitiga DNS rebinding e CSRF; não é autenticação contra outro processo local.
Todo estado fica em memória por instância. Reiniciar/reset descarta apenas demo.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import socket
import sys
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from crm_demo import CAMPOS, CRM

MAX_BODY = 16 * 1024
STATIC = {'/': ('index.html', 'text/html'), '/index.html': ('index.html', 'text/html'),
          '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
ACTIONS = {'/api/mensagem': ({'lead_id', 'texto'}, set()),
           '/api/mover': ({'lead_id', 'etapa'}, {'pipeline_id'}),
           '/api/reservar': ({'lead_id', 'campos'}, set()),
           '/api/reset': (set(), set())}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
       "base-uri 'none'; frame-ancestors 'none'; form-action 'self'")


class HTTPProblem(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def object_without_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Campo JSON duplicado')
        result[key] = value
    return result


def validate_shape(value, required, optional=frozenset()):
    if not isinstance(value, dict):
        raise ValueError('O JSON deve ser um objeto')
    if set(value) - required - optional or required - set(value):
        raise ValueError('Campos ausentes ou desconhecidos')


class DemoHandler(BaseHTTPRequestHandler):
    server_version = 'CRM-Demo-Local'
    sys_version = ''
    protocol_version = 'HTTP/1.1'

    def setup(self):
        super().setup()
        self.connection.settimeout(3)

    def log_message(self, fmt, *args):
        # Não despejar mensagens/nome/e-mail em logs do terminal.
        pass

    def respond(self, status, data, mime='application/json'):
        content = (json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
                   if mime == 'application/json' else data)
        self.send_response(status)
        self.send_header('Content-Type', mime + '; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', CSP)
        self.send_header('Referrer-Policy', 'no-referrer')
        # Fechar também em erro evita bytes não consumidos virarem outro request.
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        if self.command != 'HEAD':
            self.wfile.write(content)

    def send_error(self, code, message=None, explain=None):
        # Inclusive métodos/cabeçalhos inválidos processados pela stdlib são JSON.
        self.respond(code, {'erro': 'Requisição HTTP recusada'})

    def guard(self):
        hosts = {f'{host}:{self.server.server_port}' for host in ('127.0.0.1', 'localhost')}
        if len(self.headers.get_all('Host', [])) != 1 or self.headers.get('Host') not in hosts:
            raise HTTPProblem(403, 'Host deve apontar para o loopback na porta desta demo')
        origins = self.headers.get_all('Origin', [])
        if len(origins) > 1 or (origins and origins[0] not in {'http://' + h for h in hosts}):
            raise HTTPProblem(403, 'Origin não autorizado')
        if self.command == 'POST' and not origins:
            raise HTTPProblem(403, 'Origin é obrigatório para alterar a demonstração')
        if self.headers.get_all('Transfer-Encoding'):
            raise HTTPProblem(400, 'Transfer-Encoding não é aceito')
        parts = urlsplit(self.path)
        if parts.scheme or parts.netloc or parts.fragment or not self.path.startswith('/'):
            raise HTTPProblem(400, 'Use um caminho HTTP local')
        return parts

    def read_json(self):
        lengths = self.headers.get_all('Content-Length', [])
        if not lengths:
            raise HTTPProblem(411, 'Content-Length é obrigatório')
        if len(lengths) != 1 or not re.fullmatch(r'[0-9]+', lengths[0]):
            raise HTTPProblem(400, 'Content-Length inválido')
        # Evitar converter uma sequência arbitrariamente grande em int.
        if len(lengths[0]) > 6 or int(lengths[0]) > MAX_BODY:
            raise HTTPProblem(413, 'Corpo excede 16KB')
        length = int(lengths[0])
        types = self.headers.get_all('Content-Type', [])
        if len(types) != 1 or types[0].lower().replace(' ', '') not in (
                'application/json', 'application/json;charset=utf-8'):
            raise HTTPProblem(415, 'Envie application/json em UTF-8')
        try:
            raw = self.rfile.read(length)
        except (socket.timeout, OSError):
            raise HTTPProblem(408, 'Tempo de leitura do corpo esgotado') from None
        if len(raw) != length:
            raise HTTPProblem(400, 'Corpo HTTP incompleto')
        try:
            data = json.loads(raw.decode('utf-8'), object_pairs_hook=object_without_duplicates,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Número inválido')))
        except (UnicodeError, ValueError, RecursionError):
            raise HTTPProblem(400, 'JSON inválido, duplicado ou não UTF-8') from None
        if not isinstance(data, dict):
            raise HTTPProblem(400, 'O JSON deve ser um objeto')
        return data

    def dispatch(self):
        try:
            parts = self.guard()
            path = parts.path
            known = path in STATIC or path in ACTIONS or path in ('/api/estado', '/api/disponibilidade')
            if not known:
                raise HTTPProblem(404, 'Rota não encontrada')
            if self.command not in ('GET', 'POST'):
                raise HTTPProblem(405, 'Método não permitido')
            if self.command == 'GET':
                if path in ACTIONS:
                    raise HTTPProblem(405, 'Esta rota exige POST')
                if path == '/api/disponibilidade':
                    query = parse_qs(parts.query, keep_blank_values=True, max_num_fields=4)
                    if set(query) != {'data'} or len(query['data']) != 1 or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', query['data'][0]):
                        raise ValueError('Informe somente data=AAAA-MM-DD')
                    day = query['data'][0]
                    self.respond(200, {'data': day, 'horarios': self.server.crm.disponibilidade(day)})
                elif parts.query:
                    raise ValueError('Esta rota não aceita parâmetros')
                elif path == '/api/estado':
                    self.respond(200, self.server.crm.estado())
                else:
                    filename, mime = STATIC[path]
                    # Caminho nunca é derivado do request: allowlist literal, sem listagem.
                    self.respond(200, (ROOT / 'web' / filename).read_bytes(), mime)
                return
            if path not in ACTIONS:
                raise HTTPProblem(405, 'Esta rota exige GET')
            if parts.query:
                raise ValueError('Esta rota não aceita parâmetros')
            payload = self.read_json()
            required, optional = ACTIONS[path]
            validate_shape(payload, required, optional)
            for key, value in payload.items():
                if key != 'campos' and (not isinstance(value, str) or not value.strip()):
                    raise ValueError('Campos devem ser textos não vazios')
            if path == '/api/reservar':
                fields = payload['campos']
                validate_shape(fields, set(CAMPOS))
                if any(not isinstance(value, str) or not value.strip() for value in fields.values()):
                    raise ValueError('Campos da reserva devem ser textos não vazios')
            # A escrita e a leitura posterior compõem uma seção crítica; outro request
            # não pode inserir seu estado entre a ação e o recibo desta mesma ação.
            crm = self.server.crm
            with crm.lock:
                if path == '/api/mensagem':
                    result = crm.mensagem(payload['lead_id'], payload['texto'])
                elif path == '/api/mover':
                    result = crm.mover(payload['lead_id'], payload['etapa'], payload.get('pipeline_id'))
                elif path == '/api/reservar':
                    result = crm.reservar(payload['lead_id'], payload['campos'])
                else:
                    crm.reset()
                    result = {'demo': True, 'acao': 'reset', 'mensagem': 'Somente a sessão local foi reiniciada'}
                state = crm.estado()
            self.respond(200, {'resultado': result, 'estado': state})
        except HTTPProblem as exc:
            self.respond(exc.status, {'erro': exc.message})
        except KeyError:
            self.respond(404, {'erro': 'Oportunidade demo inexistente'})
        except (ValueError, RecursionError):
            # Mensagem útil, mas sem ecoar os dados submetidos nem tracebacks.
            exc = sys.exception()
            self.respond(400, {'erro': str(exc) if isinstance(exc, ValueError) else 'JSON complexo demais'})
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception:
            self.respond(500, {'erro': 'Falha interna da demonstração local'})

    do_GET = dispatch
    do_POST = dispatch
    do_PUT = dispatch
    do_DELETE = dispatch
    do_PATCH = dispatch
    do_OPTIONS = dispatch
    do_HEAD = dispatch


def criar_servidor(port=0):
    """Cria, mas não inicia, um servidor independente ligado APENAS ao loopback."""
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError('Porta deve ser um inteiro entre 0 e 65535')
    server = ThreadingHTTPServer(('127.0.0.1', port), DemoHandler)
    server.daemon_threads = True
    server.crm = CRM()
    return server


def roteiro():
    """Transcrito determinístico: mesmas fixtures, relógio fixo, sem HTTP ou rede."""
    crm = CRM()
    cases = []
    scripts = [
        ('completa', 'DEMO-001', ['Sou Pessoa Demo A, quero marcar uma reunião dia 03/11 às 15h sobre atendimento. Meu email é a@example.com']),
        ('incompleta', 'DEMO-002', ['Quero agendar uma reunião', '03/11', '10h', 'Pessoa Demo B', 'b@example.com', 'atendimento digital']),
        ('informal', 'DEMO-003', ['eae blz qria marca um papo dia 04/11 de tarde, poe no nome de Pessoa Demo C, meu email eh c@example.com', '16h ta otimo', 'atendimento digital'])]
    for name, lead, messages in scripts:
        steps = [{'texto': msg, 'resultado': crm.mensagem(lead, msg)} for msg in messages]
        cases.append({'nome': name, 'lead_id': lead, 'passos': steps})
    moved = crm.mover('DEMO-001', 'Qualificando')
    status = crm.mensagem('DEMO-001', 'qual o status da minha oportunidade?')
    fields = dict(nome='Pessoa Demo B', email='b@example.com', data='2026-11-03',
                  hora='15:00', assunto='atendimento digital')
    try:
        crm.reservar('DEMO-002', fields)
        conflict = {'erro': None}
    except ValueError as exc:
        conflict = {'erro': str(exc)}
    human = crm.mensagem('DEMO-001', 'quero falar com um humano')
    optout = crm.mensagem('DEMO-002', 'não quero mais receber mensagens de vocês')
    return {'demo': True, 'aviso': 'Reservas SIMULADAS; nenhum Meet, e-mail ou aviso a humano enviado.',
            'casos': cases, 'movimento': moved, 'status': status, 'conflito': conflict,
            'humano': human, 'opt_out': optout, 'estado_final': crm.estado()}


def main(argv=None):
    parser = argparse.ArgumentParser(description='CRM didático local, sem conexão com produção')
    parser.add_argument('--port', type=int, default=8765, help='porta loopback (0 permite efêmera; padrão 8765)')
    parser.add_argument('--roteiro', action='store_true', help='imprime roteiro JSON determinístico; não abre servidor')
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error('--port deve estar entre 0 e 65535')
    if args.roteiro:
        print(json.dumps(roteiro(), ensure_ascii=False, indent=2))
        return 0
    try:
        server = criar_servidor(args.port)
    except OSError as exc:
        parser.exit(1, f'Não foi possível abrir o servidor local: {exc}\n')
    print(f'Demonstração local em http://127.0.0.1:{server.server_port} — sem CRM real. Ctrl+C encerra.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
