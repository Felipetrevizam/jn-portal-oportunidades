"""PNCP: contratações públicas de inovação (Fomenta360).

Só a parte de compras que é fomento à inovação: Contrato Público para Solução
Inovadora (CPSI, LC 182/2021) e encomenda tecnológica. Usa a busca pública do
PNCP (`/api/search`), a mesma que o portal usa, filtrando editais que estão
recebendo proposta.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

from funding_intelligence.adapters.base import BaseAdapter
from funding_intelligence.adapters.generico import temas
from funding_intelligence.models import clean_text, opportunity

BUSCA = (
    "https://pncp.gov.br/api/search/?q={termo}&tipos_documento=edital&ordenacao=-data"
    "&pagina=1&tam_pagina=100&status=recebendo_proposta"
)
TERMOS = ('"solução inovadora"', '"encomenda tecnológica"', "CPSI")


class PncpCpsiAdapter(BaseAdapter):
    id = "pncp-cpsi"
    name = "PNCP · Contratação de solução inovadora (CPSI) e encomenda tecnológica"
    url = "https://pncp.gov.br/app/editais?q=%22solu%C3%A7%C3%A3o%20inovadora%22&status=recebendo_proposta"

    def collect(self) -> list[dict[str, Any]]:
        if self.fixture:
            itens = json.loads(open(self.fixture, encoding="utf-8").read())["items"]
        else:
            itens = []
            for termo in TERMOS:
                itens.extend(json.loads(self.request_bytes(BUSCA.format(termo=quote(termo))))["items"])
        vistos, resultado = set(), []
        for item in itens:
            chave = item.get("numero_controle_pncp") or item.get("item_url")
            if chave in vistos:
                continue
            vistos.add(chave)
            resultado.append(self.parse(item))
        return resultado

    def parse(self, item: dict[str, Any]) -> dict[str, Any]:
        fim = (item.get("data_fim_vigencia") or "")[:10] or None
        status = "open" if not fim or fim >= self.today.isoformat() else "closed"
        orgao = clean_text(item.get("orgao_nome"))
        descricao = clean_text(item.get("description"))
        try:
            valor = float(item["valor_global"]) if item.get("valor_global") not in (None, "None", "") else None
        except (TypeError, ValueError):
            valor = None
        return opportunity(
            source_id=self.id,
            source_name=self.name,
            source_url=f"https://pncp.gov.br/app/editais/{item.get('orgao_cnpj')}/{item.get('ano')}/{item.get('numero_sequencial')}",
            checked_at=self.checked_at,
            external_id=item.get("numero_controle_pncp"),
            title=f"{orgao}: {clean_text(item.get('title'))} – {descricao}"[:300],
            funder=orgao,
            status=status,
            published=(item.get("data_publicacao_pncp") or "")[:10] or None,
            deadline=fim,
            organization_types=["startup", "empresa"],
            geography=[item["uf"]] if item.get("uf") else ["BR"],
            themes=temas(descricao),
            instrument_type="contratacao_pdi",
            repayable=False,
            program_budget=valor,
            description=descricao or None,
            closed=fim if status == "closed" else None,
        )
