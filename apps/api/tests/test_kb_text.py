from pathlib import Path

import pytest

from h2d.kb.text import chunk_markdown, sha256_hex, split_front_matter

# Os manuais fictícios ficam só na máquina local (fora do Git, fora do container): sem eles, pula.
MANUAIS = next(
    (p / "manuais" for p in Path(__file__).resolve().parents if (p / "manuais").is_dir()), None
)


def test_sha256_e_estavel_e_diferencia_conteudo():
    assert sha256_hex(b"abc") == sha256_hex(b"abc")
    assert sha256_hex(b"abc") != sha256_hex(b"abd")
    assert len(sha256_hex(b"")) == 64


def test_front_matter_separa_cabecalho_e_corpo():
    meta, body = split_front_matter(
        "---\ntitulo: Meu manual\nvisibilidade: ti\n---\n\n# Corpo\ntexto"
    )

    assert meta == {"titulo": "Meu manual", "visibilidade": "ti"}
    assert body.startswith("# Corpo")


@pytest.mark.parametrize("texto", ["sem cabecalho", "---\nsó abre, nunca fecha"])
def test_front_matter_ausente_ou_incompleto_devolve_tudo_como_corpo(texto):
    meta, body = split_front_matter(texto)

    assert meta == {}
    assert body == texto


def test_breadcrumb_segue_a_hierarquia_de_titulos():
    md = "# Manual\n\n## Instalar\n\nPasso um.\n\n### Detalhes\n\nMais texto.\n\n## Erros\n\nOutro."

    chunks = chunk_markdown(md)

    assert [c.breadcrumb for c in chunks] == [
        "Manual > Instalar",
        "Manual > Instalar > Detalhes",
        "Manual > Erros",
    ]
    assert [c.position for c in chunks] == [0, 1, 2]


def test_titulo_do_documento_abre_o_breadcrumb():
    chunks = chunk_markdown("## Seção\n\ntexto", title="VPN")

    assert chunks[0].breadcrumb == "VPN > Seção"


def test_trechos_respeitam_o_limite_de_palavras():
    paragrafos = "\n\n".join(" ".join(["palavra"] * 40) for _ in range(6))

    chunks = chunk_markdown(f"## Seção\n\n{paragrafos}", max_words=100)

    assert len(chunks) > 1
    assert all(len(c.content.split()) <= 100 for c in chunks)
    assert all(c.breadcrumb == "Seção" for c in chunks)


def test_passos_numerados_nao_sao_partidos():
    passos = "\n".join(
        f"{n}. Passo número {n} com algumas palavras para contar" for n in range(1, 8)
    )
    md = f"## Fazer\n\n{' '.join(['intro'] * 50)}\n\n{passos}"

    chunks = chunk_markdown(md, max_words=80)

    com_passos = [c for c in chunks if "1. Passo" in c.content]
    assert len(com_passos) == 1
    assert "7. Passo" in com_passos[0].content


def test_tabela_nao_e_partida_quando_cabe():
    tabela = "| A | B |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |"
    md = f"## Dados\n\n{' '.join(['texto'] * 90)}\n\n{tabela}"

    chunks = chunk_markdown(md, max_words=100)

    com_tabela = [c for c in chunks if "| A | B |" in c.content]
    assert len(com_tabela) == 1
    assert "| 3 | 4 |" in com_tabela[0].content


def test_tabela_grande_partida_repete_o_cabecalho_em_cada_pedaco():
    linhas = "\n".join(
        f"| erro {n} | causa {n} com algumas palavras | corrija {n} assim |" for n in range(1, 16)
    )
    tabela = f"| Mensagem | Causa | O que fazer |\n| --- | --- | --- |\n{linhas}"

    chunks = chunk_markdown(f"## Erros\n\n{tabela}", max_words=40)

    assert len(chunks) > 1
    for chunk in chunks:
        primeiras = chunk.content.splitlines()[:2]
        assert primeiras == ["| Mensagem | Causa | O que fazer |", "| --- | --- | --- |"]
    juntos = "\n".join(c.content for c in chunks)
    assert all(f"| erro {n} |" in juntos for n in range(1, 16))


def test_bloco_de_codigo_fica_inteiro_e_titulo_dentro_dele_nao_conta():
    md = "## Comando\n\n```\n# isto é comentário, não título\nls -l\n```\n\nDepois."

    chunks = chunk_markdown(md)

    assert len(chunks) == 1
    assert "# isto é comentário" in chunks[0].content
    assert chunks[0].breadcrumb == "Comando"


def test_secao_vazia_nao_gera_trecho():
    chunks = chunk_markdown("## Vazia\n\n## Cheia\n\nTem texto.")

    assert [c.breadcrumb for c in chunks] == ["Cheia"]


def test_lista_gigante_e_partida_por_item_como_ultimo_recurso():
    itens = "\n".join(f"- item {n} " + "x " * 20 for n in range(1, 20))

    chunks = chunk_markdown(f"## Lista\n\n{itens}", max_words=60)

    assert len(chunks) > 1
    assert all(len(c.content.split()) <= 60 for c in chunks)
    juntos = "\n".join(c.content for c in chunks)
    assert all(f"- item {n} " in juntos for n in range(1, 20))


@pytest.mark.skipif(MANUAIS is None, reason="manuais fictícios só existem na máquina local")
def test_manuais_reais_geram_trechos_curtos_com_breadcrumb():
    assert MANUAIS is not None
    arquivos = sorted(MANUAIS.glob("[0-9]*.md"))
    assert len(arquivos) == 15

    for arquivo in arquivos:
        meta, body = split_front_matter(arquivo.read_text(encoding="utf-8"))
        chunks = chunk_markdown(body, title=meta["titulo"])

        assert chunks, arquivo.name
        assert all(c.breadcrumb.startswith(meta["titulo"]) for c in chunks), arquivo.name
        assert all(0 < len(c.content.split()) <= 110 for c in chunks), arquivo.name
