"""Fontes coletadas pelo adaptador genérico (Fomenta360).

Cada entrada é o resultado do reconhecimento do site: página de listagem,
padrão que marca o início de cada chamada e os metadados da fonte. A ficha
de cada uma fica em docs/fontes/ no repositório do Fomenta360.
"""

from __future__ import annotations

from datetime import date

from funding_intelligence.adapters.generico import Config, criar_adaptador

ANO = date.today().year
# Título típico de edital: "EDITAL FAPXX Nº 01/2026", "Chamada Pública 03/2026"...
TITULO_EDITAL = r"^\W*(edital|chamada|chamamento|sele[çc][ãa]o p[úu]blica)\b"

FONTES: list[Config] = [
    # ---------------------------------------------------------------- federais
    Config(
        id="capes",
        nome="CAPES",
        url="https://www.gov.br/capes/pt-br/assuntos/editais-e-resultados-capes",
        financiador="CAPES",
        tipo="agencia_federal",
        prioridade="P1",
        # A página lista os editais abertos como links (página do programa ou
        # PDF do edital); o prazo fica na página do programa.
        inicio_link=r"/acoes-e-programas/|/assuntos/premios/|/centrais-de-conteudo/editais/",
        conteudo="#content-core, main",
        descartar=r"^(resultados?( de editais)?|errata)\b|altera[çc][ãa]o$",
        lista_abertas=True,
        max_detalhes=40,
        instrumento_padrao="bolsa",
    ),
    Config(
        id="senai-inovacao",
        nome="SENAI/SESI · Plataforma Inovação para a Indústria",
        url="https://www.portaldaindustria.com.br/canais/plataforma-inovacao-para-industria/",
        financiador="SENAI / SESI",
        tipo="sistema_industria",
        prioridade="P1",
        # Cada categoria (Smart Factory, Chamada Regional, Agenda.Tech...) tem
        # página própria com cards de chamadas abertas e encerradas.
        seguir_listagens=r"/plataforma-inovacao-para-industria/categoria/",
        item_seletor="div.card-chamada",
        titulo_seletor=".card-body strong, .card-body h3, .card-body h4",
        conteudo="main, body",
        ano_minimo=ANO - 1,
        proponentes=("empresa", "startup"),
        instrumento_padrao="contratacao_pdi",
        detalhe=False,
    ),
    # ---------------------------------------------------------------- FAPs
    # FAPs em WordPress: a categoria de editais pela API REST.
    Config(id="fapeal", nome="FAPEAL", url="https://www.fapeal.br/pesquisador/editais/", financiador="FAPEAL",
           modo="wp", wp_categorias=("editais-vigentes", "chamadas-abertas"), lista_abertas=True,
           ano_minimo=ANO - 1, geografia=("AL",)),
    Config(id="fapesb", nome="FAPESB", url="https://www.fapesb.ba.gov.br/category/edital/", financiador="FAPESB",
           modo="wp", wp_categorias=("aberto",), ano_minimo=ANO - 1, geografia=("BA",)),
    Config(id="fapema", nome="FAPEMA", url="https://www.fapema.br/category/editais/editais-em-aberto/", financiador="FAPEMA",
           modo="wp", wp_categorias=("editais-em-aberto", "em-aberto"), lista_abertas=True, ano_minimo=ANO - 1,
           geografia=("MA",)),
    Config(id="fapespa", nome="FAPESPA", url="https://www.fapespa.pa.gov.br/category/chamadas/", financiador="FAPESPA",
           modo="wp", wp_categorias=("chamadas",), ano_minimo=ANO - 1, geografia=("PA",),
           filtro_titulo=r"chamada|edital|sele[çc][ãa]o|inscri"),
    Config(id="fapepi", nome="FAPEPI", url="https://www.fapepi.pi.gov.br/editais-fapepi/", financiador="FAPEPI",
           modo="wp", wp_categorias=("editais",), ano_minimo=ANO - 1, geografia=("PI",)),
    Config(id="fapesc", nome="FAPESC", url="https://fapesc.sc.gov.br/chamadas-abertas/", financiador="FAPESC",
           modo="wp", wp_categorias=("chamadas-abertas", "chamadas-em-andamento"), geografia=("SC",)),
    # FAPs com página HTML de editais abertos.
    Config(id="fapeg", nome="FAPEG", url="https://goias.gov.br/fapeg/editais/inscricoes-abertas/", financiador="FAPEG",
           # Tabela: Nº | Tipo | Origem | Descrição | Link ("ABRIR").
           item_seletor="table tbody tr", titulo_seletor="td:nth-of-type(4)", conteudo="main, article",
           lista_abertas=True, geografia=("GO",)),
    Config(id="fapitec", nome="FAPITEC/SE", url="https://fapitec.se.gov.br/editais-abertos/", financiador="FAPITEC/SE",
           inicio_titulo=TITULO_EDITAL, lista_abertas=True, ano_minimo=ANO - 1, geografia=("SE",)),
    Config(id="fapes", nome="FAPES", url="https://fapes.es.gov.br/editais-abertos-pesquisa-4", financiador="FAPES",
           urls_extras=("https://fapes.es.gov.br/editais-abertos-extensao-2",
                        "https://fapes.es.gov.br/edital-aberto-formação-científica",
                        "https://fapes.es.gov.br/chamadas-internacionais"),
           inicio_titulo=TITULO_EDITAL, lista_abertas=True, ano_minimo=ANO - 1, geografia=("ES",)),
    Config(id="fapt", nome="FAPT/TO", url="http://www.to.gov.br/fapt/01-editais-abertos/5sy36y0lf49g", financiador="FAPT",
           inicio_link=r"(edital|chamamento|chamada)", lista_abertas=True, ano_minimo=ANO - 1, geografia=("TO",)),
    Config(id="fapergs", nome="FAPERGS", url="https://fapergs.rs.gov.br/chamadas-e-editais", financiador="FAPERGS",
           inicio_link=r"fapergs\.rs\.gov\.br/(edital|chamada)", ano_minimo=ANO - 1, geografia=("RS",)),
    Config(id="fapac", nome="FAPAC", url="https://fapac.ac.gov.br/98-2/", financiador="FAPAC",
           inicio_titulo=TITULO_EDITAL, ano_minimo=ANO - 1, geografia=("AC",), detalhe=False),
    Config(id="fundect", nome="FUNDECT", url="https://www.fundect.ms.gov.br/informativos/consultas/", financiador="FUNDECT",
           inicio_titulo=TITULO_EDITAL, ano_minimo=ANO - 1, geografia=("MS",), detalhe=False),
    Config(id="fapdf", nome="FAPDF", url=f"https://www.fap.df.gov.br/editais-fapdf-{ANO}1", financiador="FAPDF",
           # O endereço muda todo ano (editais-fapdf-20261); o site do GDF
           # costuma recusar os servidores do GitHub.
           urls_extras=(f"https://www.fap.df.gov.br/chamadas-internacionais-{ANO}1",),
           inicio_titulo=r"^\W*(edital|chamada)\s+(n[º°o.]*\s*)?\d+/20\d\d", ano_minimo=ANO - 1, geografia=("DF",),
           detalhe=False),
    Config(id="fapeam", nome="FAPEAM", url="https://www.fapeam.am.gov.br/wp-admin/admin-ajax.php?action=get-editais&aba=vigentes",
           financiador="FAPEAM", modo="json", json_lista="editais_formatted", json_titulo="post_title",
           json_link="permalink", json_texto=("vigencia",), lista_abertas=True, geografia=("AM",)),
    Config(id="fapemat", nome="FAPEMAT", url="https://www.fapemat.mt.gov.br/pt/editais_1?categoryId=73983336",
           financiador="FAPEMAT", inicio_link=r"/pt/w/", lista_abertas=True, geografia=("MT",),
           descartar=r"^(resultado|homologa)"),
    Config(id="araucaria", nome="Fundação Araucária", url="https://www.fappr.pr.gov.br/Programas-Abertos",
           financiador="Fundação Araucária", inicio_titulo=r"^CP \d+/\d{2}:\s", lista_abertas=True,
           geografia=("PR",), detalhe=False, prioridade="P1"),
    # Agregador das FAPs (chamadas nacionais e internacionais conjuntas).
    Config(id="confap", nome="CONFAP", url="https://confap.org.br/pt/editais", financiador="CONFAP",
           tipo="agregador", inicio_link=r"/pt/editais/\d+/", lista_abertas=True, max_detalhes=20),
    Config(
        id="fapesp",
        nome="FAPESP",
        url="https://fapesp.br/chamadas/",
        financiador="FAPESP",
        prioridade="P1",
        # Cada chamada é um link para fapesp.br/<número>; o prazo vem como
        # "submissão de propostas: dd/mm/aaaa" logo abaixo.
        inicio_link=r"^https://(?:www\.)?fapesp\.br/\d{4,6}/?$",
        conteudo="#conteudo, main, .content, body",
        lista_abertas=True,
        geografia=("SP", "BR"),
    ),
    Config(
        id="faperj",
        nome="FAPERJ",
        url="https://www.faperj.br/?id=28.5.7",
        financiador="FAPERJ",
        prioridade="P1",
        # Página corrida com todos os editais do ano: cada um começa em
        # "Edital FAPERJ Nº NN/AAAA" e traz "Submissão de propostas on-line".
        inicio_titulo=r"^Edital FAPERJ N",
        conteudo="section.corpo-interna, #conteudo, body",
        ano_minimo=ANO - 1,
        geografia=("RJ",),
        detalhe=False,
    ),
]

ADAPTADORES = {config.id: criar_adaptador(config) for config in FONTES}
