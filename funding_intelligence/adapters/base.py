from __future__ import annotations

import io
import json
import os
import socket
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from pypdf import PdfReader

from funding_intelligence.models import utc_now


USER_AGENT = "Fomenta360-Coletor/1.0 (+https://github.com/Felipetrevizam/jn-portal-oportunidades)"


# Os portais do governo derrubam conexões vindas dos runners do GitHub de vez em
# quando (reset, recusa, timeout): em novembro de 2026, CNPq e BNDES falharam
# assim em dias isolados e funcionaram no dia seguinte. Erro passageiro ganha
# mais duas chances; 4xx não, porque 404 é resposta, não falha de rede.
ESPERAS_RETENTATIVA_S: tuple[float, ...] = (5.0, 20.0)


def erro_passageiro(erro: BaseException) -> bool:
    if isinstance(erro, urllib.error.HTTPError):
        return erro.code == 429 or erro.code >= 500
    return isinstance(erro, (urllib.error.URLError, ConnectionError, TimeoutError, socket.timeout))


class BaseAdapter(ABC):
    id: str
    name: str
    url: str

    def __init__(self, *, fixture: str | None = None, today: date | None = None):
        self.fixture = fixture
        self.today = today or date.today()
        self.checked_at = utc_now()
        # Carga histórica (disparo manual com `carga_historica`): a fonte lê os
        # últimos 24 meses de encerradas uma vez. No dia a dia, lê só o que está
        # na vitrine, e o pipeline guarda o que encerra.
        self.historical = os.environ.get("RADAR_CARGA_HISTORICA") == "1"

    def request_bytes(
        self, url: str, *, method: str = "GET", headers: dict[str, str] | None = None,
        data: bytes | None = None,
    ) -> bytes:
        # Accept e Accept-Language são os cabeçalhos que qualquer cliente HTTP envia;
        # sem eles, alguns firewalls (in.gov.br) recusam o pedido com 403.
        request_headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9",
            **(headers or {}),
        }
        for tentativa in range(len(ESPERAS_RETENTATIVA_S) + 1):
            request = urllib.request.Request(url, headers=request_headers, data=data, method=method)
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    return response.read()
            except Exception as erro:
                if tentativa == len(ESPERAS_RETENTATIVA_S) or not erro_passageiro(erro):
                    raise
                time.sleep(ESPERAS_RETENTATIVA_S[tentativa])
        raise AssertionError("inalcançável")

    def fetch_bytes(self, url: str) -> bytes:
        return self.request_bytes(url)

    def fetch_html(self, url: str | None = None) -> str:
        if self.fixture:
            return Path(self.fixture).read_text(encoding="utf-8")
        return self.fetch_bytes(url or self.url).decode("utf-8", errors="replace")

    def soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")

    def pdf_text(self, url: str) -> str:
        reader = PdfReader(io.BytesIO(self.fetch_bytes(urljoin(self.url, url))))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    @abstractmethod
    def collect(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def snapshot(self) -> dict[str, Any]:
        opportunities = self.collect()
        return {
            "source": {"id": self.id, "name": self.name, "url": self.url},
            "checked_at": self.checked_at,
            "status": "healthy",
            "error": None,
            "opportunities": opportunities,
        }


def load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))
