"""Grava o contrato da API. Uso: python -m h2d.export_openapi <arquivo>"""

import json
import os
import sys
from pathlib import Path

# O contrato não depende de ambiente: valores fixos permitem exportar sem banco nem .env.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://unused/unused")
os.environ.setdefault("JWT_SECRET", "usado-somente-para-exportar-o-contrato")
os.environ["ENVIRONMENT"] = "dev"

from h2d.main import app  # noqa: E402


def main() -> None:
    target = Path(sys.argv[1])
    target.write_text(
        json.dumps(app.openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
