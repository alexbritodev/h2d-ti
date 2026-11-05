"""Modelo de embeddings (ADR-003): MiniLM multilíngue, local, 384 dimensões.

Em produção usa o FastEmbed (ONNX em CPU). Nos testes entra o `FakeEmbedder`, que não baixa nada e
mantém a proximidade entre textos que compartilham palavras, o bastante para testar a busca.
"""

import asyncio
import hashlib
import math
import re
from functools import lru_cache
from typing import Any, Protocol

from h2d.config import get_settings
from h2d.models import EMBEDDING_DIM, EMBEDDING_MODEL

BATCH_SIZE = 32


class Embedder(Protocol):
    model_name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedder:
    """Carrega o modelo na primeira chamada: subir a API não custa memória até alguém buscar."""

    model_name = EMBEDDING_MODEL

    def __init__(self, cache_dir: str) -> None:
        self._cache_dir = cache_dir
        self._model: Any = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(self.model_name, cache_dir=self._cache_dir)
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
