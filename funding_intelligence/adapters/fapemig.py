"""FAPEMIG: API REST oficial do portal de chamadas.

Reconhecimento de 21/11/2026 (Fomenta360): a página
fapemig.br/oportunidades/chamadas-e-editais é um app Nuxt alimentado pelo
WordPress em api.site.fapemig.br, que publica a rota
`/wp-json/fapemig-chamadas-e-editais/v1/chamadas` sem autenticação, com
número, situação, datas de submissão, valor, público-alvo e anexos de cada
chamada (196 no total, 100 por página).
"""

from __future__ import annotations

import json
import re
from typing import Any

from funding_intelligence.adapters.base import BaseAdapter
from funding_intelligence.adapters.generico import instrumento, temas
from funding_intelligence.models import clean_text, opportunity

API = "https://api.site.fapemig.br/wp-json/fapemig-chamadas-e-editais/v1/chamadas"
PAGINA = "https://fapemig.br/oportunidades/chamadas-e-editais/{slug}"

PUBLICO = {
    "ict": ["ict", "universidade"],
    "pesquisadores": ["pesquisador"],
    "empresas": ["empresa", "startup"],
    "ambiente-de-inovacao": ["outros"],
    "governo": ["estado", "municipio"],
}
SITUACAO = {"aberta": "open", "analise": "closed", "resultados": "closed", "encerrada": "closed"}


def sem_html(valor: Any) -> str:
    return clean_text(re.sub(r"<[^>]+>", " ", str(valor or "")))


class FapemigAdapter(BaseAdapter):
    id = "fapemig"
    name = "FAPEMIG"
    url = "https://fapemig.br/oportunidades/chamadas-e-editais"

    def collect(self) -> list[dict[str, Any]]:
        if self.fixture:
            itens = json.loads(open(self.fixture, encoding="utf-8").read())["data"]
        else:
            itens, pagina = [], 1
            while True:
                dados = json.loads(self.request_bytes(f"{API}?per_page=100&page={pagina}"))
                itens.extend(dados.get("data") or [])
                if pagina >= int((dados.get("pagination") or {}).get("total_pages") or 1):
                    break
                pagina += 1
        return [op for op in (self.parse(item) for item in itens) if op]

    def parse(self, item: dict[str, Any]) -> dict[str, Any] | None:
        if item.get("publicacao_status") not in (None, "publish"):
            return None
        fim = (item.get("data_fim_submissao") or "")[:10] or None
        continuo = item.get("fluxo_tipo") == "continuo"
        situacao = item.get("status_chamada") or ""
        status = SITUACAO.get(situacao, "unknown")
        if status == "open" and fim and fim < self.today.isoformat():
            status = "closed"
        publicos = [s.get("slug") for s in (item.get("publico_alvo") or {}).get("selected", [])]
        tipos = [t for slug_ in publicos for t in PUBLICO.get(slug_, [])] or ["outros"]
        texto = " ".join(sem_html(item.get(k)) for k in ("descricao_chamada", "quem_pode_participar", "o_que_pode_ser_financiado"))
        anexos = [
            {
                "title": clean_text(a.get("descricao") or a.get("nome_original")) or "Anexo",
                "url": a["url_anexo"],
                "published": None,
            }
            for a in item.get("anexos") or []
            if a.get("url_anexo")
        ]
        numero = re.match(r"0*(\d+)/(\d{4})", item.get("numero") or "")
        try:
            valor = float(item.get("valor")) if item.get("valor") not in (None, "", "None") else None
        except ValueError:
            valor = None
        return opportunity(
            source_id=self.id,
            source_name=self.name,
            source_url=PAGINA.format(slug=item.get("slug")),
            checked_at=self.checked_at,
            external_id=f"{int(numero.group(1))}-{numero.group(2)}" if numero else str(item.get("id")),
            title=item.get("titulo") or "",
            funder="FAPEMIG",
            status="open" if continuo and situacao == "aberta" else status,
            published=(item.get("data_publicacao") or "")[:10] or None,
            deadline=None if continuo else fim,
            organization_types=tipos,
            geography=["MG"],
            themes=temas(f"{item.get('titulo')} {texto}"),
            instrument_type=instrumento(f"{item.get('titulo')} {texto}", "auxilio_pesquisa"),
            repayable=False,
            program_budget=valor,
            documents=anexos,
            description=texto[:1200] or None,
            channel="fluxo_continuo" if continuo else "chamada_publica",
            closed=fim if status == "closed" else None,
        )
