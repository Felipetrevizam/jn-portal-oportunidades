"""Diário Oficial da União, seção 3: rede de segurança (Fomenta360).

Lê a edição do dia em in.gov.br/leiturajornal (JSON embutido na página, com
todos os atos da seção) e separa os avisos de chamada pública de pesquisa,
inovação e fomento de órgãos federais. Serve para achar chamada de órgão que
ainda não tem conector: cada achado vai para a revisão como pista, com o link
do ato. O texto completo de cada candidato é aberto para tirar o prazo.
"""

from __future__ import annotations

import json
import re
from datetime import timedelta
from typing import Any

from bs4 import BeautifulSoup

from funding_intelligence.adapters.base import BaseAdapter
from funding_intelligence.adapters.generico import extrair_numero, extrair_prazo, instrumento, temas, tipos_de_proponente
from funding_intelligence.models import clean_text, opportunity

LEITURA = "https://www.in.gov.br/leiturajornal?data={data}&secao=dou3"
ATO = "https://www.in.gov.br/web/dou/-/{slug}"
DIAS = 3
MAX_ATOS = 25

CHAMADA = re.compile(r"chamada p[úu]blica|chamamento p[úu]blico|edital de sele[çc][ãa]o|sele[çc][ãa]o p[úu]blica|edital de chamada", re.I)
FOMENTO = re.compile(
    r"pesquisa|inova[çc][ãa]o|subven[çc][ãa]o|fomento|desenvolvimento tecnol[óo]gico|bolsas? de|p&d|ct&i|startups?|"
    r"extens[ãa]o tecnol[óo]gica|empreendedorismo",
    re.I,
)
FORA = re.compile(
    r"licita[çc][ãa]o|preg[ãa]o|dispensa|extrato|concurso p[úu]blico|notifica[çc][ãa]o|resultado|homologa|retifica|cultural|aldir blanc|"
    r"est[áa]gio|processo seletivo simplificado|vagas? no curso|provimento de vagas|candidatos? (a|ao|à) (curso|mestrado|doutorado)|"
    r"credenciamento de (leiloeiro|m[ée]dico|cl[íi]nica)",
    re.I,
)


class DouAdapter(BaseAdapter):
    id = "dou-chamadas"
    name = "Diário Oficial da União · Chamadas de pesquisa e inovação (seção 3)"
    url = "https://www.in.gov.br/leiturajornal?secao=dou3"

    def collect(self) -> list[dict[str, Any]]:
        atos: list[dict[str, Any]] = []
        if self.fixture:
            atos = json.loads(open(self.fixture, encoding="utf-8").read())["jsonArray"]
        else:
            for dias in range(DIAS):
                dia = self.today - timedelta(days=dias)
                html = self.fetch_bytes(LEITURA.format(data=dia.strftime("%d-%m-%Y"))).decode("utf-8", errors="replace")
                m = re.search(r'<script id="params" type="application/json">(.*?)</script>', html, re.S)
                if m:
                    atos.extend(json.loads(m.group(1)).get("jsonArray", []))
        candidatos = [a for a in atos if self.interessa(a)]
        resultado, vistos = [], set()
        for ato in candidatos[:MAX_ATOS]:
            if ato.get("urlTitle") in vistos:
                continue
            vistos.add(ato.get("urlTitle"))
            resultado.append(self.parse(ato))
        if not atos:
            raise ValueError("DOU: nenhuma edição lida")
        return resultado

    @staticmethod
    def interessa(ato: dict[str, Any]) -> bool:
        orgao = ato.get("hierarchyStr") or ""
        texto = f"{ato.get('title', '')} {ato.get('content', '')}"
        if orgao.startswith(("Prefeituras", "Entidades de Fiscalização", "Poder Judiciário", "Poder Legislativo")):
            return False
        return bool(CHAMADA.search(texto) and FOMENTO.search(texto) and not FORA.search(texto[:300]))

    def parse(self, ato: dict[str, Any]) -> dict[str, Any]:
        link = ATO.format(slug=ato.get("urlTitle"))
        texto = clean_text(ato.get("content"))
        if not self.fixture:
            try:
                sopa = BeautifulSoup(self.fetch_bytes(link), "html.parser")
                corpo = sopa.select_one(".texto-dou") or sopa.body
                texto = clean_text(corpo.get_text(" ", strip=True)) or texto
            except Exception:
                pass
        prazo = extrair_prazo(texto)
        status = "unknown" if not prazo else ("open" if prazo >= self.today.isoformat() else "closed")
        orgao = (ato.get("hierarchyStr") or "").split("/")
        publicado = ato.get("pubDate")
        return opportunity(
            source_id=self.id,
            source_name=self.name,
            source_url=link,
            checked_at=self.checked_at,
            external_id=ato.get("urlTitle"),
            title=f"{orgao[-1] if orgao else ''}: {clean_text(ato.get('title'))}"[:300],
            funder=clean_text(orgao[1] if len(orgao) > 1 else (orgao[0] if orgao else "União")),
            status=status,
            published=f"{publicado[6:10]}-{publicado[3:5]}-{publicado[0:2]}" if publicado and len(publicado) == 10 else None,
            deadline=prazo,
            organization_types=tipos_de_proponente(texto[:3000]) or ["outros"],
            geography=["BR"],
            themes=temas(texto[:3000]),
            instrument_type=instrumento(texto[:2000], "outros"),
            repayable=False,
            description=texto[:1200] or None,
            closed=prazo if status == "closed" else None,
        )
