import time
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedError
from app.core.security import Principal
from app.models import Document, DocumentChunk
from app.permissions import PermissionService
from app.rag.embeddings.providers import EmbeddingsAdapter
from app.rag.retrievers.bm25 import BM25IndexCache
from app.rag.vectorstores import VectorStoreProvider
from app.schemas.retrieval import RetrievedChunk, SearchResponse


class SecureRetriever:
    def __init__(
        self,
        session: AsyncSession,
        principal: Principal,
        embeddings: EmbeddingsAdapter,
        vector_store: VectorStoreProvider,
    ) -> None:
        self.session = session
        self.principal = principal
        self.embeddings = embeddings
        self.vector_store = vector_store
        self.permissions = PermissionService(session, principal)
        self.bm25 = BM25IndexCache()

    async def retrieve(
        self,
        *,
        user_id: str,
        query: str,
        knowledge_base_ids: list[str],
        top_k: int,
        score_threshold: float | None,
        metadata_filter: dict[str, Any] | None,
        retrieval_mode: str = "hybrid",
    ) -> SearchResponse:
        started = time.perf_counter()
        requested = [UUID(value) for value in knowledge_base_ids]
        if user_id != str(self.principal.user_id):
            raise PermissionDeniedError("检索身份不匹配")
        scope = await self.permissions.build_retrieval_scope(requested)
        if set(scope.knowledge_base_ids) != set(requested):
            raise PermissionDeniedError("包含无权访问的知识库")
        enforced_filter = self.permissions.merge_metadata_filter(scope, metadata_filter)
        vector = await self.embeddings.embed_query(query)
        candidates = await self.vector_store.search(vector, enforced_filter, top_k * 2)
        vector_scores = {vector_id: score for vector_id, score, _ in candidates}
        keyword_scores: dict[str, float] = {}
        if retrieval_mode != "vector":
            keyword_scores = dict(
                await self.bm25.search(
                    self.session,
                    self.principal.tenant_id,
                    scope.knowledge_base_ids,
                    query,
                    top_k * 2,
                )
            )
        fused_ids = _rrf_rank([vector_scores, keyword_scores])
        if not fused_ids:
            return SearchResponse(
                query=query,
                items=[],
                duration_ms=int((time.perf_counter() - started) * 1000),
                trace_id=str(uuid4()),
            )
        rows = (
            await self.session.execute(
                select(DocumentChunk, Document)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(
                    DocumentChunk.vector_id.in_(fused_ids),
                    DocumentChunk.tenant_id == self.principal.tenant_id,
                    DocumentChunk.knowledge_base_id.in_(scope.knowledge_base_ids),
                    DocumentChunk.enabled.is_(True),
                    Document.enabled.is_(True),
                    Document.status == "ready",
                )
            )
        ).all()
        rows_by_vector = {chunk.vector_id: (chunk, document) for chunk, document in rows}
        items: list[RetrievedChunk] = []
        for vector_id in fused_ids:
            pair = rows_by_vector.get(vector_id)
            if pair is None:
                continue
            chunk, document = pair
            if score_threshold is not None and vector_scores.get(vector_id, 0.0) < score_threshold:
                continue
            items.append(
                RetrievedChunk(
                chunk_id=chunk.id,
                document_id=document.id,
                document_name=document.original_name,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                page_number=chunk.page_number,
                score=vector_scores.get(vector_id, 0.0),
                metadata=chunk.metadata_json,
                )
            )
        return SearchResponse(
            query=query,
            items=items[:top_k],
            duration_ms=int((time.perf_counter() - started) * 1000),
            trace_id=str(uuid4()),
        )


def _rrf_rank(channels: list[dict[str, float]], k: int = 60) -> list[str]:
    """Reciprocal Rank Fusion: merge multiple ranked channels into one ordered id list."""
    fused: dict[str, float] = {}
    for channel in channels:
        for rank, vector_id in enumerate(sorted(channel, key=channel.get, reverse=True)):
            fused[vector_id] = fused.get(vector_id, 0.0) + 1.0 / (k + rank)
    return sorted(fused, key=fused.get, reverse=True)
