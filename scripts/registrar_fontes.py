"""Registra em config/sources.json e na matriz do workflow toda fonte de ADAPTERS.

Uso: python scripts/registrar_fontes.py
Fonte nova entra com os dados da Config (adaptador genérico) ou de TIPOS_MANUAIS.
Fonte já registrada tem nome e URL sincronizados com a classe; o resto é mantido.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from funding_intelligence.adapters import ADAPTERS
from funding_intelligence.adapters.fontes_genericas import FONTES

RAIZ = Path(__file__).resolve().parents[1]
TIPOS_MANUAIS = {
    "fapemig": ("fundacao_estadual", "P1"),
    "pncp-cpsi": ("plataforma_federal", "P1"),
    "dou-chamadas": ("diario_oficial", "P1"),
    "eu-horizon": ("internacional", "P3"),
}

configs = {c.id: c for c in FONTES}
caminho = RAIZ / "config" / "sources.json"
dados = json.loads(caminho.read_text(encoding="utf-8"))
por_id = {s["id"]: s for s in dados["sources"]}
for chave, classe in ADAPTERS.items():
    if chave in por_id:
        por_id[chave].update({"name": classe.name, "url": classe.url, "adapter": chave})
        continue
    tipo, prioridade = (configs[chave].tipo, configs[chave].prioridade) if chave in configs else TIPOS_MANUAIS.get(chave, ("outros", "P2"))
    fonte = {"id": chave, "name": classe.name, "type": tipo, "adapter": chave, "frequency": "daily", "url": classe.url, "priority": prioridade}
    dados["sources"].append(fonte)
    por_id[chave] = fonte
# Fonte que saiu de ADAPTERS sai também da configuração (senão o agregador a
# daria como "snapshot ausente" todo dia).
removidas = [s["id"] for s in dados["sources"] if s["adapter"] not in ADAPTERS]
dados["sources"] = [s for s in dados["sources"] if s["adapter"] in ADAPTERS]
if removidas:
    print("removidas:", ", ".join(removidas))
caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

workflow = RAIZ / ".github" / "workflows" / "radar.yml"
texto = workflow.read_text(encoding="utf-8")
matriz = [c for c in ADAPTERS if c != "transferegov"]
texto = re.sub(r"source: \[[^\]]*\]", "source: [" + ", ".join(matriz) + "]", texto, count=1)
workflow.write_text(texto, encoding="utf-8")
print(f"{len(dados['sources'])} fontes em sources.json; {len(matriz)} na matriz do workflow")
