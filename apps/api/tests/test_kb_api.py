import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.kb.embeddings import FakeEmbedder
from h2d.kb.ingest import claim_next_job, process_job
from h2d.models import Role
from tests.conftest import PASSWORD

VPN = (
    b"---\ntitulo: VPN corporativa\ncategoria: Redes\nvisibilidade: publico\n---\n\n"
    b"## Sessao\n\nA sessao da VPN dura 12 horas.\n"
)
SEG = (
    b"---\ntitulo: Resposta a incidentes\ncategoria: Seguranca\nvisibilidade: ti\n---\n\n"
    b"## Prazos\n\nO prazo para incidente critico e de 15 minutos.\n"
)


async def _login(client, make_user, role: Role, email="pessoa@h2d.local"):
    user = await make_user(email=email, role=role)
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    return user


async def _upload(client, name: str, data: bytes, **form):
    return await client.post(
        "/api/kb/documents", files={"file": (name, data, "text/markdown")}, data=form
    )


async def _process_all(session: AsyncSession) -> None:
    await session.commit()
    while (job := await claim_next_job(session)) is not None:
        await process_job(session, job, FakeEmbedder())
        await session.commit()


@pytest.mark.parametrize("role", [Role.USER, Role.TECH])
async def test_so_admin_envia_e_acompanha_ingestao(client, make_user, role):
    await _login(client, make_user, role)

    assert (await _upload(client, "vpn.md", VPN)).status_code == 403
    assert (await client.get("/api/kb/documents")).status_code == 403
    assert (await client.get("/api/kb/jobs")).status_code == 403


async def test_sem_login_nada_funciona(client):
    assert (await client.get("/api/kb/search", params={"q": "vpn"})).status_code == 401
    assert (await client.get("/api/kb/library")).status_code == 401


async def test_admin_envia_arquivo_e_ve_o_job_na_lista(client, make_user, session):
    await _login(client, make_user, Role.ADMIN)

    response = await _upload(client, "vpn.md", VPN)

    assert response.status_code == 201
    body = response.json()
    assert body["duplicate"] is False and body["job_id"]
    jobs = (await client.get("/api/kb/jobs")).json()
    assert jobs[0]["state"] == "queued" and jobs[0]["filename"] == "vpn.md"
    docs = (await client.get("/api/kb/documents")).json()
    assert docs[0]["title"] == "VPN corporativa"
    assert docs[0]["version_status"] == "processing"

    await _process_all(session)

    docs = (await client.get("/api/kb/documents")).json()
    assert docs[0]["version_status"] == "active"
    assert (await client.get("/api/kb/jobs")).json()[0]["state"] == "succeeded"


async def test_reenvio_do_mesmo_arquivo_nao_cria_job(client, make_user):
    await _login(client, make_user, Role.ADMIN)
    first = (await _upload(client, "vpn.md", VPN)).json()

    again = (await _upload(client, "outro-nome.md", VPN)).json()

    assert again["duplicate"] is True
    assert again["job_id"] is None
    assert again["version_id"] == first["version_id"]
    assert len((await client.get("/api/kb/jobs")).json()) == 1


@pytest.mark.parametrize(
    ("nome", "dados"), [("manual.exe", b"MZ"), ("falso.pdf", b"texto"), ("vazio.md", b"")]
)
async def test_arquivo_invalido_recebe_422_com_motivo(client, make_user, nome, dados):
    await _login(client, make_user, Role.ADMIN)

    response = await _upload(client, nome, dados)

    assert response.status_code == 422
    assert response.json()["detail"]


async def test_busca_respeita_o_papel_de_quem_pergunta(client, make_user, session):
    await _login(client, make_user, Role.ADMIN, "admin@h2d.local")
    await _upload(client, "vpn.md", VPN)
    await _upload(client, "seg.md", SEG)
    await _process_all(session)
    pergunta = {"q": "prazo para incidente critico 15 minutos"}

    como_admin = (await client.get("/api/kb/search", params=pergunta)).json()
    client.cookies.clear()
    await _login(client, make_user, Role.USER, "comum@h2d.local")
    como_usuario = (await client.get("/api/kb/search", params=pergunta)).json()

    assert any("15 minutos" in h["content"] for h in como_admin)
    assert all(h["document_title"] != "Resposta a incidentes" for h in como_usuario)
    assert all("15 minutos" not in h["content"] for h in como_usuario)


async def test_trecho_restrito_responde_404_para_usuario_comum(client, make_user, session):
    await _login(client, make_user, Role.ADMIN, "admin@h2d.local")
    await _upload(client, "seg.md", SEG)
    await _process_all(session)
    hit = (await client.get("/api/kb/search", params={"q": "incidente critico"})).json()[0]
    assert (await client.get(f"/api/kb/chunks/{hit['chunk_id']}")).status_code == 200

    client.cookies.clear()
    await _login(client, make_user, Role.USER, "comum@h2d.local")

    assert (await client.get(f"/api/kb/chunks/{hit['chunk_id']}")).status_code == 404


async def test_biblioteca_lista_so_o_que_a_pessoa_pode_ver(client, make_user, session):
    await _login(client, make_user, Role.ADMIN, "admin@h2d.local")
    await _upload(client, "vpn.md", VPN)
    await _upload(client, "seg.md", SEG)
    await _process_all(session)
    admin = {d["title"] for d in (await client.get("/api/kb/library")).json()}
    client.cookies.clear()
    await _login(client, make_user, Role.USER, "comum@h2d.local")

    usuario = {d["title"] for d in (await client.get("/api/kb/library")).json()}

    assert admin == {"VPN corporativa", "Resposta a incidentes"}
    assert usuario == {"VPN corporativa"}


async def test_admin_muda_visibilidade_e_o_trecho_some_para_o_usuario(client, make_user, session):
    await _login(client, make_user, Role.ADMIN, "admin@h2d.local")
    doc = (await _upload(client, "vpn.md", VPN)).json()["document_id"]
    await _process_all(session)

    response = await client.patch(f"/api/kb/documents/{doc}", json={"visibility": "it"})

    assert response.status_code == 200
    assert response.json()["visibility"] == "it"
    client.cookies.clear()
    await _login(client, make_user, Role.USER, "comum@h2d.local")
    assert (await client.get("/api/kb/search", params={"q": "sessao da VPN"})).json() == []


async def test_reindexar_cria_novo_job(client, make_user):
    await _login(client, make_user, Role.ADMIN)
    doc = (await _upload(client, "vpn.md", VPN)).json()["document_id"]

    response = await client.post(f"/api/kb/documents/{doc}/reindex")

    assert response.status_code == 202
    assert len((await client.get("/api/kb/jobs")).json()) == 2


async def test_documento_publicado_abre_em_secoes_e_o_restrito_some_para_o_usuario(
    client, make_user, session
):
    await _login(client, make_user, Role.ADMIN, "admin@h2d.local")
    vpn = (await _upload(client, "vpn.md", VPN)).json()["document_id"]
    seg = (await _upload(client, "seg.md", SEG)).json()["document_id"]
    await _process_all(session)

    visto_pelo_admin = (await client.get(f"/api/kb/library/{seg}")).json()
    client.cookies.clear()
    await _login(client, make_user, Role.USER, "comum@h2d.local")
    publico = await client.get(f"/api/kb/library/{vpn}")
    restrito = await client.get(f"/api/kb/library/{seg}")

    assert "15 minutos" in visto_pelo_admin["sections"][0]["content"]
    assert publico.status_code == 200 and publico.json()["sections"]
    assert restrito.status_code == 404
