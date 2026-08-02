from typing import Protocol

from app.schemas.retrieval import RetrievedChunk


class Reranker(Protocol):
    async def rerank(self, query: str, items: list[RetrievedChunk]) -> list[RetrievedChunk]: ...
