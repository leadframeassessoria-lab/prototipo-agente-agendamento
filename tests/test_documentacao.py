"""Regressão dos links relativos após arquivar o README original."""
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTOS = (
    'README.md',
    'docs/roteiro-apresentacao.md',
    'docs/legado-agendamento.md',
    'docs/dificuldades-e-melhorias.md',
    'prompts/crm-demo.md',
)


class LinksDocumentacaoTest(unittest.TestCase):
    def test_links_locais_resolvem_da_pasta_do_documento(self):
        verificados = 0
        for nome in DOCUMENTOS:
            documento = ROOT / nome
            for link in re.findall(r'\]\(([^)]+)\)', documento.read_text(encoding='utf-8')):
                if re.match(r'^(?:https?://|#|mailto:)', link):
                    continue
                verificados += 1
                destino = (documento.parent / link.split('#', 1)[0]).resolve()
                with self.subTest(documento=nome, link=link):
                    self.assertIn(ROOT, destino.parents, 'Link escapa do projeto')
                    self.assertTrue(destino.is_file(), 'Link relativo quebrado: ' + link)
        self.assertGreater(verificados, 0)


if __name__ == '__main__':
    unittest.main()
