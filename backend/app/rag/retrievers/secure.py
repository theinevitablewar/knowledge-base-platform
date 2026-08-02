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

    async def retrieve(
        self,
        *,
        user_id: str,
        query: str,
        knowledge_base_ids: list[str],
        top_k: int,
        score_threshold: float | None,
        metadata_filter: dict[str, Any] | None,
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
        candidates = await self.vector_store.search(vector, enforced_filter, top_k)
        vector_scores = {vector_id: score for vector_id, score, _ in candidates}
        if not vector_scores:
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
                    DocumentChunk.vector_id.in_(vector_scores),
                    DocumentChunk.tenant_id == self.principal.tenant_id,
                    DocumentChunk.knowledge_base_id.in_(scope.knowledge_base_ids),
                    DocumentChunk.enabled.is_(True),
                    Document.enabled.is_(True),
                    Document.status == "ready",
                )
            )
        ).all()
        items = [
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=document.id,
                document_name=document.original_name,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                page_number=chunk.page_number,
                score=vector_scores[chunk.vector_id],
                metadata=chunk.metadata_json,
            )
            for chunk, document in rows
            if score_threshold is None or vector_scores[chunk.vector_id] >= score_threshold
        ]
        items.sort(key=lambda item: item.score, reverse=True)
        return SearchResponse(
            query=query,
            items=items[:top_k],
            duration_ms=int((time.perf_counter() - started) * 1000),
            trace_id=str(uuid4()),
        )
