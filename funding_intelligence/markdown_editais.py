"""Edital em PDF -> Markdown (Fomenta360).

Regra do projeto: o PDF do edital não é guardado em lugar nenhum. Ele é baixado
para a memória, convertido em Markdown e descartado; fica o Markdown, o link
oficial do PDF e o hash SHA-256 do arquivo (para saber quando o órgão trocou o
documento, sem precisar guardá-lo).

A conversão usa o Docling (docling-project/docling, MIT): lê a camada de texto
quando ela existe, reconhece tabelas (cronogramas, valores) e aplica OCR às
páginas que são só imagem (edital escaneado), com o EasyOCR em português.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

from pypdf import PdfReader

# Página com menos texto que isto na camada de texto é tratada como imagem.
MIN_CARACTERES_PAGINA = 40


@dataclass
class Conversao:
    markdown: str
    sha256: str
    paginas: int
    paginas_imagem: int  # páginas sem camada de texto (passaram por OCR)


def paginas_sem_texto(pdf: bytes) -> tuple[int, int]:
    """(total de páginas, páginas sem camada de texto)."""
    try:
        leitor = PdfReader(io.BytesIO(pdf))
    except Exception:
        return 0, 0
    total = len(leitor.pages)
    vazias = 0
    for pagina in leitor.pages:
        try:
            texto = pagina.extract_text() or ""
        except Exception:
            texto = ""
        if len(texto.strip()) < MIN_CARACTERES_PAGINA:
            vazias += 1
    return total, vazias


_conversor = None


def _docling():
    """Conversor criado uma vez por processo (carrega os modelos de layout e OCR)."""
    global _conversor
    if _conversor is None:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import EasyOcrOptions, PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        opcoes = PdfPipelineOptions(
            do_ocr=True,
            do_table_structure=True,
            ocr_options=EasyOcrOptions(lang=["pt", "en"]),
        )
        _conversor = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opcoes)})
    return _conversor


def converter_pdf(pdf: bytes, nome: str = "edital.pdf") -> Conversao:
    """Converte o PDF (em memória) em Markdown. Nada é escrito em disco."""
    from docling.datamodel.base_models import DocumentStream

    total, vazias = paginas_sem_texto(pdf)
    resultado = _docling().convert(DocumentStream(name=nome, stream=io.BytesIO(pdf)))
    markdown = resultado.document.export_to_markdown()
    return Conversao(
        markdown=markdown.strip() + "\n",
        sha256=hashlib.sha256(pdf).hexdigest(),
        paginas=total,
        paginas_imagem=vazias,
    )
