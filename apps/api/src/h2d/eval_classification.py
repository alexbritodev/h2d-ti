"""Mede o classificador contra o conjunto rotulado (eval/classificacao_v0.jsonl).

Uso: python -m h2d.eval_classification [caminho.jsonl] [--skip N] [--limit N]
Chama o modelo de verdade (OPENROUTER_API_KEY), uma vez por conversa, então gasta a cota do dia:
use --limit para medir uma parte. As categorias vêm do catálogo do banco (rode o seed ou o
bootstrap antes). A prioridade comparada é a da matriz, igual à do sistema.
"""

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

from h2d.db import get_sessionmaker
from h2d.llm.client import LLMError, get_llm
from h2d.models import Category, Skill
from h2d.tickets import classify as clf
from h2d.tickets.rules import priority_from

DEFAULT_PATH = "eval/classificacao_v0.jsonl"
RANK = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}


async def _main(path: str, limit: int | None, skip: int = 0) -> None:
    text = await asyncio.to_thread(Path(path).read_text, encoding="utf-8")
    rows = [json.loads(line) for line in text.splitlines() if line]
    rows = rows[skip:]
    if limit:
        rows = rows[:limit]
    async with get_sessionmaker()() as session:
        categories = [
            clf.CategoryOption(c.id, c.name, c.parent_id, c.default_skill_id, c.sla_policy_id)
            for c in await session.scalars(select(Category).where(Category.is_active))
        ]
        skills = list(await session.scalars(select(Skill.name).order_by(Skill.name)))
    if not categories:
        raise SystemExit(
            "O banco não tem categorias. Rode o seed ou o bootstrap do catálogo antes."
        )

    llm = get_llm()
    ok_cat = ok_sub = ok_prio = near_prio = invalid = 0
    misses: list[str] = []
    for row in rows:
        messages = clf.build_messages(
            transcript=row["conversa"],
            categories=categories,
            skills=skills,
            department=None,
            vip=False,
        )
        try:
            result = await llm.complete(messages, temperature=0.0, max_tokens=600)
            got = clf.parse_classification(result.text)
        except (LLMError, ValueError) as error:
            invalid += 1
            misses.append(f"#{row['id']}: sem classificação ({str(error)[:80]})")
            continue
        want = row["esperado"]
        parent, child = clf.match_category(got, categories)
        cat_ok = parent is not None and clf.normalize(parent.name) == clf.normalize(
            want["categoria"]
        )
        sub_ok = child is not None and clf.normalize(child.name) == clf.normalize(
            want["subcategoria"]
        )
        want_prio = priority_from(clf.LEVELS[want["impacto"]], clf.LEVELS[want["urgencia"]]).value
        got_prio = priority_from(got.impacto, got.urgencia).value
        ok_cat += cat_ok
        ok_sub += sub_ok
        ok_prio += got_prio == want_prio
        near_prio += abs(RANK[got_prio] - RANK[want_prio]) <= 1
        if not (cat_ok and sub_ok and got_prio == want_prio):
            misses.append(
                f"#{row['id']}: esperado {want['categoria']} > {want['subcategoria']} "
                f"{want_prio}; veio {got.categoria} > {got.subcategoria} {got_prio} "
                f"(confiança {got.confianca:.2f})"
            )
    n = len(rows)
    print(f"Conversas avaliadas: {n} | sem classificação válida: {invalid}")
    print(f"Categoria certa: {ok_cat}/{n} ({100 * ok_cat / n:.0f}%)")
    print(f"Subcategoria certa: {ok_sub}/{n} ({100 * ok_sub / n:.0f}%)")
    print(
        f"Prioridade exata: {ok_prio}/{n} ({100 * ok_prio / n:.0f}%) | até 1 nível: {near_prio}/{n}"
    )
    for miss in misses:
        print(" -", miss)


def _option(name: str) -> int | None:
    if name not in sys.argv:
        return None
    return int(sys.argv[sys.argv.index(name) + 1])


if __name__ == "__main__":
    limit, skip = _option("--limit"), _option("--skip") or 0
    values = {str(v) for v in (limit, skip) if v is not None}
    args = [a for a in sys.argv[1:] if not a.startswith("--") and a not in values]
    asyncio.run(_main(args[0] if args else DEFAULT_PATH, limit, skip))
