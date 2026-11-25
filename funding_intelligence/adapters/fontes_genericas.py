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
    # Editais viraram tipo próprio do WordPress (/edital/), sem situação na API;
    # a página separa a aba "Abertos" (#abertos-tab) da "Em Execução". Aba vazia
    # é resposta válida: a FAPEPI está sem edital aberto (25/11/2026).
    Config(id="fapepi", nome="FAPEPI", url="https://www.fapepi.pi.gov.br/editais-fapepi/", financiador="FAPEPI",
           conteudo="#abertos-tab", vazio_valido=True, lista_abertas=True, inicio_titulo=TITULO_EDITAL,
           geografia=("PI",)),
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
    Config(id="fapeap", nome="FAPEAP", url="https://fapeap.portal.ap.gov.br/", financiador="FAPEAP",
           # Os programas com edital ficam no menu "Programas"; cada página traz o edital.
           inicio_link=r"/pagina/programas/[a-z0-9-]+$", lixo=("script", "style", "noscript", "iframe", "svg"),
           conteudo="body", lista_abertas=True, geografia=("AP",), max_detalhes=15),
    Config(id="facepe", nome="FACEPE", url="https://www2.facepe.br/editais/todos/?c=aberto", financiador="FACEPE",
           # A página de abertos lista os PDFs: "Edital nº 31/2026 ... (1 de outubro de 2026)".
           inicio_link=r"^\W*edital\s+n", lista_abertas=True, ano_minimo=ANO - 1, geografia=("PE",), detalhe=False),
    Config(id="fapern", nome="FAPERN", url=f"https://www.fapern.rn.gov.br/documentos/Editais/Editais%20{ANO}/",
           urls_extras=(f"https://www.fapern.rn.gov.br/documentos/Editais/Editais%20{ANO - 1}/",),
           financiador="FAPERN", inicio_link=r"/Editais(?:%20| )\d{4}/Edital", geografia=("RN",), max_detalhes=20),
    Config(id="faperr", nome="FAPERR", url="https://faperr.rr.gov.br/", financiador="FAPERR", modo="wp",
           filtro_titulo=r"inscri|chamada|edita|sele[çc][ãa]o", ano_minimo=ANO - 1, geografia=("RR",)),
    Config(id="rnp", nome="RNP · Chamadas públicas", financiador="RNP", tipo="organizacao_social",
           url="https://www.rnp.br/chamadas/chamadas-publicas/", inicio_titulo=TITULO_EDITAL,
           inicio_link=r"rnp\.br/chamadas/.+/.", ano_minimo=ANO - 1),
    Config(id="fundo-amazonia", nome="Fundo Amazônia · Chamadas públicas", financiador="BNDES / Fundo Amazônia",
           tipo="fundo_federal", url="https://www.fundoamazonia.gov.br/pt/como-apresentar-projetos/chamadas-publicas/",
           # As chamadas ficam no menu lateral, que o motor descartaria.
           inicio_link=r"/chamadas-publicas/[a-z0-9-]+/?$", lixo=("script", "style", "noscript", "iframe", "svg"),
           conteudo="body", geografia=("AC", "AM", "AP", "MA", "MT", "PA", "RO", "RR", "TO"),
           instrumento_padrao="termo_fomento"),
    Config(id="inovativa", nome="InovAtiva · Painel de oportunidades", financiador="InovAtiva (MDIC / Sebrae)",
           tipo="programa_federal", url="https://inovativa.online/painel-de-oportunidades/", modo="wp",
           # Tipo de post próprio do WordPress (o painel é montado em JavaScript).
           wp_endpoint="wp-json/wp/v2/oportunidades", ano_minimo=ANO - 1, proponentes=("startup",),
           instrumento_padrao="outros"),
    Config(id="anp-premio", nome="ANP · Prêmio de Inovação Tecnológica", financiador="ANP", tipo="agencia_reguladora",
           url="https://www.gov.br/anp/pt-br/assuntos/tecnologia-meio-ambiente/premio-anp-inovacao-tecnologica",
           # A ANP não publica chamadas de P&D (quem executa é a petroleira); o
           # prêmio anual é a oportunidade pública do programa.
           inicio_link=r"/premio-anp-inovacao-tecnologica/premio-anp-de-inovacao-tecnologica-20\d\d", ano_minimo=ANO - 1,
           instrumento_padrao="premio", proponentes=("empresa", "ict", "pesquisador")),
    # Bancos, estatais e fundações.
    Config(id="fbb", nome="Fundação Banco do Brasil · Editais", financiador="Fundação Banco do Brasil", tipo="fundacao_privada",
           url="https://fbb.org.br/editais-de-projetos/editais-publicos/", inicio_link=r"fbb\.org\.br/edital-publico/.",
           instrumento_padrao="termo_fomento", proponentes=("osc", "cooperativa")),
    Config(id="petrobras-socioambiental", nome="Petrobras · Seleções públicas socioambientais", financiador="Petrobras",
           tipo="estatal", url="https://petrobras.com.br/sustentabilidade/selecoes-publicas", inicio_titulo=TITULO_EDITAL,
           instrumento_padrao="termo_fomento", ano_minimo=ANO - 1),
    Config(id="brde-fundo-verde", nome="BRDE · Fundo Verde", financiador="BRDE", tipo="banco_desenvolvimento",
           url="https://www.brde.com.br/fundo-verde/", inicio_titulo=TITULO_EDITAL, geografia=("RS", "SC", "PR"),
           ano_minimo=ANO - 1),
    Config(id="serrapilheira", nome="Instituto Serrapilheira", financiador="Instituto Serrapilheira", tipo="fundacao_privada",
           url="https://serrapilheira.org/todas-as-chamadas/", inicio_link=r"serrapilheira\.org/ano/.", ano_minimo=ANO - 1),
    Config(id="funbio", nome="Funbio · Chamadas de projetos", financiador="Funbio", tipo="fundacao_privada",
           url="https://chamadas.funbio.org.br/", inicio_titulo=TITULO_EDITAL, inicio_link=r"chamadas\.funbio\.org\.br/.+",
           instrumento_padrao="termo_fomento"),
    Config(id="ics", nome="Instituto Clima e Sociedade · Editais", financiador="iCS", tipo="fundacao_privada",
           url="https://climaesociedade.org/editais/", inicio_titulo=TITULO_EDITAL, inicio_link=r"climaesociedade\.org/.+edital",
           ano_minimo=ANO - 1, instrumento_padrao="termo_fomento"),
    Config(id="fundo-casa", nome="Fundo Casa Socioambiental · Chamadas", financiador="Fundo Casa", tipo="fundacao_privada",
           url="https://casa.org.br/chamadas", inicio_titulo=TITULO_EDITAL, inicio_link=r"casa\.org\.br/.+chamada",
           ano_minimo=ANO - 1, instrumento_padrao="termo_fomento", proponentes=("osc",)),
    Config(id="itau-social", nome="Itaú Social · Editais", financiador="Itaú Social", tipo="fundacao_privada",
           url="https://www.itausocial.org.br/editais/", inicio_titulo=TITULO_EDITAL, inicio_link=r"itausocial\.org\.br/.+",
           ano_minimo=ANO - 1, instrumento_padrao="termo_fomento", proponentes=("osc",)),
    Config(id="open-startups", nome="100 Open Startups · Oportunidades", financiador="Empresas (inovação aberta)",
           tipo="agregador", url="https://www.openstartups.net/oportunidades/startups/", inicio_titulo=TITULO_EDITAL,
           inicio_link=r"openstartups\.net/.+", proponentes=("startup",), instrumento_padrao="outros", ano_minimo=ANO - 1),
    Config(id="bnb-fundeci", nome="BNB · Fundeci (editais)", financiador="Banco do Nordeste · Fundeci",
           tipo="banco_desenvolvimento", url="https://www.bnb.gov.br/fundeci/editais",
           inicio_link=r"/fundeci/editais/-/asset_publisher/", ano_minimo=ANO - 1,
           geografia=("AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE", "MG", "ES")),
    # Bancos e agências de fomento: linhas de crédito permanentes (fluxo
    # contínuo, sem prazo). Entram no catálogo como mecanismos.
    Config(id="basa-fno", nome="Banco da Amazônia · Linhas FNO", financiador="Banco da Amazônia · FNO",
           tipo="banco_desenvolvimento", url="https://www.bancoamazonia.com.br/linhas-de-fomento/fno",
           inicio_link=r"/linhas-de-fomento/fno/[a-z0-9-]+$", canal="fluxo_continuo", lista_abertas=True,
           instrumento_padrao="credito", detalhe=False, ler_pdf=False, proponentes=("empresa", "cooperativa"),
           geografia=("AC", "AM", "AP", "PA", "RO", "RR", "TO"), descartar=r"^conhe[çc]a"),
    Config(id="goias-fomento", nome="Goiás Fomento · Linhas de crédito", financiador="Goiás Fomento",
           tipo="agencia_fomento", url="https://www.goiasfomento.com/linhas-de-credito/",
           inicio_link=r"goiasfomento\.com/(linhas-de-credito/[a-z0-9-]+/|linha-[a-z0-9-]+/)$", canal="fluxo_continuo",
           lista_abertas=True, instrumento_padrao="credito", detalhe=False, ler_pdf=False,
           proponentes=("empresa",), geografia=("GO",), descartar=r"oferece cr[ée]dito"),
    # Sebrae estadual com página própria de chamadas (os demais estados não
    # publicam edital de fomento fora da transparência/licitações).
    Config(id="sebrae-rs", nome="Sebrae RS · Chamadas públicas", financiador="Sebrae RS", tipo="sistema_s",
           url="https://sebraers.com.br/editais-e-licitacoes-chamadas-publicas/", inicio_titulo=TITULO_EDITAL,
           inicio_link=r"chamada-publica|chamada_publica", ano_minimo=ANO - 1, geografia=("RS",),
           proponentes=("empresa",), instrumento_padrao="outros"),
    # Secretarias estaduais de ciência, tecnologia e inovação.
    Config(id="sct-ce", nome="SCT-CE · Editais", url="https://www.sct.ce.gov.br/editais/", financiador="Secitece-CE",
           tipo="secretaria_estadual", inicio_titulo=TITULO_EDITAL, ano_minimo=ANO - 1, geografia=("CE",)),
    Config(id="secti-ma", nome="SECTI-MA · Editais", url=f"https://secti.ma.gov.br/programas-ou-campanhas/editais-{ANO}",
           financiador="SECTI-MA", tipo="secretaria_estadual", inicio_titulo=TITULO_EDITAL, ano_minimo=ANO - 1,
           geografia=("MA",)),
    Config(id="belmont-forum", nome="Belmont Forum · Open opportunities", financiador="Belmont Forum",
           tipo="internacional", prioridade="P3", url="https://belmontforum.org/open-opportunities/", modo="wp",
           # Tipo de post próprio; o Brasil participa pela FAPESP e pelo CONFAP.
           wp_endpoint="wp-json/wp/v2/open_opportunity", geografia=("INTERNACIONAL",),
           proponentes=("ict", "universidade", "pesquisador")),
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
