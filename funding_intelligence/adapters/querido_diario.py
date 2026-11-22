"""Querido Diário: diários oficiais municipais (Fomenta360).

Rede de segurança para editais municipais de inovação (leis municipais de
inovação, programas de startups, prêmios). Usa a API pública do Querido
Diário (Open Knowledge Brasil), em api.queridodiario.org.br, buscando nos
últimos dias os trechos que falam de chamada/edital junto de inovação,
pesquisa ou startup. Cada trecho vira uma pista para a revisão, com o link
do diário.
"""

from __future__ import annotations

import json
import re
from datetime import timedelta
from typing import Any
from urllib.parse import quote

from funding_intelligence.adapters.base import BaseAdapter
from funding_intelligence.adapters.generico import extrair_prazo, temas
from funding_intelligence.models import clean_text, opportunity

API = (
    "https://api.queridodiario.org.br/gazettes?querystring={q}&published_since={desde}"
    "&size=100&excerpt_size=600&number_of_excerpts=3"
)
CONSULTAS = (
    '"chamada pública" inovação',
    '"edital" startup',
    '"chamamento público" "inovação"',
    '"edital" "fomento à inovação"',
)
DIAS = 7
CHAMADA = re.compile(r"chamada p[úu]blica|chamamento p[úu]blico|edital", re.I)
FOMENTO = re.compile(r"inova[çc][ãa]o|startups?|pesquisa|tecnol[óo]gic|empreendedor", re.I)
FORA = re.compile(
    r"licita[çc][ãa]o|preg[ãa]o|concurso p[úu]blico|processo seletivo|contrato n|extrato|homologa|merenda|obra|"
    r"g[êe]neros aliment|agricultura familiar|pnae|assinado digitalmente|credenciamento de (m[ée]dic|cl[íi]nic|leiloeir)",
    re.I,
)
JANELA = 250


def interessa(texto: str) -> bool:
    """Chamada/edital com inovação, pesquisa ou startup a até 250 caracteres."""
    if FORA.search(texto):
        return False
    for m in CHAMADA.finditer(texto):
        if FOMENTO.search(texto[max(0, m.start() - JANELA): m.end() + JANELA]):
            return True
    return False


class QueridoDiarioAdapter(BaseAdapter):
    id = "querido-diario"
    name = "Querido Diário · Diários oficiais municipais (inovação)"
    url = "https://queridodiario.ok.org.br/"

    def collect(self) -> list[dict[str, Any]]:
        if self.fixture:
            diarios = json.loads(open(self.fixture, encoding="utf-8").read())["gazettes"]
        else:
            desde = (self.today - timedelta(days=DIAS)).isoformat()
            diarios = []
            for consulta in CONSULTAS:
                dados = json.loads(self.request_bytes(API.format(q=quote(consulta), desde=desde)))
                diarios.extend(dados.get("gazettes") or [])
        resultado, vistos = [], set()
        for diario in diarios:
            for trecho in diario.get("excerpts") or []:
                texto = clean_text(trecho)
                if not interessa(texto):
                    continue
                chave = (diario.get("url"), texto[:120])
                if chave in vistos:
                    continue
                vistos.add(chave)
                resultado.append(self.parse(diario, texto))
        return resultado

    def parse(self, diario: dict[str, Any], texto: str) -> dict[str, Any]:
        prazo = extrair_prazo(texto)
        status = "unknown" if not prazo else ("open" if prazo >= self.today.isoformat() else "closed")
        municipio = clean_text(diario.get("territory_name"))
        uf = clean_text(diario.get("state_code"))
        resumo = re.sub(r"[.\s]{4,}", " ", texto)
        return opportunity(
            source_id=self.id,
            source_name=self.name,
            source_url=diario.get("url") or self.url,
            checked_at=self.checked_at,
            external_id=None,
            title=f"{municipio}/{uf} – {resumo[:160]}",
            funder=f"Prefeitura de {municipio}",
            status=status,
            published=diario.get("date"),
            deadline=prazo,
            organization_types=["startup", "empresa", "pessoa_fisica"],
            geography=[uf] if uf else ["BR"],
            themes=temas(texto),
            instrument_type="outros",
            repayable=False,
            documents=[{"title": "Diário oficial (texto)", "url": diario["txt_url"], "published": diario.get("date")}]
            if diario.get("txt_url") else [],
            description=resumo[:1200],
            closed=prazo if status == "closed" else None,
        )
