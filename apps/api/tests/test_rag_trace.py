import uuid

import pytest

from h2d.chat.service import SEARCH_LIMIT
from h2d.kb.embeddings import FakeEmbedder
from h2d.kb.rag_trace import parse_tsvector, parse_vector
from h2d.kb.search import search_chunks
from h2d.models import Role
from tests.test_chat import SEGURANCA, VPN, _base, _login


def test_le_o_tsvector_do_postgres():
    assert parse_tsvector("'conect':1,4 'vpn':2 'it''s':3") == [
        ("conect", 2),
        ("it's", 1),
        ("vpn", 1),
    ]
    assert parse_tsvector("") == []


def test_le_o_vetor_do_pgvector():
    assert parse_vector("[0.5,-0.25,1]") == [0.5, -0.25, 1.0]


@pytest.mark.parametrize("role", [Role.USER, Role.TECH])
async def test_so_admin_usa_o_painel_do_rag(client, make_user, role):
    await _login(client, make_user, role=role, email=f"{role.value}@h2d.local")
    assert (await client.get("/api/admin/rag/overview")).status_code == 403
    assert (await client.post("/api/admin/rag/trace", json={"question": "vpn"})).status_code == 403
    assert (await client.get(f"/api/admin/rag/chunks/{uuid.uuid4()}")).status_code == 403


async def test_rastreio_mostra_cada_etapa_e_escolhe_os_mesmos_trechos_da_busca(
    client, make_user, session, tmp_path
):
    await _base(session, tmp_path, VPN, SEGURANCA)
    await _login(client, make_user, role=Role.ADMIN, email="admin@h2d.local")
    pergunta = "quanto tempo dura a sessão da VPN? minha senha é Xk9#mP2vLq8z"

    response = await client.post("/api/admin/rag/trace", json={"question": pergunta})

    assert response.status_code == 200
    data = response.json()
    assert "Xk9#mP2vLq8z" not in response.text
    assert data["masking"]["redactions"] == 1 and data["masking"]["kinds"]
    words = {w["word"]: w["lexeme"] for w in data["tokenization"]["words"]}
    assert words["vpn"] == "vpn" and words["sessão"] == "sessão" or words["sessão"]
    assert words["da"] is None  # palavra vazia: sai da busca por palavras
    assert data["tokenization"]["model_token_count"] == len(data["tokenization"]["model_tokens"])
    assert data["embedding"]["dimensions"] == 384
    assert len(data["embedding"]["values"]) == 384
    assert data["vector"] and data["lexical"]
    assert data["vector"][0]["rank"] == 1 and data["lexical"][0]["rank"] == 1
    assert [t["stage"] for t in data["timings"]] == [
        "masking", "tokenization", "embedding", "search", "fusion", "prompt",
    ]  # fmt: skip
    assert data["prompt"]["sources_block"].startswith("<fontes>")
    assert data["generation"]["calls_today"] == 0  # o rastreio não chama o modelo

    # Os trechos escolhidos são os mesmos que a busca de verdade devolve.
    escolhidos = {row["chunk_id"] for row in data["fusion"] if row["selected"]}
    reais = await search_chunks(
        session, data["masking"]["masked_text"], FakeEmbedder(), can_see_it=True, limit=SEARCH_LIMIT
    )
    assert escolhidos == {str(hit.chunk_id) for hit in reais}
    top = data["fusion"][0]
    assert top["score"] == pytest.approx(top["vector_part"] + top["lexical_part"], abs=1e-4)


async def test_anatomia_do_trecho_e_visao_geral(client, make_user, session, tmp_path):
    await _base(session, tmp_path, VPN)
    await _login(client, make_user, role=Role.ADMIN, email="admin@h2d.local")
    trace = (await client.post("/api/admin/rag/trace", json={"question": "sessão da VPN"})).json()
    chunk_id = trace["fusion"][0]["chunk_id"]

    anatomy = await client.get(f"/api/admin/rag/chunks/{chunk_id}")

    assert anatomy.status_code == 200
    body = anatomy.json()
    assert body["title"] == "VPN corporativa" and body["content"]
    assert body["token_count"] == len(body["tokens"]) > 0
    assert any(item["lexeme"] == "vpn" for item in body["lexemes"])
    assert body["embedding"]["dimensions"] == 384
    assert body["truncated"] is False
    assert (await client.get(f"/api/admin/rag/chunks/{uuid.uuid4()}")).status_code == 404

    overview = (await client.get("/api/admin/rag/overview")).json()
    assert overview["documents"] == 1 and overview["chunks"] >= 1
    assert overview["params"]["embedding_dimensions"] == 384
    assert overview["public_chunks"] + overview["restricted_chunks"] == overview["chunks"]


async def test_pergunta_sem_trecho_devolve_listas_vazias(client, make_user, session, tmp_path):
    await _login(client, make_user, role=Role.ADMIN, email="admin@h2d.local")

    data = (await client.post("/api/admin/rag/trace", json={"question": "vpn"})).json()

    assert data["vector"] == [] and data["lexical"] == [] and data["fusion"] == []
    assert data["prompt"]["sources_block"] == ""
