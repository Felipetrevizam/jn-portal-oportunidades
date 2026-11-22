import importlib.util
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
spec = importlib.util.spec_from_file_location("editais_markdown", Path(__file__).resolve().parents[1] / "scripts" / "editais_markdown.py")
em = importlib.util.module_from_spec(spec)
spec.loader.exec_module(em)

from funding_intelligence.markdown_editais import paginas_sem_texto


def doc(title, url, published=None):
    return {"title": title, "url": url, "published": published}


class EscolhaDoEditalTests(unittest.TestCase):
    def test_prefere_rerratificacao_recente_a_manual_e_resultado(self):
        op = {"documents": [
            doc("Manual do Cliente", "https://x/manual.pdf"),
            doc("Regulamento", "https://x/reg.pdf/a", "2026-03-12"),
            doc("Rerratificação do Regulamento", "https://x/reg2.pdf/b", "2026-09-28"),
            doc("Resultado parcial", "https://x/res.pdf", "2026-10-13"),
        ]}
        self.assertEqual("https://x/reg2.pdf/b", em.pdf_do_edital(op)["url"])

    def test_sem_rotulo_usa_primeiro_pdf_que_nao_e_manual(self):
        op = {"documents": [doc("FAQ", "https://x/faq.pdf"), doc("Documento", "https://x/doc.pdf")]}
        self.assertEqual("https://x/doc.pdf", em.pdf_do_edital(op)["url"])

    def test_sem_pdf_nada_a_converter(self):
        self.assertIsNone(em.pdf_do_edital({"documents": [doc("Edital", "https://x/pagina")]}))

    def test_nome_de_arquivo_seguro(self):
        self.assertEqual("finep-1132029.md", em.nome_arquivo("finep-1132029"))
        self.assertNotIn("/", em.nome_arquivo("../../etc/passwd"))

    def test_pdf_invalido_nao_quebra_contagem_de_paginas(self):
        self.assertEqual((0, 0), paginas_sem_texto(b"isto nao e pdf"))


@unittest.skipUnless(importlib.util.find_spec("docling"), "Docling não instalado (só no job de editais)")
class ConversaoTests(unittest.TestCase):
    def test_pdf_minimo_vira_markdown(self):
        from funding_intelligence.markdown_editais import converter_pdf
        pdf = (Path(__file__).parent / "fixtures" / "editais" / "edital_minimo.pdf").read_bytes()
        conv = converter_pdf(pdf)
        self.assertIn("Data limite", conv.markdown)
        self.assertEqual(64, len(conv.sha256))


if __name__ == "__main__":
    unittest.main()
