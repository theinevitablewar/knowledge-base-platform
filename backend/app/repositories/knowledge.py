from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, DocumentChunk, KnowledgeBase, KnowledgeBaseMember


class KnowledgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, knowledge_base_id: UUID, tenant_id: UUID) -> KnowledgeBase | None:
        return cast(
            KnowledgeBase | None,
            await self.session.scalar(
                select(KnowledgeBase).where(
                    KnowledgeBase.id == knowledge_base_id,
                    KnowledgeBase.tenant_id == tenant_id,
                    KnowledgeBase.status != "deleted",
                )
            ),
        )

    async def list(self, tenant_id: UUID, allowed_ids: list[UUID] | None = None) -> list[KnowledgeBase]:
        query = (
            select(KnowledgeBase)
            .where(KnowledgeBase.tenant_id == tenant_id, KnowledgeBase.status != "deleted")
            .order_by(KnowledgeBase.updated_at.desc())
        )
        if allowed_ids is not None:
            if not allowed_ids:
                return []
            query = query.where(KnowledgeBase.id.in_(allowed_ids))
        return list(await self.session.scalars(query))

    async def member(self, knowledge_base_id: UUID, user_id: UUID) -> KnowledgeBaseMember | None:
        return cast(
            KnowledgeBaseMember | None,
            await self.session.scalar(
                select(KnowledgeBaseMember).where(
                    KnowledgeBaseMember.knowledge_base_id == knowledge_base_id,
                    KnowledgeBaseMember.user_id == user_id,
                )
            ),
        )

    async def statistics(self, knowledge_base_id: UUID) -> dict[str, int]:
        document_count = (
            await self.session.scalar(
                select(func.count(Document.id)).where(
                    Document.knowledge_base_id == knowledge_base_id, Document.status != "deleted"
                )
            )
            or 0
        )
        chunk_count = (
            await self.session.scalar(
                select(func.count(DocumentChunk.id)).where(
                    DocumentChunk.knowledge_base_id == knowledge_base_id, DocumentChunk.enabled.is_(True)
                )
            )
            or 0
        )
        ready = (
            await self.session.scalar(
                select(func.count(Document.id)).where(
                    Document.knowledge_base_id == knowledge_base_id, Document.status == "ready"
                )
            )
            or 0
        )
        failed = (
            await self.session.scalar(
                select(func.count(Document.id)).where(
                    Document.knowledge_base_id == knowledge_base_id, Document.status == "failed"
                )
            )
            or 0
        )
        return {
            "document_count": document_count,
            "chunk_count": chunk_count,
            "ready_documents": ready,
            "failed_documents": failed,
        }
