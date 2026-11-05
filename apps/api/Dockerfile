FROM python:3.12-slim AS base
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir "uv>=0.11,<0.12"
WORKDIR /app
COPY pyproject.toml uv.lock ./

FROM base AS dev
# O pyright baixa um Node que depende desta biblioteca.
RUN apt-get update && apt-get install -y --no-install-recommends libatomic1 \
    && rm -rf /var/lib/apt/lists/*
COPY src ./src
RUN uv sync --frozen

# O uv só serve para instalar as dependências. A imagem final parte de uma base limpa e
# recebe só o ambiente pronto, sem o uv: menos superfície de ataque e imagem menor.
FROM base AS builder
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim AS prod
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY migrations ./migrations
COPY alembic.ini ./
RUN useradd --system --no-create-home h2d
USER h2d
CMD ["uvicorn", "h2d.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
