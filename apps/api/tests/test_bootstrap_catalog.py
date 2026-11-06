import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.bootstrap_catalog import BootstrapError, bootstrap
from h2d.models import Category, Role, Skill, SlaPolicy, SlaTarget, Technician, TechnicianSkill


async def test_cria_o_catalogo_e_rodar_de_novo_nao_duplica(session: AsyncSession):
    primeira = await bootstrap(session, [])
    segunda = await bootstrap(session, [])

    assert primeira.skills == segunda.skills == 7
    assert primeira.categories == segunda.categories
    assert await session.scalar(select(func.count()).select_from(SlaPolicy)) == 1
    assert await session.scalar(select(func.count()).select_from(SlaTarget)) == 4
    assert (await session.scalar(select(func.count()).select_from(Category)) or 0) > 7
    assert primeira.technicians_added == []


async def test_tecnicos_informados_recebem_horario_comercial_e_todas_as_habilidades(
    session: AsyncSession, make_user
):
    tecnico = await make_user(email="tec@empresa.com", role=Role.TECH)
    admin = await make_user(email="admin@empresa.com", role=Role.ADMIN)

    resumo = await bootstrap(session, ["Tec@Empresa.com ", "admin@empresa.com"])
    repetido = await bootstrap(session, ["tec@empresa.com"])

    assert resumo.technicians_added == ["tec@empresa.com", "admin@empresa.com"]
    assert repetido.technicians_added == []
    tecnicos = list(await session.scalars(select(Technician)))
    assert {t.user_id for t in tecnicos} == {tecnico.id, admin.id}
    assert all("mon" in t.schedule for t in tecnicos)
    habilidades = await session.scalar(select(func.count()).select_from(TechnicianSkill))
    total = await session.scalar(select(func.count()).select_from(Skill))
    assert habilidades == 2 * (total or 0)


@pytest.mark.parametrize(
    ("email", "trecho"),
    [("ninguem@empresa.com", "Não existe usuário"), ("comum@empresa.com", "usuário comum")],
)
async def test_recusa_email_inexistente_ou_de_usuario_comum(
    session: AsyncSession, make_user, email, trecho
):
    await make_user(email="comum@empresa.com", role=Role.USER)

    with pytest.raises(BootstrapError, match=trecho):
        await bootstrap(session, [email])
