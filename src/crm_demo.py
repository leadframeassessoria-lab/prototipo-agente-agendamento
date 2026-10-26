"""CRM didático offline: configuração observada, operações e dados simulados.

Nenhum conector de produção, chamada externa, e-mail ou Meet é criado aqui.
O relógio é fixo para tornar as apresentações reproduzíveis.
"""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import re
from threading import RLock

from nlu import AGENDAR, NLULocal, PARCIAL, extrair_resposta_direta
from normalizacao import normalizar
from portoes import PADROES_SENSIVEIS, verificar

SNAPSHOT = Path(__file__).resolve().parents[1] / 'docs/evidencias-crm-2026-10-26.json'
CAMPOS = ('data', 'hora', 'nome', 'email', 'assunto')
SLOTS = ('09:00', '10:00', '11:00', '14:00', '15:00', '16:00')
DIAS_DEMO = ('2026-11-03', '2026-11-04', '2026-11-05')
EMAIL = re.compile(r'[A-Za-z0-9.!#$%&\' *+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+')


class CRM:
    """Uma instância é uma sessão de demonstração, não um tenant de produção."""
    def __init__(self, hoje=None):
        self.hoje = hoje or date(2026, 11, 2)
        self.lock = RLock()
        self.nlu = NLULocal()
        snapshot = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
        self.pipelines = [dict(id=p['id_demo'], nome=p['nome'], etapas=p['etapas'])
                          for p in snapshot['pipelines']]
        self.evento = snapshot['evento']
        self.reset()

    def reset(self):
        """Descarta somente fixtures e interações locais desta instância."""
        with self.lock:
            self.leads = {}
            for i, (pid, etapa) in enumerate([
                ('DEMO-P1', 'Novo contato'), ('DEMO-P2', 'Qualificando'),
                ('DEMO-P3', 'Ocorrência aberta')], 1):
                lead_id = 'DEMO-%03d' % i
                self.leads[lead_id] = dict(
                    id=lead_id, nome='Pessoa Demo ' + chr(64 + i),
                    pipeline_id=pid, etapa=etapa, opt_out=False, handoff=False,
                    campos={}, fontes={}, conversa=[], agendando=False,
                    esperado=None, periodo=None)
            self.reservas = []
            self.eventos = []
            self.ocupados = {('2026-11-03', '14:00')}

    def _lead(self, lead_id):
        if lead_id not in self.leads:
            raise KeyError('Oportunidade demo inexistente')
        return self.leads[lead_id]

    def _log(self, acao, lead_id, detalhe):
        self.eventos.append(dict(sequencia=len(self.eventos) + 1, acao=acao,
                               lead_id=lead_id, detalhe=deepcopy(detalhe)))

    def estado(self):
        with self.lock:
            return deepcopy(dict(demo=True, referencia=self.hoje.isoformat(),
                pipelines=self.pipelines, evento=self.evento,
                oportunidades=list(self.leads.values()), reservas=self.reservas,
                eventos=self.eventos, dias_disponiveis=list(DIAS_DEMO)))

    def consultar(self, lead_id):
        with self.lock:
            return deepcopy(self._lead(lead_id))

    def mover(self, lead_id, etapa, pipeline_id=None):
        with self.lock:
            lead = self._lead(lead_id)
            if pipeline_id is not None and pipeline_id != lead['pipeline_id']:
                raise ValueError('Esta demo não transfere oportunidades entre funis')
            pipeline = next(p for p in self.pipelines if p['id'] == lead['pipeline_id'])
            if etapa not in pipeline['etapas']:
                raise ValueError('Etapa não pertence ao funil desta oportunidade')
            anterior = lead['etapa']
            lead['etapa'] = etapa
            self._log('mover', lead_id, dict(de=anterior, para=etapa))
            return deepcopy(lead)

    def disponibilidade(self, dia):
        with self.lock:
            try:
                d = date.fromisoformat(dia)
            except (ValueError, TypeError):
                raise ValueError('Data inválida; use AAAA-MM-DD') from None
            if d < self.hoje or dia not in DIAS_DEMO:
                return []
            return [h for h in SLOTS if (dia, h) not in self.ocupados]

    def _validar(self, campos):
        if not isinstance(campos, dict):
            raise ValueError('Campos devem ser um objeto')
        if any(not isinstance(campos.get(c), str) or not campos[c].strip() for c in CAMPOS):
            raise ValueError('Nome, e-mail, data, hora e assunto são obrigatórios')
        c = {k: campos[k].strip() for k in CAMPOS}
        if not EMAIL.fullmatch(c['email']) or len(c['email']) > 254:
            raise ValueError('E-mail inválido')
        if not 2 <= len(c['nome']) <= 80 or not 3 <= len(c['assunto']) <= 120:
            raise ValueError('Nome ou assunto inválido')
        try:
            dia = date.fromisoformat(c['data'])
        except ValueError:
            raise ValueError('Data inválida') from None
        if dia < self.hoje or c['data'] not in DIAS_DEMO:
            raise ValueError('Data fora da agenda fictícia: 03, 04 ou 05/11/2026')
        if c['hora'] not in SLOTS:
            raise ValueError('Hora fora da agenda fictícia')
        # A precedência do opt-out não pode mascarar detecção de dados sensíveis.
        sensivel = any(p.search(v) for v in c.values() for _, p in PADROES_SENSIVEIS)
        if sensivel or any(verificar(v).tipo == 'injecao' for v in c.values()):
            raise ValueError('Use somente dados fictícios não sensíveis')
        return c

    def reservar(self, lead_id, campos):
        with self.lock:
            lead = self._lead(lead_id)
            if lead['opt_out'] or lead['handoff']:
                raise ValueError('Automação pausada por opt-out ou handoff')
            c = self._validar(campos)
            if (c['data'], c['hora']) in self.ocupados:
                raise ValueError('Horário ocupado na agenda simulada')
            reserva = dict(c, id='DEMO-R%03d' % (len(self.reservas) + 1),
                           lead_id=lead_id, simulada=True, duracao_minutos=30)
            self.ocupados.add((c['data'], c['hora']))
            self.reservas.append(reserva)
            lead['fontes'] = {
                k: lead['fontes'].get(k, 'formulário de reserva simulada')
                if lead['campos'].get(k) == v else 'formulário de reserva simulada'
                for k, v in c.items()
            }
            lead['campos'] = deepcopy(c)
            lead['agendando'] = False
            lead['esperado'] = None
            lead['periodo'] = None
            self._log('reserva_simulada', lead_id, reserva)
            if lead['pipeline_id'] in ('DEMO-P1', 'DEMO-P2'):
                self.mover(lead_id, 'Agendado')
            return deepcopy(reserva)

    def _resposta(self, lead, texto, intencao, acao=None):
        lead['conversa'].append(dict(papel='assistente', texto=texto))
        return dict(resposta=texto, intencao=intencao, acao=acao,
                    campos=deepcopy(lead['campos']),
                    faltantes=[c for c in CAMPOS if not lead['campos'].get(c)]
                    if lead['agendando'] else [])

    def _coletar(self, lead, texto, interpretacao):
        # Correções substituem valores anteriores, inclusive por uma lacuna.
        for k in CAMPOS:
            campo = interpretacao.campos[k]
            if campo.ok:
                value = campo.valor
                if k == 'email' and not EMAIL.fullmatch(value):
                    continue
                lead['campos'][k] = value
                lead['fontes'][k] = campo.origem
                if k == 'hora':
                    lead['periodo'] = None
            elif campo.estado == PARCIAL:
                lead['campos'].pop(k, None)
                lead['fontes'].pop(k, None)
                if k == 'hora':
                    lead['periodo'] = campo.nota
        esperado = lead['esperado']
        outro_campo = any(k != esperado and (interpretacao.campos[k].ok or
                          interpretacao.campos[k].estado == PARCIAL) for k in CAMPOS)
        if (esperado in ('nome', 'assunto') and not interpretacao.campos[esperado].ok
                and not outro_campo):
            direto = extrair_resposta_direta(esperado, texto, self.hoje)
            if direto.ok:
                lead['campos'][esperado] = direto.valor
                lead['fontes'][esperado] = direto.origem
        # NLU legado não marca horas impossíveis como parcial; não conservar hora antiga.
        # Regex captura hora: "15:99", "as 15", "as 15:99", "15h99", "as 25"
        normalizado = normalizar(texto)
        match = re.search(r'\b(?:as\s+)?(\d{1,2})(?::|\s*h)?(\d{2})?\b', normalizado)
        if match:
            hora = match[1]
            minutos = match[2]
            if (minutos and int(minutos) > 59) or int(hora) > 23:
                lead['campos'].pop('hora', None)
                lead['fontes'].pop('hora', None)
        if '@' in texto:
            token = re.search(r'\S+@\S+', texto)
            if token and not EMAIL.fullmatch(token[0].rstrip('.,;!?')):
                lead['campos'].pop('email', None)
                lead['fontes'].pop('email', None)

    def _agendar(self, lead):
        c = lead['campos']
        dia, hora = c.get('data'), c.get('hora')
        prefixo = ''
        if dia:
            slots = self.disponibilidade(dia)
            if not slots:
                c.pop('data', None)
                c.pop('hora', None)
                prefixo = 'Essa data não tem horários na agenda fictícia. '
            elif hora and hora not in slots:
                c.pop('hora', None)
                prefixo = 'Esse horário está ocupado ou fora da agenda simulada. '
        faltantes = [k for k in CAMPOS if not c.get(k)]
        if not faltantes:
            try:
                r = self.reservar(lead['id'], c)
            except ValueError as exc:
                return self._resposta(lead, str(exc) + '; revise os dados fictícios.', AGENDAR)
            lead['agendando'] = False
            lead['esperado'] = None
            return self._resposta(lead,
                'Reserva simulada %s registrada para %s às %s (30 minutos). '
                'Nenhum e-mail, Meet ou aviso a humano foi enviado.' %
                (r['id'], r['data'], r['hora']), AGENDAR, 'reserva_simulada')
        campo = faltantes[0]
        lead['esperado'] = campo
        perguntas = dict(data='Para qual dia: 03, 04 ou 05/11/2026?',
            nome='Em qual nome fictício eu registro?',
            email='Qual e-mail fictício (por exemplo demo@example.com)?',
            assunto='Qual é o assunto, em uma linha?')
        if campo == 'hora':
            slots = self.disponibilidade(c['data'])
            periodo = lead['periodo']
            if periodo in ('tarde', 'fim da tarde'):
                slots = [h for h in slots if int(h[:2]) >= (16 if periodo == 'fim da tarde' else 12)]
            elif periodo == 'manhã':
                slots = [h for h in slots if int(h[:2]) < 12]
            elif periodo == 'noite':
                slots = [h for h in slots if int(h[:2]) >= 18]
            if slots:
                pergunta = 'Na agenda simulada estão livres %s; qual horário você prefere?' % ', '.join(slots)
            else:
                pergunta = 'Não há horário nesse período na demo; qual outro período você prefere?'
        else:
            pergunta = perguntas[campo]
        return self._resposta(lead, prefixo + pergunta, AGENDAR)

    def mensagem(self, lead_id, texto):
        with self.lock:
            lead = self._lead(lead_id)
            if not isinstance(texto, str) or not texto.strip() or len(texto) > 2000:
                raise ValueError('Mensagem deve ter entre 1 e 2000 caracteres')
            if lead['opt_out']:
                return dict(resposta='Contato encerrado nesta demonstração por opt-out.',
                            intencao='opt_out', acao=None, campos=deepcopy(lead['campos']), faltantes=[])
            portao = verificar(texto)
            tipo_sensivel = next((tipo for tipo, padrao in PADROES_SENSIVEIS
                                  if padrao.search(texto)), None)
            if tipo_sensivel:
                self._log('dado_recusado', lead_id, dict(tipo=tipo_sensivel))
                if portao.tipo != 'opt_out':
                    return self._resposta(lead, 'Não gravei esse dado. Use somente informações fictícias e não sensíveis.', 'dado_recusado')
            if portao.tipo == 'injecao':
                self._log('injecao_ignorada', lead_id, dict(regra='mensagem não altera regras'))
                return self._resposta(lead, 'Essa instrução não altera as regras da demo; você quer consultar a etapa ou simular uma reunião?', 'indefinida')
            if not tipo_sensivel:
                lead['conversa'].append(dict(papel='pessoa', texto=texto))
            if portao.tipo == 'opt_out':
                lead['opt_out'] = True
                lead['agendando'] = False
                self._log('opt_out', lead_id, dict(simulado=True))
                return self._resposta(lead, 'Contato encerrado nesta demonstração; novas ações automáticas estão bloqueadas.', 'opt_out', 'opt_out')
            if lead['handoff']:
                return self._resposta(lead, 'O handoff simulado está registrado e a automação está pausada. Nenhum humano foi notificado.', 'solicitar_humano')
            if portao.tipo == 'escalonamento' or re.search(r'\b(humano|atendente)\b', normalizar(texto)):
                lead['handoff'] = True
                lead['agendando'] = False
                self._log('handoff_simulado', lead_id, dict(motivo=portao.detalhe or 'pedido_humano'))
                if lead['pipeline_id'] in ('DEMO-P1', 'DEMO-P2'):
                    self.mover(lead_id, 'Pronto para humano')
                return self._resposta(lead, 'Handoff simulado registrado; a automação foi pausada. Nenhum humano foi notificado.', 'solicitar_humano', 'handoff_simulado')
            normal = normalizar(texto)
            if re.search(r'\b(status|etapa|situacao)\b', normal):
                pipeline = next(p for p in self.pipelines if p['id'] == lead['pipeline_id'])
                return self._resposta(lead, '%s: etapa %s, funil %s (registro fictício).' %
                    (lead_id, lead['etapa'], pipeline['nome']), 'consultar_status')
            leitura = self.nlu.interpretar(texto, self.hoje)
            if leitura.intencao == AGENDAR or lead['agendando']:
                lead['agendando'] = True
                self._coletar(lead, texto, leitura)
                return self._agendar(lead)
            return self._resposta(lead,
                'Nesta demo posso consultar a etapa, simular uma reunião ou registrar handoff; o que você prefere?', 'indefinida')