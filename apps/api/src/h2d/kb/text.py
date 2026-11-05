"""Funções puras da ingestão: hash, cabeçalho do manual e divisão em trechos.

Nada aqui toca banco, arquivo ou modelo de embeddings, então tudo é testável sem infraestrutura.
"""

import hashlib
import re
from dataclasses import dataclass

# O MiniLM lê só 128 tokens por trecho (ADR-003). Medido nos manuais: com 110 palavras, 19 de 101
# trechos passavam disso; com 60, só 2 de 121.
DEFAULT_MAX_WORDS = 60

_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_LIST_ITEM = re.compile(r"^\s*(\d+[.)]|[-*+])\s+")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def split_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Separa o cabeçalho `chave: valor` entre `---`. Sem cabeçalho, devolve tudo como corpo."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta: dict[str, str] = {}
    for line in parts[1].splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip():
            meta[key.strip()] = value.strip()
    return meta, parts[2].lstrip("\n")


@dataclass(frozen=True)
class Chunk:
    position: int
    breadcrumb: str
    content: str


def _words(text: str) -> int:
    return len(text.split())


def _blocks(lines: list[str]) -> list[str]:
    """Quebra o corpo de uma seção em blocos que não devem ser partidos.

    Um bloco é um parágrafo, uma tabela, um bloco de código ou uma lista seguida (passos
    numerados ficam juntos).
    """
    blocks: list[list[str]] = []
    current: list[str] = []
    kind: str | None = None
    in_fence = False

    def flush() -> None:
        nonlocal current, kind
        if current:
            blocks.append(current)
        current, kind = [], None

    for line in lines:
        if in_fence:
            current.append(line)
            if _FENCE.match(line):
                in_fence = False
                flush()
            continue
        if _FENCE.match(line):
            flush()
            in_fence = True
            current, kind = [line], "code"
            continue
        if not line.strip():
            flush()
            continue
        line_kind = (
            "table" if _TABLE_ROW.match(line) else "list" if _LIST_ITEM.match(line) else "text"
        )
        # Texto solto logo depois de um item de lista é continuação do item.
        if kind == "list" and line_kind == "text" and line.startswith((" ", "\t")):
            line_kind = "list"
        if kind is not None and line_kind != kind:
            flush()
        kind = line_kind
        current.append(line)
    flush()
    return ["\n".join(block) for block in blocks]


def _split_large(block: str, max_words: int) -> list[str]:
    """Último recurso para um bloco maior que o limite: parte por linha (item, linha de tabela)."""
    pieces: list[str] = []
    current: list[str] = []
    for line in block.splitlines():
        if current and _words("\n".join([*current, line])) > max_words:
            pieces.append("\n".join(current))
            current = []
        current.append(line)
    if current:
        pieces.append("\n".join(current))
    return pieces


def chunk_markdown(
    markdown: str, *, title: str = "", max_words: int = DEFAULT_MAX_WORDS
) -> list[Chunk]:
    """Divide o Markdown por títulos, sem partir tabelas, código nem passos numerados.

    Cada trecho fica dentro de uma única seção e leva o caminho de títulos (`breadcrumb`) para a
    citação e para a busca. Seções vazias não geram trecho.
    """
    stack: list[tuple[int, str]] = []
    sections: list[tuple[str, list[str]]] = []
    body: list[str] = []
    in_fence = False

    def breadcrumb() -> str:
        names = [name for _, name in stack]
        if title and (not names or names[0] != title):
            names.insert(0, title)
        return " > ".join(names)

    current_crumb = breadcrumb()
    for line in markdown.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
        heading = None if in_fence else _HEADING.match(line)
        if heading:
            sections.append((current_crumb, body))
            body = []
            level, name = len(heading.group(1)), heading.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, name))
            current_crumb = breadcrumb()
        else:
            body.append(line)
    sections.append((current_crumb, body))

    chunks: list[Chunk] = []
    for crumb, lines in sections:
        pending: list[str] = []
        for block in _blocks(lines):
            pieces = _split_large(block, max_words) if _words(block) > max_words else [block]
            for piece in pieces:
                if pending and _words("\n\n".join([*pending, piece])) > max_words:
                    chunks.append(Chunk(len(chunks), crumb, "\n\n".join(pending)))
                    pending = []
                pending.append(piece)
        if pending:
            chunks.append(Chunk(len(chunks), crumb, "\n\n".join(pending)))
    return chunks
