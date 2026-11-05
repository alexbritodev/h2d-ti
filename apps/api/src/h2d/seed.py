"""Dados de demonstração. Uso: python -m h2d.seed

Só cria o que falta: nunca altera nem apaga registros que já existem.
Os prazos de SLA são provisórios, até serem definidos com o time de TI.
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.config import get_settings
from h2d.db import get_sessionmaker
from h2d.models import Category, Priority, Role, Skill, SlaPolicy, SlaTarget, Technician, User
from h2d.security import hash_password

SKILLS = [
    "redes-vpn",
    "identidade-acesso",
    "email-colaboracao",
    "impressoras",
    "hardware",
    "sistemas-internos",
    "seguranca",
]

# prioridade: (1ª resposta, resolução), em minutos
SLA_TARGETS = {
    Priority.P1: (30, 240),
    Priority.P2: (60, 480),
    Priority.P3: (240, 1440),
    Priority.P4: (480, 4320),
}

# categoria: (habilidade padrão, subcategorias)
CATEGORIES = {
    "Rede e VPN": ("redes-vpn", ["VPN", "Wi-Fi", "Internet"]),
    "Acessos e senhas": ("identidade-acesso", ["Redefinição de senha", "Acesso a sistemas"]),
    "E-mail e colaboração": ("email-colaboracao", ["E-mail", "Calendário", "Videoconferência"]),
    "Impressão": ("impressoras", ["Impressora", "Digitalização"]),
    "Equipamentos": ("hardware", ["Notebook", "Periféricos"]),
    "Sistemas internos": ("sistemas-internos", ["Erro em sistema", "Dúvida de uso"]),
    "Segurança": ("seguranca", ["Phishing", "Incidente de segurança"]),
}

# (nome, e-mail, papel, setor, VIP)
USERS = [
    ("Ana Admin", "admin@h2d.local", Role.ADMIN, "TI", False),
    ("Túlio Técnico", "tecnico1@h2d.local", Role.TECH, "TI", False),
    ("Rita Redes", "tecnico2@h2d.local", Role.TECH, "TI", False),
    ("Sérgio Suporte", "tecnico3@h2d.local", Role.TECH, "TI", False),
    ("Fátima Financeiro", "usuario1@h2d.local", Role.USER, "Financeiro", False),
    ("Marcos Marketing", "usuario2@h2d.local", Role.USER, "Marketing", False),
    ("Diana Diretoria", "usuario3@h2d.local", Role.USER, "Diretoria", True),
]

# e-mail: habilidades
TECHNICIANS = {
    "tecnico1@h2d.local": ["identidade-acesso", "email-colaboracao", "sistemas-internos"],
    "tecnico2@h2d.local": ["redes-vpn", "seguranca"],
    "tecnico3@h2d.local": ["impressoras", "hardware", "email-colaboracao"],
}

_BUSINESS_HOURS = {day: ["08:00", "18:00"] for day in ("mon", "tue", "wed", "thu", "fri")}


class SeedNotAllowedError(RuntimeError):
    pass


async def _seed_skills(session: AsyncSession) -> dict[str, Skill]:
    skills = {skill.name: skill for skill in await session.scalars(select(Skill))}
    for name in SKILLS:
        if name not in skills:
            skills[name] = Skill(name=name)
            session.add(skills[name])
    await session.flush()
    return skills


async def _seed_sla_policy(session: AsyncSession) -> SlaPolicy:
    policy = await session.scalar(select(SlaPolicy).where(SlaPolicy.name == "Padrão"))
    if policy is None:
        policy = SlaPolicy(
            name="Padrão",
            targets=[
                SlaTarget(priority=priority, first_response_minutes=first, resolution_minutes=total)
                for priority, (first, total) in SLA_TARGETS.items()
            ],
        )
        session.add(policy)
        await session.flush()
    return policy


async def _seed_categories(
    session: AsyncSession, skills: dict[str, Skill], policy: SlaPolicy
) -> None:
    existing = {
        (category.parent_id, category.name): category
        for category in await session.scalars(select(Category))
    }

    async def ensure(name: str, skill: Skill, parent: Category | None) -> Category:
        parent_id = parent.id if parent else None
        category = existing.get((parent_id, name))
        if category is None:
            category = Category(
                name=name,
                parent_id=parent_id,
                default_skill_id=skill.id,
                sla_policy_id=policy.id,
            )
            session.add(category)
            await session.flush()
        return category

    for name, (skill_name, children) in CATEGORIES.items():
        skill = skills[skill_name]
        root = await ensure(name, skill, None)
        for child in children:
            await ensure(child, skill, root)


async def _seed_users(session: AsyncSession, password: str) -> dict[str, User]:
    users = {user.email: user for user in await session.scalars(select(User))}
    # O mesmo hash para todos: o argon2 é lento de propósito e isto é só para demonstração.
    password_hash = hash_password(password)
    for name, email, role, department, is_vip in USERS:
        if email not in users:
            users[email] = User(
                name=name,
                email=email,
                password_hash=password_hash,
                role=role,
                department=department,
                is_vip=is_vip,
            )
            session.add(users[email])
    await session.flush()
    return users


async def _seed_technicians(
    session: AsyncSession, users: dict[str, User], skills: dict[str, Skill]
) -> None:
    existing = set(await session.scalars(select(Technician.user_id)))
    for email, skill_names in TECHNICIANS.items():
        user = users[email]
        if user.id not in existing:
            session.add(
                Technician(
                    user_id=user.id,
                    schedule=_BUSINESS_HOURS,
                    skills=[skills[name] for name in skill_names],
                )
            )
    await session.flush()


async def run_seed(session: AsyncSession) -> None:
    settings = get_settings()
    if settings.environment == "production":
        raise SeedNotAllowedError("O seed não roda em produção")
    if settings.seed_password is None or not settings.seed_password.get_secret_value():
        raise SeedNotAllowedError("Defina SEED_PASSWORD no .env")

    skills = await _seed_skills(session)
    policy = await _seed_sla_policy(session)
    await _seed_categories(session, skills, policy)
    users = await _seed_users(session, settings.seed_password.get_secret_value())
    await _seed_technicians(session, users, skills)


async def _main() -> None:
    async with get_sessionmaker()() as session, session.begin():
        await run_seed(session)
    print("Seed concluído.")


if __name__ == "__main__":
    asyncio.run(_main())
