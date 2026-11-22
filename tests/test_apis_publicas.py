from datetime import date
from pathlib import Path
import json
import unittest

from funding_intelligence.adapters.dou import DouAdapter
from funding_intelligence.adapters.pncp_cpsi import PncpCpsiAdapter

FIXTURES = Path(__file__).parent / "fixtures"


class PncpCpsiTests(unittest.TestCase):
    def test_editais_cpsi_recebendo_proposta(self):
        itens = PncpCpsiAdapter(fixture=str(FIXTURES / "pncp" / "busca.json"), today=date(2026, 11, 21)).collect()
        self.assertEqual(3, len(itens))
        piaui = itens[0]
        self.assertEqual(("open", "2026-12-23"), (piaui["status"], piaui["dates"]["deadline"]))
        self.assertEqual(["PI"], piaui["eligibility"]["geography"])
        self.assertEqual("contratacao_pdi", piaui["instrument"]["type"])
        self.assertIn("pncp.gov.br/app/editais/06553556000191/2026/23", piaui["source"]["url"])


class DouTests(unittest.TestCase):
    def test_separa_chamada_de_pesquisa_de_federal(self):
        atos = json.loads((FIXTURES / "dou" / "dou3.json").read_text(encoding="utf-8"))["jsonArray"]
        escolhidos = [a for a in atos if DouAdapter.interessa(a)]
        self.assertTrue(escolhidos)
        self.assertTrue(all(not a["hierarchyStr"].startswith("Prefeituras") for a in escolhidos))
        self.assertTrue(all("DISPENSA" not in a["title"].upper() for a in escolhidos))

    def test_prefeitura_e_licitacao_ficam_de_fora(self):
        self.assertFalse(DouAdapter.interessa({"hierarchyStr": "Prefeituras/Estado de SP", "title": "Chamada pública", "content": "pesquisa"}))
        self.assertFalse(DouAdapter.interessa({"hierarchyStr": "Ministério X", "title": "AVISO DE LICITAÇÃO", "content": "pesquisa e inovação"}))
        self.assertTrue(DouAdapter.interessa({"hierarchyStr": "Ministério da Ciência", "title": "AVISO DE CHAMADA PÚBLICA",
                                              "content": "Chamada pública para apoio a projetos de pesquisa e inovação"}))


if __name__ == "__main__":
    unittest.main()


class HorizonTests(unittest.TestCase):
    def test_topicos_do_portal(self):
        from funding_intelligence.adapters.eu_horizon import EuHorizonAdapter
        itens = EuHorizonAdapter(fixture=str(FIXTURES / "eu" / "horizon.json"), today=date(2026, 11, 21)).collect()
        self.assertEqual(5, len(itens))
        self.assertTrue(all(i["external_id"].startswith("HORIZON") for i in itens))
        self.assertTrue(all("topic-details" in i["source"]["url"] for i in itens))


class QueridoDiarioTests(unittest.TestCase):
    def test_filtro_de_trechos(self):
        from funding_intelligence.adapters.querido_diario import interessa
        self.assertTrue(interessa("A Prefeitura torna pública a chamada pública para seleção de startups do programa de inovação"))
        self.assertFalse(interessa("Aviso de chamada pública para aquisição de gêneros alimentícios da agricultura familiar"))
        self.assertFalse(interessa("Edital de licitação. Pregão eletrônico. Inovação em serviços"))

    def test_fixture_vira_pistas_com_link_do_diario(self):
        from funding_intelligence.adapters.querido_diario import QueridoDiarioAdapter
        itens = QueridoDiarioAdapter(fixture=str(FIXTURES / "querido_diario" / "busca.json"), today=date(2026, 11, 21)).collect()
        self.assertTrue(all(i["source"]["url"].startswith("https://") for i in itens))
        self.assertTrue(all(len(i["eligibility"]["geography"][0]) == 2 for i in itens))
