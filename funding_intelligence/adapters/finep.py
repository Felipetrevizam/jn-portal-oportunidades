from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Any
from urllib.parse import urljoin, urlsplit

from funding_intelligence.adapters.base import USER_AGENT, BaseAdapter
from funding_intelligence.models import clean_text, opportunity, parse_br_date, slug


# A API de objetos do Liferay responde sem login para listar e detalhar chamadas
# (reconhecimento de 21/11/2026). Só a lista de documentos de cada chamada
# (`/o/c/chamadapublicas/{id}/documentos`) exige token, e o token que o site usa
# sai de uma credencial embutida no JavaScript público. Essa credencial foi
# emitida para o site da Finep, não para este coletor, então não é usada aqui:
# os documentos são lidos da página pública da chamada, renderizada num
# navegador, como qualquer visitante a vê.
PAUSA_PAGINA_S = 3.0
DATA_ROTULO = re.compile(r"^\s*(\d{1,2}/\d{1,2}/\d{4})\s*")


class FinepAdapter(BaseAdapter):
    id = "finep"
    name = "Finep"
    url = "https://www.finep.gov.br/oportunidades"
    api_url = (
        "https://www.finep.gov.br/o/c/chamadapublicas"
        "?sort=dataDePublicacao:desc&filter=situacao%20eq%20%27aberta%27"
    )
    detail_url = "https://www.finep.gov.br/e/chamada-publica/222684/{id}"

    def collect(self) -> list[dict[str, Any]]:
        if not self.fixture:
            return self._collect_api()
        return self._collect_legacy_html()

    def _collect_api(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            payload = json.loads(self.request_bytes(f"{self.api_url}&page={page}&pageSize=100"))
            batch = payload.get("items", [])
            items.extend(batch)
            if not batch or len(items) >= payload.get("totalCount", 0):
                break
            page += 1
        found = self.parse_api_items(items)
        if os.environ.get("RADAR_FINEP_DOCUMENTOS", "1") != "0":
            self._attach_page_documents(found)
        return found

    def _attach_page_documents(self, found: list[dict[str, Any]]) -> None:
        """Lê os links de /documents/ da página pública de cada chamada aberta.

        Sem Playwright instalado, segue só com os links da descrição: a chamada
        continua no catálogo, e a revisão humana anexa o edital que faltar.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("finep: Playwright ausente; documentos só da descrição", file=sys.stderr)
            return
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(user_agent=USER_AGENT)
            for index, item in enumerate(found):
                if index:
                    time.sleep(PAUSA_PAGINA_S)
                try:
                    # O site fica carregando analytics sem parar, então `networkidle` nunca
                    # chega: espera o primeiro link de arquivo da chamada aparecer.
                    page.goto(item["source"]["url"], wait_until="domcontentloaded", timeout=60_000)
                    page.wait_for_selector("a[href*='/documents/20']", timeout=30_000)
                    anchors = page.eval_on_selector_all(
                        "a[href*='/documents/']",
                        "els => els.map(a => [(a.closest('tr, li, .row, div') || a).innerText || '', a.href])",
                    )
                except Exception as error:  # página fora do ar não derruba a fonte
                    print(f"finep: documentos de {item['source']['url']} falharam: {error}", file=sys.stderr)
                    continue
                known = {doc["url"] for doc in item["documents"]}
                item["documents"].extend(
                    doc for doc in self.documents_from_anchors(anchors) if doc["url"] not in known
                )
            browser.close()

    @staticmethod
    def documents_from_anchors(anchors: list[list[str]]) -> list[dict[str, Any]]:
        """Converte os links da página em documentos.

        Cada arquivo aparece em PDF e em ODT; só o PDF entra. O rótulo da linha
        traz a data e o tipo ("22/09/2026 Edital", "30/10/2026 FAQ").
        """
        documents: list[dict[str, Any]] = []
        seen: set[str] = set()
        for label, href in anchors:
            path = urlsplit(href).path
            if not re.search(r"\.pdf(?:/|$)", path, re.I) or path in seen:
                continue
            seen.add(path)
            text = clean_text(label) or ""
            date_match = DATA_ROTULO.match(text)
            title = clean_text(text[date_match.end():] if date_match else text) or "Documento da chamada"
            documents.append({
                "title": title,
                "url": href,
                "published": parse_br_date(date_match.group(1)) if date_match else None,
            })
        return documents

    def parse_api_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        found = []
        for item in items:
            deadline = self._iso_date(item.get("prazoProposto"))
            source_status = (item.get("situacao") or {}).get("key", "").lower()
            if source_status != "aberta" or not deadline or deadline < self.today.isoformat():
                continue
            source_url = self.detail_url.format(id=item["id"])
            description_html = item.get("descricao") or ""
            description_soup = self.soup(description_html)
            documents = []
            seen_urls = set()
            for link in description_soup.select("a[href]"):
                href = urljoin(source_url, link.get("href"))
                if href in seen_urls or href.lower().startswith("mailto:"):
                    continue
                seen_urls.add(href)
                documents.append({
                    "title": clean_text(link.get_text(" ", strip=True)) or "Documento da chamada",
                    "url": href,
                    "published": None,
                })
            audience_text = " ".join(
                entry.get("name", "") for entry in item.get("publicoAlvo") or []
            ) + " " + (item.get("descricaoRawText") or "")
            themes = [entry.get("taxonomyCategoryName") for entry in item.get("taxonomyCategoryBriefs") or []]
            themes.extend(re.split(r";|,", item.get("tema") or ""))
            themes.append(item.get("titulo") or "")
            instrument_type, repayable = self._instrument(item, description_soup.get_text(" ", strip=True))
            found.append(opportunity(
                source_id=self.id, source_name=self.name, source_url=source_url,
                checked_at=self.checked_at, external_id=str(item["id"]),
                title=item.get("titulo") or f"Chamada Finep {item['id']}",
                funder="Finep / FNDCT", status="open",
                published=self._iso_date(item.get("dataDePublicacao")), deadline=deadline,
                organization_types=self._audience(audience_text),
                geography=self._geography((item.get("regiao") or {}).get("name")),
                themes=[theme for theme in themes if clean_text(theme)],
                instrument_type=instrument_type, repayable=repayable,
                program_budget=self._budget(item.get("descricaoRawText") or ""),
                documents=documents, description=item.get("descricaoRawText"),
            ))
        return found

    def _collect_legacy_html(self) -> list[dict[str, Any]]:
        soup = self.soup(self.fetch_html())
        found: list[dict[str, Any]] = []
        seen: set[str] = set()
        for heading in soup.select("h2, h3, h4"):
            link = heading.find("a", href=re.compile(r"chamadapublica/\d+"))
            if not link:
                continue
            title = clean_text(link.get_text(" ", strip=True))
            detail_url = urljoin(self.url, link.get("href"))
            external_match = re.search(r"chamadapublica/(\d+)", detail_url)
            if not title or not external_match or external_match.group(1) in seen:
                continue
            seen.add(external_match.group(1))
            block_parts: list[str] = []
            for sibling in heading.next_siblings:
                sibling_name = getattr(sibling, "name", None)
                if sibling_name in {"h2", "h3", "h4"}:
                    break
                text = clean_text(sibling.get_text(" ", strip=True) if hasattr(sibling, "get_text") else str(sibling))
                if text:
                    block_parts.append(text)
            block = " ".join(block_parts)
            published = self._label_date(block, "Data de publicação")
            deadline = self._label_date(block, "Prazo para envio de propostas até")
            audience = self._label(block, r"P[uú]blico-alvo")
            themes = self._split(self._label(block, r"Tema(?:\(s\))?"))
            funder = self._label(block, "Fonte de Recurso") or "Finep / FNDCT"
            status = "open" if deadline and deadline >= self.today.isoformat() else "unknown"
            found.append(opportunity(
                source_id=self.id, source_name=self.name, source_url=detail_url,
                checked_at=self.checked_at, external_id=external_match.group(1),
                title=title, funder=funder, status=status, published=published,
                deadline=deadline, organization_types=self._audience(audience),
                geography=["BR"], themes=themes, instrument_type="subvencao_economica",
                repayable=False,
            ))
        return found

    @staticmethod
    def _iso_date(value: str | None) -> str | None:
        return value[:10] if value and re.match(r"\d{4}-\d{2}-\d{2}", value) else None

    @staticmethod
    def _geography(value: str | None) -> list[str]:
        folded = slug(value)
        if "paraiba" in folded:
            return ["PB", "BR"]
        if "nordeste" in folded:
            return ["NE", "BR"]
        return ["BR"]

    @staticmethod
    def _instrument(item: dict[str, Any], description: str) -> tuple[str, bool | None]:
        key = slug((item.get("tipoDeOportunidade") or {}).get("key"))
        text = slug(description)
        if "subvencao" in text:
            return "subvencao_economica", False
        if "credito" in key or "reembolsavel" in key and "naoreembolsavel" not in key:
            return "credito", True
        if "invest" in key:
            return "investimento", None
        if "premi" in key:
            return "premio", False
        if "naoreembolsavel" in key:
            return "contratacao_pdi", False
        return "outros", None

    @staticmethod
    def _budget(text: str) -> float | None:
        match = re.search(r"(?:or[cç]amento|recursos?)[^R$]{0,80}R\$\s*([\d.,]+)\s*(milh(?:[aã]o|[oõ]es)|bilh(?:[aã]o|[oõ]es)|mil)?", text, re.I)
        if not match:
            return None
        number = float(match.group(1).replace(".", "").replace(",", "."))
        unit = slug(match.group(2))
        if unit.startswith("bilh"):
            number *= 1_000_000_000
        elif unit.startswith("milh"):
            number *= 1_000_000
        elif unit == "mil":
            number *= 1_000
        return number

    @staticmethod
    def _label(block: str, label: str) -> str | None:
        labels = r"Data de publica[cç][aã]o|Prazo para envio de propostas at[eé]|Fonte de Recurso|P[uú]blico-alvo|Tema(?:\(s\))?|Situa[cç][aã]o"
        match = re.search(rf"{label}\s*:?\s*(.+?)(?=\s+(?:{labels})\s*:|$)", block, re.I)
        return clean_text(match.group(1)) if match else None

    def _label_date(self, block: str, label: str) -> str | None:
        return parse_br_date(self._label(block, label))

    @staticmethod
    def _split(value: str | None) -> list[str]:
        return [slug(x).replace("-", "_") for x in re.split(r";|,", value or "") if clean_text(x)]

    @staticmethod
    def _audience(value: str | None) -> list[str]:
        folded = slug(value)
        result = []
        for needle, canonical in (
            ("startup", "startup"), ("empresa", "empresa"), ("cooperativ", "cooperativa"),
            ("ict", "ict"), ("universidade", "universidade"), ("instituicoes-de-pesquisa", "ict"),
        ):
            if needle in folded and canonical not in result:
                result.append(canonical)
        return result or ["outros"]
