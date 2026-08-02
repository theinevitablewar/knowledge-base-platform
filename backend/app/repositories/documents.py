from __future__ import annotations

import builtins
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, DocumentChunk, IngestionTask


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, document_id: UUID, tenant_id: UUID) -> Document | None:
        return cast(
            Document | None,
            await self.session.scalar(
                select(Document).where(
                    Document.id == document_id,
                    Document.tenant_id == tenant_id,
                    Document.status != "deleted",
                )
            ),
        )

    async def list(
        self,
        knowledge_base_id: UUID,
        tenant_id: UUID,
        status: str | None = None,
        query_text: str | None = None,
    ) -> builtins.list[Document]:
        query = (
            select(Document)
            .where(
                Document.knowledge_base_id == knowledge_base_id,
                Document.tenant_id == tenant_id,
                Document.status != "deleted",
            )
            .order_by(Document.updated_at.desc())
        )
        if status:
            query = query.where(Document.status == status)
        if query_text:
            query = query.where(Document.original_name.ilike(f"%{query_text}%"))
        return list(await self.session.scalars(query))

    async def chunks(self, document_id: UUID) -> builtins.list[DocumentChunk]:
        return list(
            await self.session.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document_id)
                .order_by(DocumentChunk.chunk_index)
            )
        )

    async def task(self, task_id: UUID) -> IngestionTask | None:
        return await self.session.get(IngestionTask, task_id)
