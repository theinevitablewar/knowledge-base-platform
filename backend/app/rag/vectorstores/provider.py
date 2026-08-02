import asyncio
from typing import Any, Protocol
from uuid import UUID

from langchain_qdrant import QdrantVectorStore
from qdrant_client import AsyncQdrantClient, QdrantClient, models

from app.core.config import Settings
from app.core.exceptions import VectorStoreError


class VectorRecord(Protocol):
    id: UUID
    content: str
    metadata_json: dict[str, Any]
    vector_id: str


class VectorStoreProvider(Protocol):
    async def ensure_collection(self, dimension: int) -> None: ...
    async def add_chunks(
        self, chunks: list[VectorRecord], vectors: list[list[float]], payloads: list[dict[str, Any]]
    ) -> None: ...
    async def delete_document(self, tenant_id: UUID, document_id: UUID) -> None: ...
    async def delete_chunk(self, tenant_id: UUID, chunk_id: UUID) -> None: ...
    async def delete_ids(self, vector_ids: list[str]) -> None: ...
    async def search(
        self, vector: list[float], security_filter: dict[str, Any], top_k: int
    ) -> list[tuple[str, float, dict[str, Any]]]: ...
    async def collection_status(self) -> dict[str, Any]: ...


class QdrantVectorStoreProvider:
    def __init__(self, settings: Settings) -> None:
        self.collection = f"{settings.qdrant_collection_prefix}_chunks"
        self.client = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
        sync_client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
        self.langchain_store = QdrantVectorStore(
            client=sync_client,
            collection_name=self.collection,
            embedding=None,
            validate_embeddings=False,
            validate_collection_config=False,
        )

    async def ensure_collection(self, dimension: int) -> None:
        if not await self.client.collection_exists(self.collection):
            await self.client.create_collection(
                self.collection,
                vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
            )

    async def add_chunks(
        self, chunks: list[VectorRecord], vectors: list[list[float]], payloads: list[dict[str, Any]]
    ) -> None:
        if not chunks:
            return
        try:
            await self.ensure_collection(len(vectors[0]))
            enriched_payloads = [
                {**payload, "page_content": chunk.content, "metadata": payload}
                for chunk, payload in zip(chunks, payloads, strict=True)
            ]
            await self.client.upsert(
                self.collection,
                points=[
                    models.PointStruct(id=chunk.vector_id, vector=vector, payload=payload)
                    for chunk, vector, payload in zip(chunks, vectors, enriched_payloads, strict=True)
                ],
                wait=True,
            )
        except Exception as exc:
            raise VectorStoreError("向量写入失败") from exc

    @staticmethod
    def _filter(values: dict[str, Any]) -> models.Filter:
        must: list[models.FieldCondition] = []
        for key, value in values.items():
            match = models.MatchAny(any=value) if isinstance(value, list) else models.MatchValue(value=value)
            must.append(models.FieldCondition(key=key, match=match))
        return models.Filter(must=must)

    async def delete_document(self, tenant_id: UUID, document_id: UUID) -> None:
        if not await self.client.collection_exists(self.collection):
            return
        await self.client.delete(
            self.collection,
            points_selector=models.FilterSelector(
                filter=self._filter(
                    {
                        "tenant_id": str(tenant_id),
                        "document_id": str(document_id),
                    }
                )
            ),
            wait=True,
        )

    async def delete_chunk(self, tenant_id: UUID, chunk_id: UUID) -> None:
        if not await self.client.collection_exists(self.collection):
            return
        await self.client.delete(
            self.collection,
            points_selector=models.FilterSelector(
                filter=self._filter(
                    {
                        "tenant_id": str(tenant_id),
                        "chunk_id": str(chunk_id),
                    }
                )
            ),
            wait=True,
        )

    async def delete_ids(self, vector_ids: list[str]) -> None:
        if vector_ids and await self.client.collection_exists(self.collection):
            await self.client.delete(
                self.collection,
                points_selector=models.PointIdsList(points=vector_ids),
                wait=True,
            )

    async def search(
        self, vector: list[float], security_filter: dict[str, Any], top_k: int
    ) -> list[tuple[str, float, dict[str, Any]]]:
        try:
            if not await self.client.collection_exists(self.collection):
                return []
            result = await asyncio.to_thread(
                self.langchain_store.similarity_search_with_score_by_vector,
                vector,
                top_k,
                self._filter(security_filter),
            )
            return [
                (str(document.metadata["_id"]), float(score), document.metadata) for document, score in result
            ]
        except Exception as exc:
            raise VectorStoreError("向量检索失败") from exc

    async def collection_status(self) -> dict[str, Any]:
        exists = await self.client.collection_exists(self.collection)
        if not exists:
            return {"exists": False, "name": self.collection}
        info = await self.client.get_collection(self.collection)
        return {
            "exists": True,
            "name": self.collection,
            "points_count": info.points_count,
            "status": str(info.status),
        }
