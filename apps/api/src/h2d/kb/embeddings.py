"""Modelo de embeddings (ADR-003): MiniLM multilíngue, local, 384 dimensões.

Em produção usa o FastEmbed (ONNX em CPU). Nos testes entra o `FakeEmbedder`, que não baixa nada e
mantém a proximidade entre textos que compartilham palavras, o bastante para testar a busca.
"""

import asyncio
import hashlib
import logging
import math
import re
import time
from collections.abc import Callable
from functools import lru_cache
from typing import Any, Protocol

from h2d.config import get_settings
from h2d.models import EMBEDDING_DIM, EMBEDDING_MODEL

BATCH_SIZE = 32
LOAD_ATTEMPTS = 4
LOAD_WAIT_SECONDS = 20.0

log = logging.getLogger("h2d.embeddings")


class Embedder(Protocol):
    model_name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedder:
    """Carrega o modelo na primeira chamada: subir a API não custa memória até alguém buscar."""

    model_name = EMBEDDING_MODEL

    def __init__(
        self,
        cache_dir: str,
        *,
        loader: Callable[[str, str], Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._cache_dir = cache_dir
        self._model: Any = None
        self._loader = loader or self._load_fastembed
        self._sleep = sleep

    @staticmethod
    def _load_fastembed(name: str, cache_dir: str) -> Any:
        from fastembed import TextEmbedding

        return TextEmbedding(name, cache_dir=cache_dir)

    def _load(self) -> Any:
        """Baixa e carrega o modelo. O Hugging Face limita pedidos sem login (erro 429), então
        tenta algumas vezes, com espera crescente, antes de desistir."""
        last: Exception | None = None
        for attempt in range(1, LOAD_ATTEMPTS + 1):
            try:
                return self._loader(self.model_name, self._cache_dir)
            except Exception as error:  # download e leitura do modelo levantam tipos variados
                last = error
                log.warning("modelo de embeddings: tentativa %d falhou: %s", attempt, error)
                if attempt < LOAD_ATTEMPTS:
                    self._sleep(LOAD_WAIT_SECONDS * attempt)
        raise RuntimeError(f"Não foi possível carregar o modelo de embeddings: {last}") from last

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            self._model = self._load()
        vectors = self._model.embed(texts, batch_size=BATCH_SIZE)
        return [[float(x) for x in vector] for vector in vectors]


class FakeEmbedder:
    """Saco de palavras com hash: textos com palavras em comum ficam próximos. Só para testes."""

    model_name = EMBEDDING_MODEL

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(text) for text in texts]

    @staticmethod
    def _one(text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIM
        for word in re.findall(r"\w+", text.lower()):
            digest = hashlib.sha256(word.encode()).digest()
            vector[int.from_bytes(digest[:4], "big") % EMBEDDING_DIM] += 1.0
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [x / norm for x in vector]


@lru_cache
def get_embedder() -> Embedder:
    return FastEmbedder(get_settings().fastembed_cache_dir)


async def embed_async(embedder: Embedder, texts: list[str]) -> list[list[float]]:
    """O modelo é síncrono e pesado: roda fora do laço de eventos para não travar a API."""
    return await asyncio.to_thread(embedder.embed, texts)
