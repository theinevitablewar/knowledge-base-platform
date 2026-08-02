import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.security import Principal
from app.models import Document, DocumentVersion, IngestionTask
from app.permissions import PermissionService
from app.repositories import DocumentRepository, KnowledgeRepository
from app.storage import MinioStorage

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".markdown"}


class DocumentService:
    def __init__(
        self, session: AsyncSession, principal: Principal, settings: Settings, storage: MinioStorage
    ) -> None:
        self.session, self.principal, self.settings, self.storage = session, principal, settings, storage
        self.documents = DocumentRepository(session)
        self.knowledge = KnowledgeRepository(session)
        self.permissions = PermissionService(session, principal)

    async def upload(self, knowledge_base_id: UUID, file: UploadFile) -> tuple[Document, IngestionTask]:
        knowledge_base = await self.knowledge.get(knowledge_base_id, self.principal.tenant_id)
        if not knowledge_base:
            raise NotFoundError("知识库不存在")
        if not await self.permissions.can_upload_document(knowledge_base):
            raise PermissionDeniedError("当前角色不能上传文档")
        original_name = Path(file.filename or "").name
        extension = Path(original_name).suffix.casefold()
        if extension not in ALLOWED_EXTENSIONS:
            raise ValidationError("仅支持 PDF、DOCX、TXT 和 Markdown")
        content = await file.read(self.settings.max_upload_mb * 1024 * 1024 + 1)
        if len(content) > self.settings.max_upload_mb * 1024 * 1024:
            raise ValidationError("文件超过上传大小限制")
        if not content:
            raise ValidationError("不能上传空文件")
        checksum = hashlib.sha256(content).hexdigest()
        document_id = uuid4()
        stored_name = f"{document_id}{extension}"
        key = f"original/{self.principal.tenant_id}/{knowledge_base_id}/{document_id}/v1/{stored_name}"
        await self.storage.put_bytes(key, content, file.content_type or "application/octet-stream")
        now = datetime.now(UTC)
        document = Document(
            id=document_id,
            tenant_id=self.principal.tenant_id,
            workspace_id=knowledge_base.workspace_id,
            knowledge_base_id=knowledge_base.id,
            owner_id=self.principal.user_id,
            original_name=original_name,
            stored_name=stored_name,
            mime_type=file.content_type or "application/octet-stream",
            extension=extension,
            file_size=len(content),
            storage_bucket=self.storage.bucket,
            storage_key=key,
            checksum=checksum,
            status="queued",
            enabled=True,
            version=1,
        )
        self.session.add(document)
        self.session.add(
            DocumentVersion(
                document_id=document.id,
                version=1,
                storage_key=key,
                checksum=checksum,
                status="active",
                created_by=self.principal.user_id,
                created_at=now,
            )
        )
        task = IngestionTask(
            document_id=document.id,
            task_type="ingest",
            status="queued",
            progress=0,
            current_stage="queued",
            retry_count=0,
            created_at=now,
        )
        self.session.add(task)
        await self.session.flush()
        return document, task

    async def get_allowed(self, document_id: UUID, action: str = "view") -> Document:
        document = await self.documents.get(document_id, self.principal.tenant_id)
        if not document:
            raise NotFoundError("文档不存在")
        knowledge_base = await self.knowledge.get(document.knowledge_base_id, self.principal.tenant_id)
        if not knowledge_base or not await self.permissions._can(knowledge_base, action):
            raise PermissionDeniedError("没有文档访问权限")
        return document

    async def soft_delete(self, document_id: UUID) -> Document:
        document = await self.get_allowed(document_id, "delete")
        document.status = "deleting"
        return document
