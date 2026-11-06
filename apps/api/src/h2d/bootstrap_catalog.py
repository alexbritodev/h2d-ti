"""Catálogo de produção: habilidades, política de SLA e categorias, sem usuários de demonstração.

Uso: python -m h2d.bootstrap_catalog
Opcional: TECHNICIAN_EMAILS=ana@empresa.com,beto@empresa.com. Cada e-mail precisa ser de um usuário
que já existe (técnico ou administrador); ele passa a receber chamados, em horário comercial, com
todas as habilidades. Depois dá para ajustar caso a caso.

Só cria o que falta: rodar de novo não altera nem apaga nada. Sem técnicos, todo chamado cai na
triagem manual (funciona, mas ninguém recebe a atribuição automática).
"""

import asyncio
import os
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.db import get_sessionmaker
from h2d.models import Category, Role, Technician, User
from h2d.seed import (
    _BUSINESS_HOURS,  # pyright: ignore[reportPrivateUsage]
    _seed_categories,  # pyright: ignore[reportPrivateUsage]
    _seed_skills,  # pyright: ignore[reportPrivateUsage]
    _seed_sla_policy,  # pyright: ignore[reportPrivateUsage]
)


class BootstrapError(RuntimeError):
    pass


@dataclass(frozen=True)
class Summary:
    skills: int
    categories: int
    technicians_added: list[str]


async def bootstrap(session: AsyncSession, technician_emails: list[str]) -> Summary:
    skills = await _seed_skills(session)
    policy = await _seed_sla_policy(session)
    await _seed_categories(session, skills, policy)

    added: list[str] = []
    existing = set(await session.scalars(select(Technician.user_id)))
    for raw in technician_emails:
        email = raw.strip().lower()
        if not email:
            continue
        user = await session.scalar(select(User).where(User.email == email))
        if user is None:
            raise BootstrapError(f"Não existe usuário com o e-mail {email}")
        if user.role is Role.USER:
            raise BootstrapError(f"{email} é usuário comum: mude o papel para técnico antes")
        if user.id in existing:
            continue
        session.add(
            Technician(user_id=user.id, schedule=_BUSINESS_HOURS, skills=list(skills.values()))
        )
        existing.add(user.id)
        added.append(email)
    await session.flush()

    categories = len(list(await session.scalars(select(Category.id))))
    return Summary(len(skills), categories, added)


async def _main() -> None:
    emails = os.environ.get("TECHNICIAN_EMAILS", "").split(",")
    async with get_sessionmaker()() as session, session.begin():
        summary = await bootstrap(session, emails)
    print(f"Habilidades: {summary.skills}. Categorias (com subcategorias): {summary.categories}.")
    print(f"Técnicos adicionados: {', '.join(summary.technicians_added) or 'nenhum'}.")
    print(f"Técnicos cadastrados no total: {await _count_technicians()}.")


async def _count_technicians() -> int:
    async with get_sessionmaker()() as session:
        return len(list(await session.scalars(select(Technician.id))))


if __name__ == "__main__":
    asyncio.run(_main())
