import hashlib
import math
from typing import Protocol

from langchain_openai import OpenAIEmbeddings

from app.core.config import Settings


class EmbeddingsAdapter(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...


class DeterministicEmbeddings:
    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in text.casefold().split():
            digest = hashlib.sha256(token.encode()).digest()
            vector[int.from_bytes(digest[:4], "big") % self.dimension] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class OpenAIEmbeddingsAdapter:
    def __init__(self, settings: Settings, dimension: int) -> None:
        self.client = OpenAIEmbeddings(  # type: ignore[call-arg]
            model=settings.embedding_model,
            dimensions=dimension,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
            check_embedding_ctx_length=False,
        )

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self.client.aembed_documents(texts)

    async def embed_query(self, text: str) -> list[float]:
        return await self.client.aembed_query(text)


def embedding_provider(settings: Settings, dimension: int | None = None) -> EmbeddingsAdapter:
    if settings.ai_mock_mode or not settings.openai_api_key:
        return DeterministicEmbeddings(dimension or 384)
    return OpenAIEmbeddingsAdapter(settings, dimension or settings.embedding_dimension)
