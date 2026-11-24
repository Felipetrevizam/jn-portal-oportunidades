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


class DownloadTests(unittest.TestCase):
    def test_url_com_acento_e_ordinal_vira_ascii(self):
        url = em.url_segura("https://www.faperj.br/downloads/editais/Edital_Nº_25_2026 Pós.pdf?x=ç")
        url.encode("ascii")  # não pode levantar UnicodeEncodeError
        self.assertEqual(
            "https://www.faperj.br/downloads/editais/Edital_N%C2%BA_25_2026%20P%C3%B3s.pdf?x=%C3%A7", url
        )

    def test_url_ja_codificada_nao_e_codificada_de_novo(self):
        url = "https://x.gov.br/a%20b/Edital%20N%C2%BA%201.pdf?id=1&v=2"
        self.assertEqual(url, em.url_segura(url))

    def test_host_que_derrubou_a_conexao_e_pulado(self):
        import urllib.error

        hosts = em.HostsFora()
        self.assertFalse(hosts.fora("https://cnpq.br/a.pdf"))
        hosts.registrar("https://cnpq.br/a.pdf", urllib.error.URLError(ConnectionResetError(104, "reset")))
        self.assertTrue(hosts.fora("https://cnpq.br/b.pdf"))
        self.assertFalse(hosts.fora("https://finep.gov.br/c.pdf"))

    def test_erro_que_nao_e_de_rede_nao_tira_o_host(self):
        hosts = em.HostsFora()
        hosts.registrar("https://finep.gov.br/a.pdf", ValueError("não é PDF"))
        self.assertFalse(hosts.fora("https://finep.gov.br/b.pdf"))


class OrcamentoDeTempoTests(unittest.TestCase):
    def test_para_de_comecar_conversao_depois_do_limite(self):
        relogio = iter([0.0, 10 * 60, 41 * 60])
        orcamento = em.Orcamento(minutos=40, relogio=lambda: next(relogio))
        self.assertFalse(orcamento.esgotado())  # 10 min
        self.assertTrue(orcamento.esgotado())   # 41 min


class TetoPorEditalTests(unittest.TestCase):
    def test_reserva_tira_o_teto_de_um_edital_do_orcamento(self):
        relogio = iter([0.0, 26 * 60, 28 * 60])
        orcamento = em.Orcamento(minutos=35, relogio=lambda: next(relogio), reserva_minutos=8)
        self.assertFalse(orcamento.esgotado())  # 26 min: ainda cabe um edital de 8
        self.assertTrue(orcamento.esgotado())   # 28 min: não cabe mais

    @unittest.skipUnless(hasattr(em.signal, "SIGALRM"), "precisa de SIGALRM")
    def test_conversao_lenta_e_interrompida(self):
        import time as _t
        with self.assertRaises(em.TempoDoEditalEsgotado):
            with em.tempo_maximo(1):
                _t.sleep(3)

    def test_conversao_rapida_passa(self):
        with em.tempo_maximo(5):
            valor = 1 + 1
        self.assertEqual(2, valor)
