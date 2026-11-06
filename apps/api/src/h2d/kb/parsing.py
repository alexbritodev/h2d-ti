"""Converte o arquivo enviado em Markdown, para o chunking dividir por título.

Markdown e texto passam direto. PDF e DOCX saem da leitura de texto: leve, sem OCR e sem modelo de
layout (o Docling foi descartado por peso na VPS). PDF digitalizado (só imagem) é recusado com um
motivo claro, em vez de gerar um documento vazio.
"""

import io
import re
import statistics
import unicodedata
from collections import Counter
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader
from pypdf.errors import PyPdfError

MAX_PDF_PAGES = 300
# Média de caracteres por página abaixo disso: o PDF é imagem digitalizada, sem texto.
MIN_CHARS_PER_PAGE = 40

TEXT_EXTENSIONS = {".md", ".markdown", ".txt"}


class ParsingError(Exception):
    """Arquivo que não dá para ler. A mensagem aparece na tela de ingestão."""


def to_markdown(filename: str, data: bytes) -> str:
    extension = Path(filename).suffix.lower()
    if extension in TEXT_EXTENSIONS:
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ParsingError("O arquivo não está em UTF-8") from error
    if extension == ".pdf":
        return pdf_to_markdown(data)
    if extension == ".docx":
        return docx_to_markdown(data)
    raise ParsingError(f"Formato {extension or 'desconhecido'} não suportado")


# --- PDF ------------------------------------------------------------------------------------------

_PAGE_NUMBER = re.compile(r"^\s*(p[áa]gina\s+)?\d+(\s*(/|de)\s*\d+)?\s*$", re.IGNORECASE)
_NUMBERED = re.compile(r"^(\d+(?:\.\d+){0,3})[.)]?\s+(\S.{0,78})$")
_LIST_STEP = re.compile(r"^\d+[.)]\s+\S")
_BULLET_CHARS = "•●▪◦–—*-"
_SENTENCE_END = re.compile(r"[.!?:;]$")


