"""Adaptador genérico configurável (Fomenta360).

A maior parte dos sites de fomento publica as chamadas numa página só, em
formatos parecidos: uma lista (ou uma sequência de parágrafos) em que cada
chamada começa com um título ou um link e traz, perto dele, o período de
inscrição e os PDFs. Em vez de um adaptador por site, cada site vira uma
`Config` e este motor faz o resto:

1. baixa a página de listagem (HTML, WordPress REST ou RSS);
2. "achata" o conteúdo principal em blocos (parágrafo, item de lista, linha de
   tabela, título) e abre uma chamada nova a cada bloco que casa com o padrão
   de início configurado;
3. tira de cada chamada o prazo, o número, os documentos e os tipos de
   proponente;
4. sem prazo no trecho, abre a página de detalhe e, se preciso, o PDF do
   edital (com orçamento de pedidos por execução).

Prazo vencido vira `closed`; sem prazo, a situação depende de a página listar
só chamadas abertas (`lista_abertas`). Nada é inventado: o que não está no
texto fica nulo.
"""

from __future__ import annotations

import io
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable
from urllib.parse import quote, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag
from pypdf import PdfReader

from funding_intelligence.adapters.base import BaseAdapter
from funding_intelligence.models import THEME_ALIASES, ascii_fold, clean_text, opportunity

# ------------------------------------------------------------------ datas

MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}
DATA_NUM = r"\d{1,2}/\d{1,2}/\d{2,4}"
DATA_EXT = r"\d{1,2}º?\s+de\s+(?:" + "|".join(MESES) + r")\s+de\s+\d{4}"
DATA = rf"(?:{DATA_NUM}|{DATA_EXT})"
# Palavras que anunciam o prazo de submissão. "Resultado", "divulgação" e
# "vigência" ficam de fora de propósito: são datas depois do prazo.
GATILHO = (
    r"(?:inscri[çc][õo]es|inscri[çc][ãa]o|submiss[ãa]o|submeter|prazo|envio\s+d[ae]s?\s+propostas?|"
    r"recebimento\s+d[ae]s?\s+propostas?|encerramento|data\s+limite|propostas?\s+(?:at[ée]|de)|"
    r"deadline|candidaturas?)"
)
INTERVALO = re.compile(rf"{GATILHO}[^\n]{{0,90}}?({DATA})\s*(?:a|at[ée]|-|–|e)\s*({DATA})", re.I)
ATE = re.compile(rf"{GATILHO}[^\n]{{0,90}}?(?:at[ée]|limite|:)\s*(?:o\s+dia\s+)?({DATA})", re.I)
PROXIMA = re.compile(rf"{GATILHO}[^\n]{{0,60}}?({DATA})", re.I)


