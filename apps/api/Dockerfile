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
RUN useradd --system --no-create-home h2d     && mkdir -p /data/uploads /models     && chown -R h2d /data /models
USER h2d
# O modelo de embeddings (ADR-003) tenta vir baixado na imagem: a primeira busca não espera. O
# Hugging Face limita pedidos sem login (erro 429) e isso já derrubou um deploy; por isso são
# várias tentativas com espera e a falha NÃO quebra o build. Sem o modelo na imagem, ele é baixado
# na primeira execução e fica guardado no volume h2d_models (ver docker-compose.yml).
RUN for tentativa in 1 2 3 4 5; do \
      python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', cache_dir='/models')" && exit 0; \
      echo "Download do modelo falhou (tentativa $tentativa de 5)"; sleep $((tentativa * 30)); \
    done; \
    echo "AVISO: modelo nao baixado no build; sera baixado no primeiro uso."; exit 0
# Um processo só: o modelo fica carregado uma vez (memória). O worker roda em outro container.
CMD ["uvicorn", "h2d.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
