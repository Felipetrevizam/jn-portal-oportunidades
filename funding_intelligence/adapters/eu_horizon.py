"""Horizon Europe: tópicos abertos e previstos no portal Funding & Tenders (Fomenta360).

Usa a API de busca do portal (api.tech.ec.europa.eu/search-api), com a chave
pública `SEDIA` que o próprio portal usa. Lógica de datas e situação portada
do conector `ft_search_v2` do ConvocaRadar-IA (MIT, julian8811).

Brasileiros participam do Horizon Europe em consórcio; o financiamento direto
depende de cada tópico (e das chamadas conjuntas com as FAPs via CONFAP). Por
isso a fonte vem como internacional e a elegibilidade fica para a revisão.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from funding_intelligence.adapters.base import BaseAdapter
from funding_intelligence.adapters.generico import temas
from funding_intelligence.models import clean_text, opportunity

BUSCA = "https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA&text=***&pageSize=100&pageNumber={pagina}"
TOPICO = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/{id}"
HORIZON = "43108390"
CONSULTA = {
    "bool": {
        "must": [
            {"terms": {"type": ["1", "2"]}},
            {"terms": {"status": ["31094501", "31094502"]}},  # aberto, previsto
            {"terms": {"frameworkProgramme": [HORIZON]}},
        ]
    }
}
MAX_PAGINAS = 10


def primeiro(valor: Any) -> str | None:
    if isinstance(valor, list):
        return str(valor[0]).strip() if valor else None
    return str(valor).strip() if valor else None


class EuHorizonAdapter(BaseAdapter):
    id = "eu-horizon"
    name = "Horizon Europe · Funding & Tenders (UE)"
    url = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/calls-for-proposals"

    def _pagina(self, pagina: int) -> dict[str, Any]:
        fronteira = uuid.uuid4().hex
        partes = []
        for nome, valor in (("query", CONSULTA), ("languages", ["en"])):
            partes.append(
                f"--{fronteira}\r\nContent-Disposition: form-data; name=\"{nome}\"; filename=\"blob\"\r\n"
                f"Content-Type: application/json\r\n\r\n{json.dumps(valor)}\r\n"
            )
        corpo = ("".join(partes) + f"--{fronteira}--\r\n").encode()
        resposta = self.request_bytes(
            BUSCA.format(pagina=pagina), method="POST", data=corpo,
            headers={"Content-Type": f"multipart/form-data; boundary={fronteira}"},
        )
        return json.loads(resposta)

    def collect(self) -> list[dict[str, Any]]:
        if self.fixture:
            resultados = json.loads(open(self.fixture, encoding="utf-8").read())["results"]
        else:
            resultados, pagina = [], 1
            while pagina <= MAX_PAGINAS:
                dados = self._pagina(pagina)
                lote = dados.get("results") or []
                resultados.extend(lote)
                if len(lote) < 100 or len(resultados) >= int(dados.get("totalResults") or 0):
                    break
                pagina += 1
        vistos, itens = set(), []
        for r in resultados:
            item = self.parse(r)
            if item and item["id"] not in vistos:
                vistos.add(item["id"])
                itens.append(item)
        return itens

    def parse(self, r: dict[str, Any]) -> dict[str, Any] | None:
        m = r.get("metadata") or {}
        identificador = primeiro(m.get("identifier"))
        if not identificador:
            return None
        # Tópico em duas etapas tem várias datas-limite: vale a última.
        prazos = sorted(str(d)[:10] for d in (m.get("deadlineDate") or []) if d)
        prazo = prazos[-1] if prazos else None
        inicio = (primeiro(m.get("startDate")) or "")[:10] or None
        status = "open" if not prazo or prazo >= self.today.isoformat() else "closed"
        titulo = primeiro(m.get("title")) or r.get("summary") or identificador
        descricao = clean_text(r.get("summary") or r.get("content") or "")
        return opportunity(
            source_id=self.id,
            source_name=self.name,
            source_url=TOPICO.format(id=identificador.lower()),
            checked_at=self.checked_at,
            external_id=identificador,
            title=f"{identificador} – {clean_text(titulo)}"[:300],
            funder="Comissão Europeia · Horizon Europe",
            status=status,
            published=inicio,
            deadline=prazo,
            organization_types=["ict", "universidade", "empresa"],
            geography=["UE", "INTERNACIONAL"],
            themes=temas(f"{titulo} {descricao}"),
            instrument_type="auxilio_pesquisa",
            repayable=False,
            description=descricao[:1200] or None,
            closed=prazo if status == "closed" else None,
        )
