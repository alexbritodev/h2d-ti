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

FROM base AS prod
ENV ENVIRONMENT=production
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
RUN uv sync --frozen --no-dev --no-editable
RUN useradd --system --no-create-home h2d
USER h2d
CMD ["uvicorn", "h2d.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
