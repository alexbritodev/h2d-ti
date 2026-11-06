import io
from pathlib import Path

import pytest
from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.kb.embeddings import FakeEmbedder
from h2d.kb.ingest import IngestionError, claim_next_job, process_job, register_upload
from h2d.kb.parsing import ParsingError, to_markdown
from h2d.kb.search import search_chunks
from h2d.kb.text import chunk_markdown
from h2d.models import KbChunk, VersionStatus

CABECALHO = "MANUAL INTERNO DE TI"

PAGINAS = [
    [
        "1. VPN corporativa",
        "",
        "A VPN dá acesso seguro aos sistemas internos quando você trabalha fora da",
        "empresa. O cliente usado é o SecureLink e o servidor é vpn.empresa.exemplo.",
        "",
        "A sessão cai após 12 horas de conexão contínua.",
        "",
        "• Use sempre um computador da empresa",
        "• Aprove o código no autenticador",
    ],
    [
        "2. Wi-Fi",
        "",
        "A rede de visitantes é isolada e não alcança sistemas internos, impressoras",
        "nem pastas de rede. A senha vale por um dia.",
    ],
    ["3. Impressoras", "", "Instale a impressora pelo nome IMP-02-01 no Portal de Software."],
    ["4. Backup", "", "O backup diário roda de madrugada e guarda os arquivos por 30 dias."],
]


def _pdf(pages: list[list[str]], *, encrypt: str | None = None, so_imagem: bool = False) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, encrypt=encrypt)
    for numero, linhas in enumerate(pages, start=1):
        if so_imagem:
            pdf.rect(100, 100, 300, 300, fill=1)
        else:
            pdf.drawString(72, 800, CABECALHO)  # cabeçalho repetido em toda página
            y = 760
            for linha in linhas:
                pdf.drawString(72, y, linha)
                y -= 16
            pdf.drawString(260, 40, f"Página {numero} de {len(pages)}")
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _docx() -> bytes:
    documento = Document()
    documento.add_heading("Manual de e-mail", level=0)
    documento.add_heading("Limites", level=1)
    documento.add_paragraph("A caixa tem 50 GB e o anexo pode ter até 25 MB.")
    documento.add_paragraph("Use o aplicativo Outlook", style="List Bullet")
    documento.add_paragraph("Aprove o autenticador", style="List Bullet")
    documento.add_heading("Erros comuns", level=2)
    tabela = documento.add_table(rows=2, cols=2)
    tabela.rows[0].cells[0].text = "Mensagem"
    tabela.rows[0].cells[1].text = "O que fazer"
    tabela.rows[1].cells[0].text = "Caixa cheia"
    tabela.rows[1].cells[1].text = "Esvazie Itens Excluídos"
    buffer = io.BytesIO()
    documento.save(buffer)
    return buffer.getvalue()


def test_pdf_vira_markdown_com_titulos_paragrafos_e_lista():
    md = to_markdown("manual.pdf", _pdf(PAGINAS))

    assert "## 1. VPN corporativa" in md
    assert "## 2. Wi-Fi" in md
    # Linhas quebradas pelo layout voltam a ser um parágrafo só.
    assert "quando você trabalha fora da empresa. O cliente usado é o SecureLink" in md
    assert "- Use sempre um computador da empresa" in md
    assert "- Aprove o código no autenticador" in md


def test_pdf_perde_cabecalho_repetido_e_numero_de_pagina():
    md = to_markdown("manual.pdf", _pdf(PAGINAS))

    assert CABECALHO not in md
    assert "Página 2 de 4" not in md


def test_pdf_curto_tambem_perde_o_cabecalho_repetido():
    md = to_markdown("curto.pdf", _pdf(PAGINAS[:2]))

    assert CABECALHO not in md
    assert "## 1. VPN corporativa" in md


def test_pdf_so_de_imagem_e_recusado_com_o_motivo():
    with pytest.raises(ParsingError, match="digitalizado"):
        to_markdown("scan.pdf", _pdf([[], []], so_imagem=True))


def test_pdf_com_senha_e_pdf_quebrado_sao_recusados():
    with pytest.raises(ParsingError, match="senha"):
        to_markdown("fechado.pdf", _pdf(PAGINAS, encrypt="segredo"))
    with pytest.raises(ParsingError, match="Não consegui abrir"):
        to_markdown("quebrado.pdf", b"%PDF-1.4\nlixo sem estrutura")


