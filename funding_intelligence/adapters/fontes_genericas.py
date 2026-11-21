"""Fontes coletadas pelo adaptador genérico (Fomenta360).

Cada entrada é o resultado do reconhecimento do site: página de listagem,
padrão que marca o início de cada chamada e os metadados da fonte. A ficha
de cada uma fica em docs/fontes/ no repositório do Fomenta360.
"""

from __future__ import annotations

from datetime import date

from funding_intelligence.adapters.generico import Config, criar_adaptador

ANO = date.today().year

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
