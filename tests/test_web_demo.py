"""Contrato HTTP real da demo; nenhum cliente sai do loopback."""
import concurrent.futures
import http.client
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from threading import Thread
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.find_spec('demo_crm')
if SPEC:
    import demo_crm


class WebDemoTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(SPEC, 'Falta o servidor local demo_crm.py (funcionalidade ainda não implementada)')
        self.server = demo_crm.criar_servidor(port=0)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.port = self.server.server_address[1]
        self.origin = f'http://127.0.0.1:{self.port}'
        self.fields = dict(nome='Pessoa Demo A', email='a@example.com',
                           data='2026-11-03', hora='15:00', assunto='atendimento digital')

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def request(self, path='/api/estado', method='GET', payload=None, headers=None, raw=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=4)
        hs = {'Origin': self.origin}
        body = raw
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            hs['Content-Type'] = 'application/json'
        hs.update(headers or {})
        try:
            conn.request(method, path, body=body, headers=hs)
            response = conn.getresponse()
            content = response.read()
            result = dict(code=response.status, headers=dict(response.getheaders()), content=content)
            if 'application/json' in result['headers'].get('Content-Type', ''):
                result['json'] = json.loads(content)
            return result
        finally:
            conn.close()

    def post(self, path, payload, **kwargs):
        return self.request(path, 'POST', payload, **kwargs)

    def assert_error(self, response, code):
        self.assertEqual(response['code'], code, response['content'])
        self.assertIsInstance(response['json']['erro'], str)
        self.assertNotIn(b'Traceback', response['content'])
        self.assertEqual(response['headers']['Cache-Control'], 'no-store')
        self.assertEqual(response['headers']['X-Content-Type-Options'], 'nosniff')

    def test_estado_fabrica_loopback_e_cabecalhos(self):
        from http.server import ThreadingHTTPServer
        self.assertIsInstance(self.server, ThreadingHTTPServer)
        self.assertEqual(self.server.server_address[0], '127.0.0.1')
        r = self.request()
        self.assertEqual(r['code'], 200)
        self.assertTrue(r['json']['demo'])
        self.assertEqual(len(r['json']['pipelines']), 3)
        self.assertEqual(r['headers']['Cache-Control'], 'no-store')
        self.assertIn("script-src 'self'", r['headers']['Content-Security-Policy'])
        self.assertIn("style-src 'self'", r['headers']['Content-Security-Policy'])
        self.assertEqual(r['headers']['X-Content-Type-Options'], 'nosniff')
        self.assertNotIn('Access-Control-Allow-Origin', r['headers'])

    def test_estaticos_allowlist_e_sem_dependencia_externa(self):
        for path, mime in [('/', 'text/html'), ('/index.html', 'text/html'),
                           ('/app.js', 'text/javascript'), ('/style.css', 'text/css')]:
            r = self.request(path)
            self.assertEqual(r['code'], 200, path)
            self.assertIn(mime, r['headers']['Content-Type'])
        html = self.request('/')['content'].decode()
        self.assertIn('Demonstração local • Sem conexão com o CRM real • Use somente dados fictícios', html)
        self.assertIn('representação didática, não captura da interface de produção', html)
        self.assertIn('Leadframe CRM', html)
        self.assertIn('aria-live=', html)
        for path in ['/app.js', '/style.css', '/']:
            source = self.request(path)['content'].decode()
            self.assertNotIn('https://', source)
            self.assertNotIn('innerHTML', source)

    def test_caminhos_fora_allowlist_nao_vazam_arquivo(self):
        for path in ['/../src/crm_demo.py', '/%2e%2e/src/crm_demo.py', '/web/',
                     '/docs/evidencias-crm-2026-10-26.json', '/.git/config', '/api/inexistente']:
            with self.subTest(path=path):
                self.assert_error(self.request(path), 404)

    def test_disponibilidade_real_do_backend(self):
        r = self.request('/api/disponibilidade?data=2026-11-03')
        self.assertEqual(r['code'], 200)
        self.assertEqual(r['json']['data'], '2026-11-03')
        self.assertIn('15:00', r['json']['horarios'])
        self.assertNotIn('14:00', r['json']['horarios'])
        for query in ['', '?data=ruim', '?data=2026-11-03&data=2026-11-04', '?outra=1']:
            self.assert_error(self.request('/api/disponibilidade' + query), 400)

    def test_mover_devolve_resultado_e_estado_lido_apos_escrita(self):
        r = self.post('/api/mover', dict(lead_id='DEMO-001', etapa='Qualificando', pipeline_id='DEMO-P1'))
        self.assertEqual(r['code'], 200)
        self.assertEqual(r['json']['resultado']['etapa'], 'Qualificando')
        self.assertEqual(r['json']['estado'], self.request()['json'])
        self.assertEqual(r['json']['estado']['eventos'][-1]['acao'], 'mover')
        self.assert_error(self.post('/api/mover', dict(lead_id='DEMO-001', etapa='Inventada')), 400)
        self.assert_error(self.post('/api/mover', dict(lead_id='DEMO-001', etapa='Qualificando', pipeline_id='DEMO-P2')), 400)

    def test_mensagem_e_reserva_completa(self):
        r = self.post('/api/mensagem', dict(lead_id='DEMO-001', texto='Sou Pessoa Demo A, quero marcar uma reunião dia 03/11 às 15h sobre atendimento. Meu email é a@example.com'))
        self.assertEqual(r['code'], 200)
        self.assertEqual(r['json']['resultado']['acao'], 'reserva_simulada')
        self.assertEqual(len(r['json']['estado']['reservas']), 1)
        self.assertEqual(r['json']['estado'], self.request()['json'])

    def test_reserva_conflito_e_reset(self):
        r = self.post('/api/reservar', dict(lead_id='DEMO-001', campos=self.fields))
        self.assertEqual(r['code'], 200)
        self.assertTrue(r['json']['resultado']['simulada'])
        self.assertEqual(r['json']['estado'], self.request()['json'])
        self.assert_error(self.post('/api/reservar', dict(lead_id='DEMO-002', campos=self.fields)), 400)
        self.assertEqual(len(self.request()['json']['reservas']), 1)
        r = self.post('/api/reset', {})
        self.assertEqual(r['code'], 200)
        self.assertFalse(r['json']['estado']['reservas'])
        self.assertFalse(r['json']['estado']['eventos'])

    def test_handoff_e_optout_pausam_reserva(self):
        for lead, msg, action in [('DEMO-001', 'quero falar com um humano', 'handoff_simulado'),
                                  ('DEMO-002', 'não quero mais receber mensagens', 'opt_out')]:
            r = self.post('/api/mensagem', dict(lead_id=lead, texto=msg))
            self.assertEqual(r['json']['resultado']['acao'], action)
            self.assert_error(self.post('/api/reservar', dict(lead_id=lead, campos=self.fields)), 400)
        self.assertFalse(self.request()['json']['reservas'])

    def test_instancias_isoladas(self):
        self.post('/api/mover', dict(lead_id='DEMO-001', etapa='Qualificando'))
        other = demo_crm.criar_servidor(port=0)
        try:
            self.assertEqual(other.crm.consultar('DEMO-001')['etapa'], 'Novo contato')
        finally:
            other.server_close()

    def test_concorrencia_http_nao_duplica_reserva(self):
        def reserve(lead):
            return self.post('/api/reservar', dict(lead_id=lead, campos=self.fields))['code']
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            codes = list(pool.map(reserve, ['DEMO-001', 'DEMO-002']))
        self.assertCountEqual(codes, [200, 400])
        self.assertEqual(len(self.request()['json']['reservas']), 1)

    def test_campos_ausentes_tipos_e_desconhecidos(self):
        cases = [('/api/mensagem', {}), ('/api/mensagem', {'lead_id': [] ,'texto':'oi'}),
                 ('/api/mensagem', {'lead_id':'DEMO-001','texto':42}),
                 ('/api/mensagem', {'lead_id':'DEMO-001','texto':'  '}),
                 ('/api/mensagem', {'lead_id':'DEMO-001','texto':'x' * 2001}),
                 ('/api/mensagem', {'lead_id':'DEMO-001','texto':'oi','extra':True}),
                 ('/api/mover', {'lead_id':'DEMO-001','etapa':None}),
                 ('/api/mover', {'lead_id':'DEMO-001','etapa':'Qualificando','pipeline_id':12}),
                 ('/api/reservar', {'lead_id':'DEMO-001','campos':[]}),
                 ('/api/reservar', {'lead_id':'DEMO-001','campos':{}}),
                 ('/api/reservar', {'lead_id':'DEMO-001','campos':dict(self.fields, extra='x')}),
                 ('/api/reservar', {'lead_id':'DEMO-001','campos':dict(self.fields, nome=3)}),
                 ('/api/reset', {'extra':1})]
        for path, payload in cases:
            with self.subTest(path=path, payload=payload):
                self.assert_error(self.post(path, payload), 400)
        self.assertFalse(self.request()['json']['eventos'])

    def test_json_invalido_escalar_duplicado_e_unicode_invalido(self):
        for raw in [b'{', b'[]', b'null', b'42', b'"texto"', b'\xff',
                    b'{"lead_id":"DEMO-001","lead_id":"DEMO-002","texto":"oi"}']:
            with self.subTest(raw=raw):
                self.assert_error(self.request('/api/mensagem', 'POST', raw=raw,
                    headers={'Content-Type':'application/json'}), 400)

    def test_identificador_inexistente(self):
        self.assert_error(self.post('/api/mensagem', dict(lead_id='DEMO-999', texto='status')), 404)

    def test_host_e_origin_somente_loopback_na_porta_efetiva(self):
        for headers in [{'Host':'evil.example'}, {'Host':f'127.0.0.1:{self.port + 1}'},
                        {'Origin':'https://evil.example'}, {'Origin':'null'},
                        {'Origin':f'http://localhost:{self.port}/'},
                        {'Origin':'http://127.0.0.1:1'}]:
            with self.subTest(headers=headers):
                self.assert_error(self.request(headers=headers), 403)
        r = self.request(headers={'Host':f'localhost:{self.port}', 'Origin':f'http://localhost:{self.port}'})
        self.assertEqual(r['code'], 200)

    def test_get_sem_origin_permitido_post_sem_origin_bloqueado(self):
        for method, path, expected in [('GET','/api/estado',200), ('POST','/api/reset',403)]:
            conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=4)
            try:
                conn.request(method, path, body=b'{}' if method == 'POST' else None,
                             headers={'Content-Type':'application/json'})
                r = conn.getresponse()
                self.assertEqual(r.status, expected, r.read())
            finally:
                conn.close()

    def raw_request(self, extra_headers, body=b''):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=4)
        try:
            conn.putrequest('POST', '/api/reset')
            conn.putheader('Origin', self.origin)
            conn.putheader('Content-Type', 'application/json')
            for key, value in extra_headers:
                conn.putheader(key, value)
            conn.endheaders(body)
            r = conn.getresponse()
            content = r.read()
            return dict(code=r.status, headers=dict(r.getheaders()), content=content, json=json.loads(content))
        finally:
            conn.close()

    def test_framing_http_e_limite_16kb(self):
        for headers, body, expected in [([], b'', 411),
                ([('Content-Length','-1')],b'',400),
                ([('Content-Length','abc')],b'',400),
                ([('Content-Length','16385')],b'',413),
                ([('Content-Length','2'),('Content-Length','2')],b'{}',400),
                ([('Transfer-Encoding','chunked')],b'',400)]:
            with self.subTest(headers=headers):
                self.assert_error(self.raw_request(headers, body), expected)
        exact = b'{}' + b' ' * (16384 - 2)
        self.assertEqual(self.raw_request([('Content-Length',str(len(exact)))], exact)['code'], 200)

    def test_content_type_rotas_metodos(self):
        self.assert_error(self.request('/api/reset', 'POST', raw=b'{}', headers={'Content-Type':'text/plain'}),415)
        self.assert_error(self.post('/api/desconhecida', {}),404)
        self.assert_error(self.post('/index.html', {}),405)
        for method in ['PUT','DELETE','OPTIONS','PATCH']:
            self.assert_error(self.request('/api/estado',method),405)

    def test_portas_invalidas_nao_abrem_servidor(self):
        for port in [-1, 65536, True, '8765']:
            with self.assertRaises(ValueError):
                demo_crm.criar_servidor(port=port)

    def test_roteiro_cli_deterministico_com_tres_casos_e_trilha(self):
        cmd = [sys.executable, str(ROOT / 'demo_crm.py'), '--roteiro']
        one = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=10)
        two = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(one.returncode,0,one.stderr)
        self.assertEqual(one.stdout,two.stdout)
        data = json.loads(one.stdout)
        self.assertTrue(data['demo'])
        self.assertEqual([c['nome'] for c in data['casos']], ['completa','incompleta','informal'])
        for case in data['casos']:
            self.assertEqual(case['passos'][-1]['resultado']['acao'], 'reserva_simulada')
        self.assertEqual(len(data['estado_final']['reservas']),3)
        actions = [event['acao'] for event in data['estado_final']['eventos']]
        for action in ['mover','reserva_simulada','handoff_simulado','opt_out']:
            self.assertIn(action, actions)
        self.assertIn('ocupado',data['conflito']['erro'])
        self.assertEqual(data['status']['intencao'],'consultar_status')
        for lead in data['estado_final']['oportunidades']:
            self.assertTrue(lead['id'].startswith('DEMO-'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
