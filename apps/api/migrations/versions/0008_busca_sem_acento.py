"""busca por palavras sem acento: "usuario" passa a casar com "usuário" (somente aditiva)

O radical do Postgres muda com o acento ('usuari' x 'usuári'), e quem digita sem acento não achava
o trecho. O tsvector passa a ser calculado sobre o texto sem acentos, e a consulta também.
A coluna continua gerada: o Postgres recalcula os valores sozinho, sem perder dado.

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    # `unaccent` não é IMMUTABLE; coluna gerada exige função imutável, então vai num invólucro.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION h2d_unaccent(text) RETURNS text
        LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
        AS $$ SELECT public.unaccent('public.unaccent'::regdictionary, $1) $$
        """
    )
    op.execute(
        "ALTER TABLE kb_chunks ALTER COLUMN tsv SET EXPRESSION AS "
        "(to_tsvector('portuguese', h2d_unaccent(breadcrumb || ' ' || content)))"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE kb_chunks ALTER COLUMN tsv SET EXPRESSION AS "
        "(to_tsvector('portuguese', breadcrumb || ' ' || content))"
    )
    op.execute("DROP FUNCTION IF EXISTS h2d_unaccent(text)")
