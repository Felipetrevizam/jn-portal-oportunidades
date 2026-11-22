"""Converte em Markdown o edital (PDF) de cada chamada do catálogo (Fomenta360).

Uso:
    python scripts/editais_markdown.py \
        --catalogo public/data/funding-opportunities-v2.json \
        --saida public/data/editais --max 30

Para cada chamada aberta (ou de situação desconhecida) com um PDF de edital:
- baixa o PDF para a memória, calcula o SHA-256 e, se o hash é novo, converte
  com o Docling (texto + tabelas + OCR nas páginas que são imagem);
- grava `<saida>/<id>.md` (com cabeçalho YAML) e atualiza `<saida>/indice.json`;
- tira do Markdown o prazo de submissão, quando o catálogo não tem prazo;
- descarta o PDF. Nenhum PDF é gravado em disco nem publicado.

Markdown de chamada que saiu do catálogo é apagado. Cada execução converte no
máximo `--max` editais (os de prazo mais próximo primeiro); o resto fica para a
próxima.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from funding_intelligence.adapters.base import BaseAdapter
from funding_intelligence.adapters.generico import extrair_prazo

EDITAL = re.compile(r"\b(edital|chamada|regulamento|carta[\s-]convite)\b", re.I)
NAO_EDITAL = re.compile(r"faq|manual|tutorial|resultado|plataforma|anexo|aviso|cadastro|formul[aá]rio|errata", re.I)
PDF = re.compile(r"\.pdf(?:$|[?#/])", re.I)
LIMITE_BYTES = 40 * 1024 * 1024


class Baixador(BaseAdapter):
    """Só para reaproveitar o cliente HTTP do coletor (User-Agent, retentativa)."""

    id = name = url = "editais-markdown"

    def collect(self):  # pragma: no cover - não é uma fonte
        return []


def pdf_do_edital(op: dict) -> dict | None:
    """O documento que é o edital vigente: PDF com cara de edital, o mais recente."""
    candidatos = [
        (i, d) for i, d in enumerate(op.get("documents") or [])
        if PDF.search(d.get("url") or "") and EDITAL.search(d.get("title") or "") and not NAO_EDITAL.search(d.get("title") or "")
    ]
    if not candidatos:
        # Sem rótulo claro: o primeiro PDF que não é manual/resultado.
        candidatos = [
            (i, d) for i, d in enumerate(op.get("documents") or [])
            if PDF.search(d.get("url") or "") and not NAO_EDITAL.search(d.get("title") or "")
        ][:1]
    if not candidatos:
        return None
    candidatos.sort(key=lambda par: (par[1].get("published") or "", -par[0]), reverse=True)
    return candidatos[0][1]


def nome_arquivo(op_id: str) -> str:
    seguro = re.sub(r"[^a-z0-9-]+", "-", op_id.lower()).strip("-")
    return (seguro[:120] or hashlib.sha1(op_id.encode()).hexdigest()) + ".md"


def cabecalho(op: dict, doc: dict, conv, agora: str) -> str:
    campos = {
        "id": op["id"],
        "titulo": op.get("title"),
        "fonte": op["source"]["id"],
        "pagina_oficial": op["source"]["url"],
        "pdf_oficial": doc["url"],
        "pdf_sha256": conv.sha256,
        "paginas": conv.paginas,
        "paginas_com_ocr": conv.paginas_imagem,
        "convertido_em": agora,
        "conversor": "docling",
    }
    linhas = ["---"] + [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in campos.items()] + ["---", ""]
    return "\n".join(linhas)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalogo", default="public/data/funding-opportunities-v2.json")
    ap.add_argument("--saida", default="public/data/editais")
    ap.add_argument("--max", type=int, default=30)
    args = ap.parse_args()

    from funding_intelligence.markdown_editais import converter_pdf  # Docling só aqui

    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    caminho_indice = saida / "indice.json"
    indice = json.loads(caminho_indice.read_text(encoding="utf-8")) if caminho_indice.exists() else {}

    catalogo = json.loads(Path(args.catalogo).read_text(encoding="utf-8"))
    hoje = datetime.now(timezone.utc).date().isoformat()
    ops = [o for o in catalogo["opportunities"] if o.get("status") in ("open", "unknown")]
    # Prazo mais próximo primeiro; sem prazo por último.
    ops.sort(key=lambda o: ((o.get("dates") or {}).get("deadline") or "9999", o["id"]))

    baixador = Baixador()
    convertidos = falhas = mantidos = 0
    for op in ops:
        doc = pdf_do_edital(op)
        if not doc:
            continue
        atual = indice.get(op["id"])
        if atual and atual.get("pdf_oficial") == doc["url"] and (saida / atual["arquivo"]).exists():
            mantidos += 1
            continue  # mesmo link já convertido; o hash é conferido quando o link muda
        if convertidos >= args.max:
            continue
        try:
            pdf = baixador.request_bytes(doc["url"])
            if len(pdf) > LIMITE_BYTES or not pdf.startswith(b"%PDF"):
                raise ValueError(f"não é PDF ou passa de 40 MB ({len(pdf)} bytes)")
            sha = hashlib.sha256(pdf).hexdigest()
            if atual and atual.get("pdf_sha256") == sha and (saida / atual["arquivo"]).exists():
                atual["pdf_oficial"] = doc["url"]
                mantidos += 1
                continue
            inicio = time.monotonic()
            conv = converter_pdf(pdf, nome=doc["url"].rsplit("/", 1)[-1][:80] or "edital.pdf")
            del pdf  # o PDF não sai da memória
            agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
            arquivo = nome_arquivo(op["id"])
            (saida / arquivo).write_text(cabecalho(op, doc, conv, agora) + conv.markdown, encoding="utf-8")
            prazo = extrair_prazo(conv.markdown)
            indice[op["id"]] = {
                "arquivo": arquivo,
                "pdf_oficial": doc["url"],
                "pdf_sha256": conv.sha256,
                "paginas": conv.paginas,
                "paginas_com_ocr": conv.paginas_imagem,
                "prazo_no_edital": prazo if prazo and prazo >= "2000-01-01" else None,
                "convertido_em": agora,
                "segundos": round(time.monotonic() - inicio, 1),
            }
            convertidos += 1
            # Grava o índice a cada edital: execução interrompida (timeout do job)
            # não perde o registro do que já foi convertido.
            caminho_indice.write_text(json.dumps(indice, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            print(f"convertido {op['id']}: {conv.paginas} pág ({conv.paginas_imagem} com OCR), prazo={prazo}")
        except Exception as erro:
            falhas += 1
            print(f"::warning::edital de {op['id']} não convertido: {type(erro).__name__}: {erro}", file=sys.stderr)

    # Chamada que saiu do catálogo leva junto o seu Markdown.
    no_catalogo = {o["id"] for o in catalogo["opportunities"]}
    for op_id in [k for k in indice if k not in no_catalogo]:
        (saida / indice[op_id]["arquivo"]).unlink(missing_ok=True)
        del indice[op_id]

    caminho_indice.write_text(json.dumps(indice, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"editais em markdown: {convertidos} convertidos, {mantidos} já em dia, {falhas} falhas, {len(indice)} no índice (hoje {hoje})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