def pdf_to_markdown(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ParsingError("O PDF tem senha")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ParsingError(f"O PDF tem mais de {MAX_PDF_PAGES} páginas")
        pages = [(page.extract_text() or "") for page in reader.pages]
    except ParsingError:
        raise
    except (PyPdfError, ValueError, KeyError, OSError) as error:
        raise ParsingError(f"Não consegui abrir o PDF: {error}") from error

    if not pages:
        raise ParsingError("O PDF não tem páginas")
    if sum(len(p.strip()) for p in pages) / len(pages) < MIN_CHARS_PER_PAGE:
        raise ParsingError(
            "O PDF parece ser digitalizado (só imagens). Ainda não há leitura por OCR: "
            "envie uma versão com texto selecionável."
        )
    return _text_to_markdown(_drop_page_furniture(pages))


def _drop_page_furniture(pages: list[str]) -> list[str]:
    """Tira número de página e cabeçalho/rodapé que se repetem em quase todas as páginas."""
    counts: Counter[str] = Counter()
    for page in pages:
        counts.update({line.strip() for line in page.splitlines() if line.strip()})
    repeated = {
        line
        for line, n in counts.items()
        if len(pages) >= 2 and n >= max(2, -(-6 * len(pages) // 10)) and len(line) <= 90
    }
    cleaned = []
    for page in pages:
        keep = [
            line
            for line in page.splitlines()
            if line.strip() not in repeated and not _PAGE_NUMBER.match(line)
        ]
        cleaned.append("\n".join(keep))
    return cleaned


def _bullet_text(text: str) -> str | None:
    """Texto do item se a linha começa com marcador de lista. Os PDFs gravam o marcador como
    caractere privado da fonte ou de controle (U+F0B7, U+007F...), então isso também vale."""
    if (
        len(text) > 2
        and text[1] == " "
        and (text[0] in _BULLET_CHARS or unicodedata.category(text[0]) in ("Co", "Cc"))
    ):
        return text[2:].strip()
    return None


def _is_heading(line: str, previous: str, following: str) -> str | None:
    """Devolve o prefixo Markdown se a linha parece um título, ou None."""
    text = line.strip()
    if not text or len(text) > 80 or text.endswith((".", ",", ";")):
        return None
    numbered = _NUMBERED.match(text)
    if numbered:
        depth = numbered.group(1).count(".") + 1
        # "1. Abra..." entre outros itens numerados é passo de procedimento, não título.
        in_steps = bool(_LIST_STEP.match(previous.strip()) or _LIST_STEP.match(following.strip()))
        if depth == 1 and in_steps:
            return None
        return "#" * min(depth + 1, 4) + " "
    letters = [c for c in text if c.isalpha()]
    if len(letters) >= 4 and text.isupper() and len(text) <= 70:
        return "## "
    return None


def _text_to_markdown(pages: list[str]) -> str:
    lines = [line.rstrip() for page in pages for line in [*page.splitlines(), ""]]
    widths = [len(line) for line in lines if len(line) > 30]
    typical = statistics.median(widths) if widths else 80

    out: list[str] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            out.append(" ".join(paragraph))
            out.append("")
            paragraph.clear()

    for index, line in enumerate(lines):
        text = line.strip()
        if not text:
            flush()
            continue
        previous = lines[index - 1] if index > 0 else ""
        following = lines[index + 1] if index + 1 < len(lines) else ""
        prefix = _is_heading(text, previous, following)
        if prefix:
            flush()
            out.extend([f"{prefix}{text}", ""])
            continue
        bullet = _bullet_text(text)
        if bullet:
            flush()
            out.append(f"- {bullet}")
            continue
        if _LIST_STEP.match(text):
            flush()
            out.append(text)
            continue
        if paragraph and paragraph[-1].endswith("-") and text[:1].islower():
            paragraph[-1] = paragraph[-1][:-1] + text  # palavra hifenizada na quebra de linha
        else:
            # Linha curta que fecha frase termina o parágrafo: é como o texto composto se comporta.
            if (
                paragraph
                and _SENTENCE_END.search(paragraph[-1])
                and len(lines[index - 1]) < 0.75 * typical
                and text[:1].isupper()
            ):
                flush()
            paragraph.append(text)
    flush()
    return "\n".join(out).strip() + "\n"


# --- DOCX -----------------------------------------------------------------------------------------

_HEADING_STYLE = re.compile(r"^(?:heading|t[ií]tulo)\s*(\d)$", re.IGNORECASE)


def _cell(text: str) -> str:
    return " ".join(text.replace("|", "/").split())


def _table_markdown(table: Table) -> str:
    rows = [[_cell(cell.text) for cell in row.cells] for row in table.rows]
    rows = [row for row in rows if any(row)]
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
    lines += ["| " + " | ".join(row) + " |" for row in rows[1:]]
    return "\n".join(lines)


def docx_to_markdown(data: bytes) -> str:
    try:
        document = Document(io.BytesIO(data))
    except Exception as error:  # o python-docx levanta tipos variados em arquivo quebrado
        raise ParsingError(f"Não consegui abrir o DOCX: {error}") from error

    blocks: list[str] = []
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            paragraph = Paragraph(child, document)  # type: ignore[arg-type]
            text = paragraph.text.strip()
            if not text:
                continue
            style = (paragraph.style.name if paragraph.style is not None else "") or ""
            heading = _HEADING_STYLE.match(style)
            if heading:
                blocks.append("#" * min(int(heading.group(1)) + 1, 6) + " " + text)
            elif style.lower() in {"title", "título", "titulo"}:
                blocks.append("# " + text)
            elif "bullet" in style.lower() or "marcador" in style.lower():
                blocks.append("- " + text)
            elif "number" in style.lower() or "numer" in style.lower():
                blocks.append("1. " + text)
            else:
                blocks.append(text)
        elif tag == "tbl":
            table = _table_markdown(Table(child, document))  # type: ignore[arg-type]
            if table:
                blocks.append(table)
    if not blocks:
        raise ParsingError("Não encontrei texto no documento")
    return "\n\n".join(blocks) + "\n"