def test_docx_vira_markdown_com_titulos_lista_e_tabela():
    md = to_markdown("manual.docx", _docx())

    assert "# Manual de e-mail" in md
    assert "## Limites" in md
    assert "### Erros comuns" in md
    assert "- Use o aplicativo Outlook" in md
    assert "| Mensagem | O que fazer |" in md and "| --- | --- |" in md
    assert "| Caixa cheia | Esvazie Itens Excluídos |" in md


def test_docx_quebrado_e_recusado():
    with pytest.raises(ParsingError, match="DOCX"):
        to_markdown("quebrado.docx", b"PK\x03\x04isto nao e um docx")


def test_texto_fora_de_utf8_e_recusado():
    with pytest.raises(ParsingError, match="UTF-8"):
        to_markdown("velho.txt", "açúcar".encode("latin-1"))


def test_paragrafo_gigante_em_uma_linha_so_e_partido_por_frases():
    frase = "A conexão cai quando a rede bloqueia a porta usada pelo cliente. "
    texto = "## Problemas\n\n" + frase * 40

    chunks = chunk_markdown(texto, max_words=60)

    assert len(chunks) > 1
    assert all(len(c.content.split()) <= 60 for c in chunks)
    assert all(c.content.rstrip().endswith(".") for c in chunks)


# --- Pelo pipeline completo -----------------------------------------------------------------------


async def _processar(session: AsyncSession, tmp_path: Path, nome: str, dados: bytes):
    registrado = await register_upload(
        session, upload_dir=str(tmp_path), actor_id=None, filename=nome, data=dados
    )
    await session.commit()
    job = await claim_next_job(session)
    assert job is not None
    await process_job(session, job, FakeEmbedder())
    await session.commit()
    return registrado


async def test_pdf_enviado_vira_trechos_pesquisaveis_com_o_titulo_na_citacao(session, tmp_path):
    registrado = await _processar(session, tmp_path, "Manual de rede.pdf", _pdf(PAGINAS))

    await session.refresh(registrado.version)
    assert registrado.version.status is VersionStatus.ACTIVE
    assert registrado.document.title == "Manual de rede"
    trechos = list(await session.scalars(select(KbChunk).order_by(KbChunk.position)))
    assert any("VPN corporativa" in t.breadcrumb for t in trechos)
    hits = await search_chunks(
        session, "quanto tempo dura a sessão da VPN", FakeEmbedder(), can_see_it=False
    )
    assert hits and "12 horas" in hits[0].content


async def test_docx_enviado_vira_trechos_pesquisaveis(session, tmp_path):
    registrado = await _processar(session, tmp_path, "email.docx", _docx())

    await session.refresh(registrado.version)
    assert registrado.version.status is VersionStatus.ACTIVE
    hits = await search_chunks(
        session, "limite do anexo no e-mail", FakeEmbedder(), can_see_it=False
    )
    assert hits and "25 MB" in hits[0].content


@pytest.mark.parametrize(
    ("nome", "dados", "trecho"),
    [
        ("falso.pdf", b"isto e texto, nao um PDF", "não é um PDF"),
        ("falso.docx", b"%PDF-1.4 renomeado", "não é um DOCX"),
        ("programa.exe", b"MZ", "não suportado"),
    ],
)
async def test_arquivo_renomeado_ou_de_outro_tipo_e_recusado_no_envio(
    session, tmp_path, nome, dados, trecho
):
    with pytest.raises(IngestionError, match=trecho):
        await register_upload(
            session, upload_dir=str(tmp_path), actor_id=None, filename=nome, data=dados
        )


async def test_pdf_digitalizado_falha_o_job_com_o_motivo_para_a_tela(session, tmp_path):
    registrado = await register_upload(
        session,
        upload_dir=str(tmp_path),
        actor_id=None,
        filename="scan.pdf",
        data=_pdf([[], []], so_imagem=True),
    )
    await session.commit()
    job = await claim_next_job(session)
    assert job is not None

    with pytest.raises(IngestionError, match="digitalizado"):
        await process_job(session, job, FakeEmbedder())

    assert registrado.version.status is VersionStatus.PROCESSING  # o worker grava a falha depois
