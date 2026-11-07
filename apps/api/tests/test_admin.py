from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.models import (
    AppSetting,
    AuditLog,
    Category,
    Priority,
    PromptVersion,
    Role,
    SlaPolicy,
    SlaTarget,
)
from tests.conftest import PASSWORD


async def _login(client, make_user, role: Role, email: str = "chefe@h2d.local"):
    user = await make_user(email=email, role=role)
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    return user


async def test_so_admin_le_o_painel(client, make_user):
    await _login(client, make_user, Role.TECH, "tec@h2d.local")
    for path in ("audit", "categories", "sla", "prompts", "settings"):
        assert (await client.get(f"/api/admin/{path}")).status_code == 403


async def test_auditoria_vem_do_banco_com_ator_e_rotulo(client, make_user, session: AsyncSession):
    admin = await _login(client, make_user, Role.ADMIN)
    session.add(
        AuditLog(
            actor_id=admin.id,
            action="user.update",
            entity_type="user",
            entity_id="123",
            before={"email": "a@h2d.local", "is_active": True},
            after={"email": "a@h2d.local", "is_active": False},
        )
    )
    await session.flush()

    response = await client.get("/api/admin/audit")

    assert response.status_code == 200
    entry = next(e for e in response.json() if e["action"] == "user.update")
    assert entry["actor_name"] == admin.name
    assert entry["entity_label"] == "a@h2d.local"
    assert entry["before"]["is_active"] is True and entry["after"]["is_active"] is False


async def test_categorias_contam_subcategorias(client, make_user, session: AsyncSession):
    await _login(client, make_user, Role.ADMIN)
    pai = Category(name="Rede e VPN")
    session.add(pai)
    await session.flush()
    session.add(Category(name="VPN", parent_id=pai.id))
    await session.flush()

    rows = (await client.get("/api/admin/categories")).json()

    by_name = {r["name"]: r for r in rows}
    assert by_name["Rede e VPN"]["children"] == 1
    assert by_name["VPN"]["parent_name"] == "Rede e VPN"


async def test_sla_lista_prazos_por_prioridade(client, make_user, session: AsyncSession):
    await _login(client, make_user, Role.ADMIN)
    policy = SlaPolicy(name="Padrão")
    session.add(policy)
    await session.flush()
    session.add_all(
        [
            SlaTarget(
                policy_id=policy.id,
                priority=Priority.P2,
                first_response_minutes=60,
                resolution_minutes=480,
            ),
            SlaTarget(
                policy_id=policy.id,
                priority=Priority.P1,
                first_response_minutes=30,
                resolution_minutes=240,
            ),
        ]
    )
    await session.flush()

    rows = (await client.get("/api/admin/sla")).json()

    assert [r["priority"] for r in rows] == ["P1", "P2"]
    assert rows[0]["resolution_minutes"] == 240


async def test_prompts_listam_versoes(client, make_user, session: AsyncSession):
    await _login(client, make_user, Role.ADMIN)
    session.add_all(
        [
            PromptVersion(name="atendimento", version=1, content="a"),
            PromptVersion(name="atendimento", version=2, content="b", is_active=True),
        ]
    )
    await session.flush()

    rows = (await client.get("/api/admin/prompts")).json()

    assert [(r["version"], r["is_active"]) for r in rows] == [(2, True), (1, False)]


async def test_limiar_padrao_e_salvar_audita(client, make_user, session: AsyncSession):
    admin = await _login(client, make_user, Role.ADMIN)
    assert (await client.get("/api/admin/settings")).json() == {"confidence_threshold": 0.6}

    response = await client.put("/api/admin/settings", json={"confidence_threshold": 0.75})

    assert response.status_code == 200
    assert (await client.get("/api/admin/settings")).json() == {"confidence_threshold": 0.75}
    row = await session.get(AppSetting, "classification_confidence_threshold")
    assert row is not None and row.value == 0.75
    log = await session.scalar(select(AuditLog).where(AuditLog.action == "settings.update"))
    assert log is not None and log.actor_id == admin.id
    assert log.before is None and log.after == {"confidence_threshold": 0.75}


async def test_limiar_fora_de_0_a_1_e_recusado(client, make_user):
    await _login(client, make_user, Role.ADMIN)
    assert (
        await client.put("/api/admin/settings", json={"confidence_threshold": 1.5})
    ).status_code == 422
