from datetime import date
from pathlib import Path
import tempfile
import unittest

from funding_intelligence.adapters.fapemig import FapemigAdapter
from funding_intelligence.adapters.generico import (
    AdaptadorGenerico, Config, achatar, criar_adaptador, extrair_numero, extrair_prazo, limpar_titulo,
)
from bs4 import BeautifulSoup

FIXTURES = Path(__file__).parent / "fixtures"


class PrazoTests(unittest.TestCase):
    def test_intervalo_fica_com_o_fim(self):
        self.assertEqual("2026-12-08", extrair_prazo("Inscrições: 26/10/2026 a 08/12/2026"))

    def test_data_limite_com_dois_pontos(self):
        self.assertEqual("2026-11-23", extrair_prazo("Data-limite para submissão de propostas: 23/11/2026 Área: X"))

    def test_data_por_extenso(self):
        self.assertEqual("2027-02-12", extrair_prazo("Prazo: a proposta deve ser enviada até 12 de fevereiro de 2027"))

    def test_resultado_nao_e_prazo(self):
        self.assertIsNone(extrair_prazo("Resultado final: 30/01/2027. Vigência de 24 meses."))

    def test_cronograma_com_duas_submissoes_fica_com_a_ultima(self):
        texto = "Submissão 1ª etapa: até 10/12/2026. Submissão 2ª etapa: até 20/02/2027. Resultado: 30/04/2027"
        self.assertEqual("2027-02-20", extrair_prazo(texto))

    def test_numero_da_chamada(self):
        self.assertEqual("12-2026", extrair_numero("Edital FAPERJ Nº 12/2026 – Programa"))
        self.assertEqual("19-2026", extrair_numero("CHAMADA FAPEMIG nº 019/2026"))

    def test_titulo_sem_rabo_de_publicacao(self):
        self.assertEqual(
            "Edital FAPERJ Nº 05/2026 – Pesquisador Visitante (PV)",
            limpar_titulo("Edital FAPERJ Nº 05/2026 – Pesquisador Visitante (PV) Publicado em DO de 10/02/2026"),
        )


class MotorTests(unittest.TestCase):
    def test_texto_inline_ao_lado_de_bloco_nao_se_perde(self):
        sopa = BeautifulSoup(
            '<div><h3><a href="/18456">Chamada X</a></h3><span>Data-limite: 23/11/2026</span></div>', "html.parser"
        )
        blocos = achatar(sopa.div, "https://fapesp.br/")
        self.assertEqual(["Chamada X", "Data-limite: 23/11/2026"], [b.texto for b in blocos])
        self.assertEqual("https://fapesp.br/18456", blocos[0].links[0][1])

    def _coletar(self, html: str, **kw) -> list[dict]:
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(html)
        config = Config(id="teste", nome="Teste", url="https://exemplo.gov.br/editais", financiador="Teste", **kw)
        return criar_adaptador(config)(fixture=f.name, today=date(2026, 11, 21)).collect()

    def test_pagina_corrida_vira_uma_chamada_por_titulo(self):
        html = """<main>
          <p><strong>Edital X Nº 01/2026 – Apoio a Startups</strong></p>
          <p>Submissão de propostas: de 01/10/2026 a 30/11/2026</p>
          <p><a href="/docs/edital-01.pdf">Edital</a> <a href="/docs/anexo.pdf">Anexo I</a></p>
          <p><strong>Edital X Nº 02/2026 – Bolsas</strong></p>
          <p>Inscrições até 10/11/2026</p>
          <p><strong>Edital X Nº 03/2024 – Antigo</strong></p>
        </main>"""
        itens = self._coletar(html, inicio_titulo=r"^Edital X N", ano_minimo=2025, detalhe=False, ler_pdf=False)
        self.assertEqual(["teste-1-2026", "teste-2-2026"], [i["id"] for i in itens])
        self.assertEqual(("open", "2026-11-30"), (itens[0]["status"], itens[0]["dates"]["deadline"]))
        self.assertEqual(("closed", "2026-11-10"), (itens[1]["status"], itens[1]["dates"]["deadline"]))
        self.assertEqual(2, len(itens[0]["documents"]))
        self.assertIn("startup", itens[0]["eligibility"]["organization_types"])

    def test_descarte_olha_so_o_titulo(self):
        # Regressão: o bloco de abertura da FAPERJ traz o edital inteiro, com
        # "resultado final" lá no meio; a chamada não pode ser descartada por isso.
        html = """<main><p>Edital X Nº 01/2026 – Programa A. Submissão até 30/11/2026.
          Resultado final: 30/01/2027.</p><p>Edital X Nº 02/2026 – Programa B</p>
          <p>Resultado final do Edital X Nº 03/2026</p></main>"""
        itens = self._coletar(html, inicio_titulo=r"^(Edital X N|Resultado)", detalhe=False, ler_pdf=False)
        self.assertEqual(["teste-1-2026", "teste-2-2026"], [i["id"] for i in itens])

    def test_cards_por_seletor(self):
        html = """<main><div class="card"><div><p>Inscrições: 28/11/2026 a 16/01/2027</p></div>
          <div><strong>Chamada Regional A</strong><p>Para empresas industriais.</p></div>
          <div><a href="https://exemplo.gov.br/a">Acesse</a></div></div></main>"""
        itens = self._coletar(html, item_seletor="div.card", titulo_seletor="strong", detalhe=False, ler_pdf=False)
        self.assertEqual("Chamada Regional A", itens[0]["title"])
        self.assertEqual("2027-01-16", itens[0]["dates"]["deadline"])
        self.assertEqual("https://exemplo.gov.br/a", itens[0]["source"]["url"])

    def test_sem_prazo_em_pagina_de_abertas_fica_aberta(self):
        html = '<main><p><a href="/p/x">Programa Y de Bolsas 2026</a></p></main>'
        itens = self._coletar(html, inicio_link=r"/p/", lista_abertas=True, detalhe=False, ler_pdf=False)
        self.assertEqual(("open", None), (itens[0]["status"], itens[0]["dates"]["deadline"]))

    def test_pagina_sem_chamada_falha(self):
        with self.assertRaises(ValueError):
            self._coletar("<main><p>Nada aqui</p></main>", inicio_titulo=r"^Edital", detalhe=False)


class FapemigTests(unittest.TestCase):
    def test_api_oficial(self):
        itens = FapemigAdapter(fixture=str(FIXTURES / "fapemig" / "chamadas.json"), today=date(2026, 11, 21)).collect()
        self.assertEqual(12, len(itens))
        minas = next(i for i in itens if i["external_id"] == "19-2026")
        self.assertEqual(("open", "2027-02-12"), (minas["status"], minas["dates"]["deadline"]))
        self.assertEqual(80_000_000, minas["funding"]["program_budget"])
        self.assertTrue(minas["documents"][0]["url"].endswith(".pdf"))
        self.assertEqual(["MG"], minas["eligibility"]["geography"])


if __name__ == "__main__":
    unittest.main()
