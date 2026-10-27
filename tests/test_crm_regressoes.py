"""Reproduções fictícias dos achados da revisão independente."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from crm_demo import CRM


class RegressoesCRM(unittest.TestCase):
    def test_optout_nao_mascara_deteccao_sensivel_nos_dois_caminhos(self):
        marcador = 'MARCADOR-FICTICIO-NAO-RETER'
        mensagem = 'não quero mais receber mensagens; minha senha: ' + marcador
        crm = CRM()
        resultado = crm.mensagem('DEMO-001', mensagem)
        self.assertEqual(resultado['intencao'], 'opt_out')
        self.assertTrue(crm.consultar('DEMO-001')['opt_out'])
        self.assertNotIn(marcador, json.dumps(crm.estado(), ensure_ascii=False))
        outro = CRM()
        campos = dict(nome='Pessoa Demo', email='demo@example.com',
                      data='2026-11-03', hora='15:00', assunto=mensagem)
        with self.assertRaises(ValueError):
            outro.reservar('DEMO-001', campos)
        self.assertFalse(outro.estado()['reservas'])
        self.assertNotIn(marcador, json.dumps(outro.estado(), ensure_ascii=False))

    def test_reserva_direta_encerra_coleta_anterior(self):
        crm = CRM()
        crm.mensagem('DEMO-001', 'Quero agendar dia 03/11 às 15h')
        self.assertTrue(crm.consultar('DEMO-001')['agendando'])
        campos = dict(nome='Pessoa Demo', email='demo@example.com',
                      data='2026-11-04', hora='10:00', assunto='atendimento')
        crm.reservar('DEMO-001', campos)
        lead = crm.consultar('DEMO-001')
        self.assertFalse(lead['agendando'])
        self.assertIsNone(lead['esperado'])
        self.assertIsNone(lead['periodo'])
        self.assertEqual(lead['campos'], campos)
        crm.mensagem('DEMO-001', 'meu nome é Pessoa Demo, demo@example.com, sobre atendimento')
        reservas = crm.estado()['reservas']
        self.assertEqual(len(reservas), 1)
        self.assertEqual((reservas[0]['data'], reservas[0]['hora']), ('2026-11-04', '10:00'))
        self.assertIn('15:00', crm.disponibilidade('2026-11-03'))

    def test_correcao_data_nao_preenche_assunto_pendente(self):
        crm = CRM()
        crm.mensagem('DEMO-001', 'Quero agendar dia 03/11 às 15h')
        crm.mensagem('DEMO-001', 'Pessoa Demo')
        crm.mensagem('DEMO-001', 'demo@example.com')
        self.assertEqual(crm.consultar('DEMO-001')['esperado'], 'assunto')
        resultado = crm.mensagem('DEMO-001', 'na verdade dia 04/11')
        lead = crm.consultar('DEMO-001')
        self.assertNotIn('assunto', lead['campos'])
        self.assertEqual(lead['campos']['data'], '2026-11-04')
        self.assertEqual(resultado['faltantes'], ['assunto'])
        self.assertFalse(crm.estado()['reservas'])
        crm.mensagem('DEMO-001', 'atendimento')
        self.assertEqual(len(crm.estado()['reservas']), 1)
        self.assertEqual(crm.estado()['reservas'][0]['assunto'], 'atendimento')

    def test_correcao_hora_impossivel_invalida_horario_anterior(self):
        for correcao in ('na verdade às 25', 'na verdade 25h', 'na verdade 25:00', 'na verdade 15:99'):
            with self.subTest(correcao=correcao):
                crm = CRM()
                crm.mensagem('DEMO-001', 'Quero agendar dia 03/11 às 15h')
                crm.mensagem('DEMO-001', 'Pessoa Demo')
                crm.mensagem('DEMO-001', correcao)
                self.assertNotIn('hora', crm.consultar('DEMO-001')['campos'])
                crm.mensagem('DEMO-001', 'demo@example.com')
                crm.mensagem('DEMO-001', 'sobre atendimento')
                self.assertFalse(crm.estado()['reservas'])
                self.assertEqual(crm.consultar('DEMO-001')['esperado'], 'hora')
                self.assertIn('15:00', crm.disponibilidade('2026-11-03'))

    def test_correcao_hora_impossivel_as_minutos(self):
        """Teste específico para o caso 'às 15:99' identificado na revisão independente."""
        crm = CRM()
        crm.mensagem('DEMO-001', 'Quero agendar dia 03/11 às 15h')
        crm.mensagem('DEMO-001', 'Pessoa Demo')
        crm.mensagem('DEMO-001', 'demo@example.com')
        # Teste específico: "na verdade às 15:99" - minutos 99 são inválidos
        result = crm.mensagem('DEMO-001', 'na verdade às 15:99')
        lead = crm.consultar('DEMO-001')
        self.assertNotIn('hora', lead['campos'], 'Hora com minutos inválidos (99) deve ser removida')
        self.assertFalse(crm.estado()['reservas'], 'Nenhuma reserva deve ser criada')
        self.assertEqual(lead['esperado'], 'hora', 'Deve pedir horário novamente')
        self.assertIn('15:00', crm.disponibilidade('2026-11-03'), '15:00 deve estar disponível')


if __name__ == '__main__':
    unittest.main(verbosity=2)