def para_iso(valor: str) -> str | None:
    texto = valor.lower().replace("º", "")
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})$", texto.strip())
    if m:
        dia, mes, ano = map(int, m.groups())
    else:
        m = re.match(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", texto.strip())
        if not m or m.group(2) not in MESES:
            return None
        dia, mes, ano = int(m.group(1)), MESES[m.group(2)], int(m.group(3))
    if ano < 100:
        ano += 2000
    try:
        return date(ano, mes, dia).isoformat()
    except ValueError:
        return None


def extrair_prazo(texto: str) -> str | None:
    """Último dia de submissão anunciado no texto, ou None.

    Junta todas as datas ditas como prazo (fim de intervalo, "até", data logo
    depois do gatilho) e fica com a maior: em cronograma com várias etapas de
    submissão, vale a última; e o fim de "de 01/10 a 30/11" é 30/11.
    """
    plano = re.sub(r"\s+", " ", texto)
    datas: list[str] = []
    for m in INTERVALO.finditer(plano):
        datas.append(m.group(2))
    for m in ATE.finditer(plano):
        datas.append(m.group(1))
    if not datas:
        datas = [m.group(1) for m in PROXIMA.finditer(plano)]
    isos = [d for d in (para_iso(x) for x in datas) if d]
    return max(isos) if isos else None


def extrair_publicacao(texto: str) -> str | None:
    m = re.search(rf"(?:publicad[oa]\s+em|lan[çc]amento|data\s+de\s+publica[çc][ãa]o)[^\d]{{0,30}}({DATA})", texto, re.I)
    return para_iso(m.group(1)) if m else None


# ------------------------------------------------------------------ classificação

NUMERO = re.compile(r"\bn(?:[º°o.]|ú?mero)?\s*\.?\s*0*(\d{1,4})\s*[/_-]\s*(20\d{2})\b", re.I)
NUMERO_SOLTO = re.compile(r"\b(?:edital|chamada|chamamento|cp)\s+(?:p[úu]blica\s+)?0*(\d{1,4})\s*[/-]\s*(20\d{2})\b", re.I)


def extrair_numero(texto: str) -> str | None:
    m = NUMERO.search(texto) or NUMERO_SOLTO.search(texto)
    return f"{int(m.group(1))}-{m.group(2)}" if m else None


TIPOS_ORG = (
    (r"\bstartups?\b", "startup"),
    (r"\bempresas?\b|\bmpes?\b|microempresa|pequenas? empresas?|\bind[úu]strias?\b", "empresa"),
    (r"\bicts?\b|institui[çc][õo]es? cient[íi]fica", "ict"),
    (r"universidade|institui[çc][õo]es? de ensino superior|\bies\b", "universidade"),
    (r"pesquisador|doutor|mestr|bolsista|professor|estudante|p[óo]s-?gradua", "pesquisador"),
    (r"organiza[çc][õo]es? da sociedade civil|\boscs?\b|associa[çc][õo]es? sem fins", "osc"),
    (r"cooperativa", "cooperativa"),
    (r"munic[íi]pios?|prefeituras?", "municipio"),
    (r"empreendedor|pessoas? f[íi]sicas?", "pessoa_fisica"),
)


def tipos_de_proponente(texto: str) -> list[str]:
    achados = [canon for rx, canon in TIPOS_ORG if re.search(rx, texto, re.I)]
    return list(dict.fromkeys(achados))


INSTRUMENTOS = (
    (r"subven[çc][ãa]o", "subvencao_economica"),
    (r"\bbolsas?\b", "bolsa"),
    (r"financiamento reembols|cr[ée]dito|linha de financiamento", "credito"),
    (r"pr[êe]mio", "premio"),
    (r"credenciamento", "credenciamento"),
    (r"aux[íi]lio|apoio a projetos|projetos de pesquisa|pesquisa", "auxilio_pesquisa"),
)


def instrumento(texto: str, padrao: str) -> str:
    for rx, canon in INSTRUMENTOS:
        if re.search(rx, texto, re.I):
            return canon
    return padrao


def temas(texto: str) -> list[str]:
    dobrado = ascii_fold(texto)
    return [canon for rx, canon in THEME_ALIASES if re.search(rx, dobrado)]


# ------------------------------------------------------------------ HTML

BLOCOS = {"p", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "dt", "dd", "blockquote", "figcaption"}
LIXO = ["script", "style", "nav", "header", "footer", "noscript", "iframe", "svg"]


def escolher(sopa: BeautifulSoup, seletores: str) -> Tag:
    """Primeiro seletor da lista que existe na página, na ordem de preferência.

    `select_one("a, b")` devolve o primeiro elemento na ordem do documento, que
    costuma ser o <body>; aqui vale a ordem em que os seletores foram escritos.
    """
    for seletor in seletores.split(","):
        achado = sopa.select_one(seletor.strip())
        if achado is not None:
            return achado
    return sopa.body or sopa
EXT_DOC = re.compile(r"\.(pdf|docx?|odt|xlsx?|ods|zip)(?:$|[?#/])", re.I)


@dataclass
class Bloco:
    texto: str
    links: list[tuple[str, str]]  # (texto, url absoluta)
    tag: str


CONTENTORES = BLOCOS | {"div", "section", "article", "ul", "ol", "table", "tbody", "thead", "tfoot", "dl", "main", "aside", "body", "center"}


def achatar(raiz: Tag, base: str) -> list[Bloco]:
    """Sequência de blocos de texto na ordem do documento.

    Elemento de bloco sem outro elemento de bloco dentro vira um Bloco. Texto e
    elementos inline soltos ao lado de blocos (o <span> com o prazo depois do
    <h3> com o título) viram um Bloco próprio, na posição em que aparecem.
    Assim a mesma rotina serve para lista, tabela, acordeão e página corrida.
    """
    saida: list[Bloco] = []

    def links_de(nos: list[Any]) -> list[tuple[str, str]]:
        resultado = []
        for no in nos:
            if not isinstance(no, Tag):
                continue
            ancoras = [no] if no.name == "a" else no.find_all("a")
            for a in ancoras:
                href = a.get("href")
                if href and not href.startswith(("mailto:", "javascript:", "#")):
                    resultado.append((clean_text(a.get_text(" ", strip=True)), urljoin(base, href)))
        return resultado

    def emitir(nos: list[Any], tag: str, herdado: list[tuple[str, str]]) -> None:
        texto = clean_text(" ".join(
            (n.get_text(" ", strip=True) if isinstance(n, Tag) else str(n)) for n in nos
        ))
        links = links_de(nos) + [(texto or t, h) for t, h in herdado]
        if texto or links:
            saida.append(Bloco(texto, links, tag))

    def tem_bloco(no: Tag) -> bool:
        return any(d.name in CONTENTORES for d in no.find_all(True))

    def visitar(no: Tag, herdado: list[tuple[str, str]]) -> None:
        if not tem_bloco(no):
            emitir([no], no.name, herdado)
            return
        # Card inteiro dentro de um link (<a><h5>Título</h5></a>): os blocos de
        # dentro herdam o link, senão o título fica sem destino.
        if no.name == "a" and no.get("href") and not no["href"].startswith(("mailto:", "javascript:", "#")):
            herdado = herdado + [("", urljoin(base, no["href"]))]
        inline: list[Any] = []
        for filho in no.children:
            if isinstance(filho, Tag) and (filho.name in CONTENTORES or tem_bloco(filho)):
                if inline:
                    emitir(inline, "span", herdado)
                    inline = []
                visitar(filho, herdado)
            else:
                inline.append(filho)
        if inline:
            emitir(inline, "span", herdado)

    visitar(raiz, [])
    return saida


@dataclass
class Trecho:
    titulo: str
    url: str | None
    blocos: list[Bloco] = field(default_factory=list)

    @property
    def texto(self) -> str:
        return " \n".join(b.texto for b in self.blocos)

    @property
    def links(self) -> list[tuple[str, str]]:
        return [link for b in self.blocos for link in b.links]


# Texto de botão, que não serve de título ("Ver detalhes", "Saiba mais").
CTA = re.compile(r"^\W*(ver detalhes|saiba mais|leia mais|acesse( aqui)?|clique aqui|mais informa[çc][õo]es|veja mais|confira)\W*$", re.I)
RABO_TITULO = re.compile(
    r"\s+(?:publica[çc][ãa]o|publicad[oa]|lan[çc]amento|data-?limite|inscri[çc][õo]es|submiss[ãa]o|"
    r"prazo|[áa]rea:|resultado|leia mais|saiba mais)\b.*$",
    re.I,
)


def limpar_titulo(texto: str) -> str:
    texto = re.sub(r"^(link|download|baixar|pdf)\s+", "", clean_text(texto), flags=re.I)
    texto = re.sub(r"^(ver detalhes|saiba mais|leia mais|acesse)\s+", "", texto, flags=re.I)
    titulo = RABO_TITULO.sub("", texto) or texto
    if len(titulo) > 220:
        titulo = titulo[:220].rsplit(" ", 1)[0] + "…"
    return titulo


# ------------------------------------------------------------------ configuração


@dataclass
class Config:
    id: str
    nome: str
    url: str
    financiador: str
    # Tipo da fonte em config/sources.json.
    tipo: str = "fundacao_estadual"
    prioridade: str = "P2"
    # De onde vem a lista: "html" (página), "wp" (WordPress REST) ou "rss".
    modo: str = "html"
    # Páginas extras da mesma listagem (paginação, abas por ano).
    urls_extras: tuple[str, ...] = ()
    # Seletor CSS do conteúdo principal da página.
    conteudo: str = "#content-core, main, #content, article, .entry-content, body"
    # Abre uma chamada nova quando o TEXTO do bloco casa com isto...
    inicio_titulo: str | None = None
    # ...ou quando um LINK do bloco casa com isto (o texto do link vira o título).
    inicio_link: str | None = None
    # Título que casa com isto é descartado (resultado, errata solta, menu).
    descartar: str | None = (
        r"^(resultados?|errata|retifica|veja|confira|clique|saiba|leia|acesse|portaria|resolu[çc][ãa]o|"
        r"homologa|convoca[çc][ãa]o|aviso de|extrato|ata\b|termo de|nota\b|lista de|rela[çc][ãa]o de)|resultado (final|preliminar|parcial)"
        # Notícia institucional ("Fapepi acompanha...", "Fapespa divulga resultado...").
        r"|^\S+ (acompanha|participa|visita|realiza|recebe|divulga resultado|homenageia|promove)\b"
    )
    # Ano mínimo no título/texto; trechos de anos anteriores são ignorados.
    ano_minimo: int | None = None
    # Página lista só chamadas abertas? Então sem prazo vira "open".
    lista_abertas: bool = False
    # Abrir a página de detalhe quando o trecho não tiver prazo.
    detalhe: bool = True
    detalhe_conteudo: str | None = None
    ler_pdf: bool = True
    max_detalhes: int = 12
    max_pdfs: int = 4
    # Metadados padrão da fonte.
    geografia: tuple[str, ...] = ("BR",)
    proponentes: tuple[str, ...] = ()
    instrumento_padrao: str = "auxilio_pesquisa"
    canal: str = "chamada_publica"
    tema_padrao: tuple[str, ...] = ()
    pausa_s: float = 1.0
    # Para modo "wp": endpoint e filtro de título.
    wp_endpoint: str = "wp-json/wp/v2/posts"
    # Slug(s) de categoria do WordPress; o id é resolvido na hora.
    wp_categorias: tuple[str, ...] = ()
    wp_params: str = "per_page=25&_fields=id,link,title,date,content"
    filtro_titulo: str | None = None
    # Elementos descartados antes de ler a página (menu e rodapé, por padrão).
    lixo: tuple[str, ...] = tuple(LIXO)
    # Itens por seletor CSS (cards): cada elemento vira uma chamada.
    item_seletor: str | None = None
    titulo_seletor: str = "h1, h2, h3, h4, h5, .card-title, .titulo, strong, a"
    # Links da página principal que levam a outras páginas de listagem.
    seguir_listagens: str | None = None
    max_listagens: int = 30
    # Modo "json": caminho da lista (chaves separadas por ponto) e campos.
    json_lista: str = ""
    json_titulo: str = "title"
    json_link: str = "link"
    json_texto: tuple[str, ...] = ()
    # Hook para casos especiais sem criar outro adaptador.
    ajustar: Callable[["Trecho"], "Trecho | None"] | None = None


class AdaptadorGenerico(BaseAdapter):
    config: Config

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.id = self.config.id
        self.name = self.config.nome
        self.url = self.config.url
        self.pedidos_detalhe = 0
        self.pedidos_pdf = 0
        self._ultimo_pedido: dict[str, float] = {}
        self.avisos: list[str] = []

    # -------------------------------------------------------------- rede

    def _baixar(self, url: str) -> bytes:
        if self.fixture:
            return open(self.fixture, "rb").read()
        host = urlsplit(url).netloc
        espera = self.config.pausa_s - (time.monotonic() - self._ultimo_pedido.get(host, float("-inf")))
        if espera > 0:
            time.sleep(espera)
        try:
            return self.fetch_bytes(quote(url, safe=":/?&=%#+,;@~!$'()*[]"))
        finally:
            self._ultimo_pedido[host] = time.monotonic()

    def _sopa(self, url: str) -> BeautifulSoup:
        sopa = BeautifulSoup(self._baixar(url).decode("utf-8", errors="replace"), "html.parser")
        for lixo in sopa(list(self.config.lixo)):
            lixo.decompose()
        return sopa

    # -------------------------------------------------------------- coleta

    def collect(self) -> list[dict[str, Any]]:
        cfg = self.config
        if cfg.modo == "wp":
            trechos = self._trechos_wp()
        elif cfg.modo == "rss":
            trechos = self._trechos_rss()
        elif cfg.modo == "json":
            trechos = self._trechos_json()
        else:
            trechos = []
            fila = [cfg.url, *cfg.urls_extras]
            visitadas: set[str] = set()
            while fila:
                url = fila.pop(0)
                if url in visitadas:
                    continue
                visitadas.add(url)
                sopa = self._sopa(url)
                if cfg.seguir_listagens and url == cfg.url and not self.fixture:
                    rx = re.compile(cfg.seguir_listagens, re.I)
                    novas = [urljoin(url, a["href"]).split("#")[0] for a in sopa.find_all("a", href=True) if rx.search(a["href"])]
                    fila.extend(dict.fromkeys(n for n in novas if n not in visitadas))
                    fila = fila[: cfg.max_listagens]
                raiz = escolher(sopa, cfg.conteudo)
                if cfg.item_seletor:
                    trechos.extend(self._itens(raiz, url))
                else:
                    trechos.extend(self._segmentar(achatar(raiz, url)))
                if self.fixture:
                    break
        if not trechos:
            raise ValueError(f"{cfg.nome}: nenhuma chamada reconhecida em {cfg.url}")
        resultado: list[dict[str, Any]] = []
        vistos: set[str] = set()
        for trecho in trechos:
            if cfg.ajustar:
                trecho = cfg.ajustar(trecho)
                if trecho is None:
                    continue
            item = self._oportunidade(trecho)
            if item and item["id"] not in vistos:
                vistos.add(item["id"])
                resultado.append(item)
        return resultado

    def _segmentar(self, blocos: list[Bloco]) -> list[Trecho]:
        cfg = self.config
        rx_titulo = re.compile(cfg.inicio_titulo, re.I) if cfg.inicio_titulo else None
        rx_link = re.compile(cfg.inicio_link, re.I) if cfg.inicio_link else None
        rx_descartar = re.compile(cfg.descartar, re.I) if cfg.descartar else None
        trechos: list[Trecho] = []
        atual: Trecho | None = None
        anterior = ""
        for bloco in blocos:
            inicio: tuple[str, str | None] | None = None
            if rx_link:
                for texto_link, href in bloco.links:
                    if rx_link.search(href) or rx_link.search(texto_link):
                        titulo = bloco.texto if len(texto_link) <= 8 or CTA.match(texto_link) else texto_link
                        if CTA.match(titulo) or len(titulo) <= 8:
                            # Botão sozinho no bloco: o título é o que vem logo antes.
                            titulo = anterior or titulo
                        inicio = (titulo, href)
                        break
            if inicio is None and rx_titulo and rx_titulo.search(bloco.texto):
                href = next((h for t, h in bloco.links if not EXT_DOC.search(h)), None) or next(
                    (h for _, h in bloco.links), None
                )
                inicio = (bloco.texto, href)
            if inicio and not (rx_descartar and rx_descartar.search(inicio[0])):
                if atual and atual.url == inicio[1] and inicio[1] and clean_text(atual.titulo) == clean_text(inicio[0]):
                    atual.blocos.append(bloco)
                    continue
                atual = Trecho(titulo=limpar_titulo(inicio[0]), url=inicio[1])
                trechos.append(atual)
            if atual:
                atual.blocos.append(bloco)
            if bloco.texto and not CTA.match(bloco.texto):
                anterior = bloco.texto
        if cfg.ano_minimo:
            trechos = [t for t in trechos if self._ano_ok(t)]
        return trechos

    def _itens(self, raiz: Tag, url: str) -> list[Trecho]:
        cfg = self.config
        rx_descartar = re.compile(cfg.descartar, re.I) if cfg.descartar else None
        trechos = []
        for el in raiz.select(cfg.item_seletor or ""):
            blocos = achatar(el, url)
            tit_el = el.select_one(cfg.titulo_seletor)
            titulo = clean_text(tit_el.get_text(" ", strip=True)) if tit_el else (blocos[0].texto if blocos else "")
            if not titulo or (rx_descartar and rx_descartar.search(titulo)):
                continue
            link_el = (tit_el if tit_el and tit_el.name == "a" else (tit_el.find("a", href=True) if tit_el else None)) or el.find("a", href=True)
            href = urljoin(url, link_el["href"]) if link_el and link_el.get("href") and not link_el["href"].startswith(("javascript:", "#")) else None
            trechos.append(Trecho(titulo=limpar_titulo(titulo), url=href, blocos=blocos))
        if cfg.ano_minimo:
            trechos = [t for t in trechos if self._ano_ok(t)]
        return trechos

    def _ano_ok(self, trecho: Trecho) -> bool:
        anos = [int(a) for a in re.findall(r"\b(20\d{2})\b", trecho.titulo)]
        if not anos:
            anos = [int(a) for a in re.findall(r"\b(20\d{2})\b", trecho.texto[:600])]
        return not anos or max(anos) >= (self.config.ano_minimo or 0)

    def _trechos_wp(self) -> list[Trecho]:
        cfg = self.config
        partes = urlsplit(cfg.url)
        base = f"{partes.scheme}://{partes.netloc}/"
        url = urljoin(base, cfg.wp_endpoint) + ("&" if "?" in cfg.wp_endpoint else "?") + cfg.wp_params
        if cfg.wp_categorias and not self.fixture:
            ids = []
            for categoria in cfg.wp_categorias:
                achadas = json.loads(self._baixar(urljoin(base, f"wp-json/wp/v2/categories?slug={categoria}&_fields=id")))
                ids.extend(str(c["id"]) for c in achadas)
            if not ids:
                raise ValueError(f"{cfg.nome}: categoria {cfg.wp_categorias} não existe no WordPress")
            url += "&categories=" + ",".join(ids)
        posts = json.loads(self._baixar(url))
        rx = re.compile(cfg.filtro_titulo, re.I) if cfg.filtro_titulo else None
        trechos = []
        for post in posts:
            titulo = clean_text(BeautifulSoup(post.get("title", {}).get("rendered", ""), "html.parser").get_text(" "))
            if rx and not rx.search(titulo):
                continue
            sopa = BeautifulSoup((post.get("content") or {}).get("rendered", ""), "html.parser")
            blocos = achatar(sopa, post.get("link") or base) if sopa.find(True) else []
            trecho = Trecho(titulo=titulo, url=post.get("link"), blocos=blocos)
            data = (post.get("date") or "")[:10]
            if data:
                trecho.blocos.insert(0, Bloco(f"Publicado em {data[8:10]}/{data[5:7]}/{data[:4]}", [], "p"))
            trechos.append(trecho)
        if cfg.ano_minimo:
            trechos = [t for t in trechos if self._ano_ok(t)]
        return trechos

    def _trechos_json(self) -> list[Trecho]:
        cfg = self.config
        dados: Any = json.loads(self._baixar(cfg.url))
        for chave in filter(None, cfg.json_lista.split(".")):
            dados = dados[chave]
        rx = re.compile(cfg.filtro_titulo, re.I) if cfg.filtro_titulo else None
        trechos = []
        for item in dados:
            titulo = clean_text(BeautifulSoup(str(item.get(cfg.json_titulo) or ""), "html.parser").get_text(" "))
            if not titulo or (rx and not rx.search(titulo)):
                continue
            blocos = []
            for campo in cfg.json_texto:
                valor = item.get(campo)
                if valor:
                    rotulo = "Inscrições" if campo in ("vigencia", "prazo", "periodo") else campo
                    sopa = BeautifulSoup(str(valor), "html.parser")
                    blocos.append(Bloco(f"{rotulo}: {clean_text(sopa.get_text(' '))}", [], "p"))
            link = item.get(cfg.json_link)
            trechos.append(Trecho(titulo=limpar_titulo(titulo), url=str(link) if link else None, blocos=blocos))
        if cfg.ano_minimo:
            trechos = [t for t in trechos if self._ano_ok(t)]
        return trechos

    def _trechos_rss(self) -> list[Trecho]:
        cfg = self.config
        raiz = ET.fromstring(self._baixar(cfg.url))
        rx = re.compile(cfg.filtro_titulo, re.I) if cfg.filtro_titulo else None
        trechos = []
        for item in raiz.iter("item"):
            titulo = clean_text(item.findtext("title"))
            if rx and not rx.search(titulo):
                continue
            link = clean_text(item.findtext("link"))
            corpo = item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or item.findtext("description") or ""
            sopa = BeautifulSoup(corpo, "html.parser")
            blocos = achatar(sopa, link or cfg.url) if sopa.find(True) else [Bloco(clean_text(sopa.get_text(" ")), [], "p")]
            trechos.append(Trecho(titulo=titulo, url=link or None, blocos=blocos))
        if cfg.ano_minimo:
            trechos = [t for t in trechos if self._ano_ok(t)]
        return trechos

    # -------------------------------------------------------------- uma chamada

    def _documentos(self, links: list[tuple[str, str]]) -> list[dict[str, Any]]:
        docs, vistos = [], set()
        for texto, url in links:
            if not EXT_DOC.search(url) or url in vistos:
                continue
            vistos.add(url)
            docs.append({"title": texto or urlsplit(url).path.rsplit("/", 1)[-1], "url": url, "published": None})
        return docs

    def _texto_detalhe(self, url: str) -> tuple[str, list[tuple[str, str]]]:
        sopa = self._sopa(url)
        seletor = self.config.detalhe_conteudo or self.config.conteudo
        raiz = escolher(sopa, seletor)
        blocos = achatar(raiz, url)
        return " \n".join(b.texto for b in blocos), [link for b in blocos for link in b.links]

    def _texto_pdf(self, url: str) -> str:
        leitor = PdfReader(io.BytesIO(self._baixar(url)))
        # O prazo costuma estar no cronograma, nas primeiras páginas.
        return "\n".join((p.extract_text() or "") for p in leitor.pages[:8])

    def _oportunidade(self, trecho: Trecho) -> dict[str, Any] | None:
        cfg = self.config
        texto = f"{trecho.titulo}\n{trecho.texto}"
        links = list(trecho.links)
        prazo = extrair_prazo(texto)

        url_detalhe = trecho.url if trecho.url and not EXT_DOC.search(trecho.url) else None
        sem_docs = not self._documentos(links)
        if (
            (prazo is None or sem_docs) and cfg.detalhe and url_detalhe and not self.fixture
            and self.pedidos_detalhe < cfg.max_detalhes
            and urlsplit(url_detalhe).netloc  # link absoluto
        ):
            self.pedidos_detalhe += 1
            try:
                texto_det, links_det = self._texto_detalhe(url_detalhe)
                texto += "\n" + texto_det
                links.extend(links_det)
                prazo = extrair_prazo(texto_det) or prazo
            except Exception as erro:
                self.avisos.append(f"detalhe {url_detalhe}: {erro}")

        docs = self._documentos(links)
        if prazo is None and cfg.ler_pdf and not self.fixture and self.pedidos_pdf < cfg.max_pdfs:
            edital = next((d for d in docs if re.search(r"edital|chamada|regulamento", d["title"] + d["url"], re.I) and re.search(r"\.pdf", d["url"], re.I)), None)
            edital = edital or next((d for d in docs if re.search(r"\.pdf", d["url"], re.I)), None)
            if edital:
                self.pedidos_pdf += 1
                try:
                    prazo = extrair_prazo(self._texto_pdf(edital["url"]))
                except Exception as erro:
                    self.avisos.append(f"pdf {edital['url']}: {erro}")

        hoje = self.today.isoformat()
        if prazo:
            status = "open" if prazo >= hoje else "closed"
        else:
            status = "open" if cfg.lista_abertas else "unknown"

        numero = extrair_numero(trecho.titulo) or extrair_numero(texto[:400])
        tipos = list(cfg.proponentes) or tipos_de_proponente(texto[:3000]) or ["outros"]
        fonte_url = url_detalhe or (docs[0]["url"] if docs else cfg.url)
        return opportunity(
            source_id=cfg.id,
            source_name=cfg.nome,
            source_url=fonte_url,
            checked_at=self.checked_at,
            external_id=numero,
            title=trecho.titulo,
            funder=cfg.financiador,
            status=status,
            published=extrair_publicacao(texto),
            deadline=prazo,
            organization_types=tipos,
            geography=list(cfg.geografia),
            themes=list(cfg.tema_padrao) + temas(texto[:3000]),
            instrument_type=instrumento(texto[:2000], cfg.instrumento_padrao),
            repayable=False,
            documents=docs,
            description=clean_text(trecho.texto)[:1200] or None,
            channel=cfg.canal,
            closed=prazo if status == "closed" else None,
        )

    def snapshot(self) -> dict[str, Any]:
        resultado = super().snapshot()
        resultado["requests"] = {"detalhes": self.pedidos_detalhe, "pdfs": self.pedidos_pdf}
        if self.avisos:
            resultado["warnings"] = self.avisos[:20]
            print(f"{self.config.id}: {len(self.avisos)} aviso(s)", file=sys.stderr)
        return resultado


def criar_adaptador(config: Config) -> type[AdaptadorGenerico]:
    nome = "Adaptador_" + re.sub(r"\W", "_", config.id)
    return type(nome, (AdaptadorGenerico,), {"config": config, "id": config.id, "name": config.nome, "url": config.url})
