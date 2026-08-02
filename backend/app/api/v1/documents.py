from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, File, Request, UploadFile

from app.api.deps import PrincipalDep, SessionDep, require_scope
from app.api.providers import SettingsDep, StorageDep
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.models import DocumentChunk, IngestionTask
from app.repositories import DocumentRepository
from app.schemas.document import ChunkOut, ChunkUpdate, DocumentOut, TaskOut, UploadResult
from app.services import DocumentService, KnowledgeBaseService
from app.services.audit import write_audit
from app.workers.tasks import delete_document_task, ingest_task

router = APIRouter(tags=["Documents"])


@router.post(
    "/knowledge-bases/{knowledge_base_id}/documents", response_model=list[UploadResult], status_code=202
)
async def upload_documents(
    knowledge_base_id: UUID,
    request: Request,
    session: SessionDep,
    principal: PrincipalDep,
    settings: SettingsDep,
    storage: StorageDep,
    files: list[UploadFile] = File(),
):
    require_scope(principal, "document:write")
    service = DocumentService(session, principal, settings, storage)
    results: list[tuple] = []
    for file in files:
        results.append(await service.upload(knowledge_base_id, file))
    for document, _task in results:
        await write_audit(
            session,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            action="document.upload",
            resource_type="document",
            resource_id=document.id,
            request_id=request.state.request_id,
            details={"name": document.original_name, "checksum": document.checksum},
        )
    await session.commit()
    for _, task in results:
        ingest_task.delay(str(task.id))
    return [
        UploadResult(document_id=document.id, task_id=task.id, status=task.status)
        for document, task in results
    ]


@router.get("/knowledge-bases/{knowledge_base_id}/documents", response_model=list[DocumentOut])
async def list_documents(
    knowledge_base_id: UUID,
    session: SessionDep,
    principal: PrincipalDep,
    status: str | None = None,
    q: str | None = None,
):
    require_scope(principal, "document:read")
    await KnowledgeBaseService(session, principal).get_allowed(knowledge_base_id)
    return await DocumentRepository(session).list(knowledge_base_id, principal.tenant_id, status, q)


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: UUID,
    session: SessionDep,
    principal: PrincipalDep,
    settings: SettingsDep,
    storage: StorageDep,
):
    require_scope(principal, "document:read")
    return await DocumentService(session, principal, settings, storage).get_allowed(document_id)


@router.get("/documents/{document_id}/download")
async def download_document(
    document_id: UUID,
    request: Request,
    session: SessionDep,
    principal: PrincipalDep,
    settings: SettingsDep,
    storage: StorageDep,
):
    require_scope(principal, "document:read")
    document = await DocumentService(session, principal, settings, storage).get_allowed(document_id)
    url = await storage.presigned_download(document.storage_key)
    await write_audit(
        session,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        action="document.download",
        resource_type="document",
        resource_id=document.id,
        request_id=request.state.request_id,
    )
    await session.commit()
    return {"url": url, "expires_in": 600}


@router.delete("/documents/{document_id}", status_code=202)
async def delete_document(
    document_id: UUID,
    request: Request,
    session: SessionDep,
    principal: PrincipalDep,
    settings: SettingsDep,
    storage: StorageDep,
):
    require_scope(principal, "document:write")
    document = await DocumentService(session, principal, settings, storage).soft_delete(document_id)
    await write_audit(
        session,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        action="document.delete.requested",
        resource_type="document",
        resource_id=document.id,
        request_id=request.state.request_id,
    )
    await session.commit()
    delete_document_task.delay(str(document.id))
    return {"message": "删除任务已提交"}


@router.post("/documents/{document_id}/reindex", response_model=TaskOut, status_code=202)
async def reindex_document(
    document_id: UUID,
    session: SessionDep,
    principal: PrincipalDep,
    settings: SettingsDep,
    storage: StorageDep,
):
    require_scope(principal, "document:write")
    document = await DocumentService(session, principal, settings, storage).get_allowed(
        document_id, "reindex"
    )
    task = IngestionTask(
        document_id=document.id,
        task_type="reindex",
        status="queued",
        progress=0,
        current_stage="queued",
        retry_count=0,
        created_at=datetime.now(UTC),
    )
    document.status = "queued"
    session.add(task)
    await session.commit()
    ingest_task.delay(str(task.id))
    return task


async def _set_enabled(
    document_id: UUID,
    enabled: bool,
    session: SessionDep,
    principal: PrincipalDep,
    settings: SettingsDep,
    storage: StorageDep,
):
    require_scope(principal, "document:write")
    document = await DocumentService(session, principal, settings, storage).get_allowed(document_id, "edit")
    document.enabled = enabled
    document.status = "ready" if enabled else "disabled"
    await session.commit()
    return document


@router.post("/documents/{document_id}/enable", response_model=DocumentOut)
async def enable_document(
    document_id: UUID,
    session: SessionDep,
    principal: PrincipalDep,
    settings: SettingsDep,
    storage: StorageDep,
):
    return await _set_enabled(document_id, True, session, principal, settings, storage)


@router.post("/documents/{document_id}/disable", response_model=DocumentOut)
async def disable_document(
    document_id: UUID,
    session: SessionDep,
    principal: PrincipalDep,
    settings: SettingsDep,
    storage: StorageDep,
):
    return await _set_enabled(document_id, False, session, principal, settings, storage)


@router.get("/documents/{document_id}/chunks", response_model=list[ChunkOut])
async def chunks(
    document_id: UUID,
    session: SessionDep,
    principal: PrincipalDep,
    settings: SettingsDep,
    storage: StorageDep,
):
    require_scope(principal, "document:read")
    await DocumentService(session, principal, settings, storage).get_allowed(document_id)
    items = await DocumentRepository(session).chunks(document_id)
    return [
        ChunkOut(
            id=item.id,
            tenant_id=item.tenant_id,
            workspace_id=item.workspace_id,
            knowledge_base_id=item.knowledge_base_id,
            document_id=item.document_id,
            parent_chunk_id=item.parent_chunk_id,
            chunk_index=item.chunk_index,
            content=item.content,
            page_number=item.page_number,
            start_index=item.start_index,
            end_index=item.end_index,
            token_count=item.token_count,
            metadata=item.metadata_json,
            enabled=item.enabled,
            vector_id=item.vector_id,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in items
    ]


@router.get("/chunks/{chunk_id}", response_model=ChunkOut)
async def chunk(chunk_id: UUID, session: SessionDep, principal: PrincipalDep):
    require_scope(principal, "document:read")
    item = await session.get(DocumentChunk, chunk_id)
    if not item or item.tenant_id != principal.tenant_id:
        raise NotFoundError("Chunk 不存在")
    return ChunkOut(
        id=item.id,
        tenant_id=item.tenant_id,
        workspace_id=item.workspace_id,
        knowledge_base_id=item.knowledge_base_id,
        document_id=item.document_id,
        parent_chunk_id=item.parent_chunk_id,
        chunk_index=item.chunk_index,
        content=item.content,
        page_number=item.page_number,
        start_index=item.start_index,
        end_index=item.end_index,
        token_count=item.token_count,
        metadata=item.metadata_json,
        enabled=item.enabled,
        vector_id=item.vector_id,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.patch("/chunks/{chunk_id}", response_model=ChunkOut)
async def update_chunk(chunk_id: UUID, body: ChunkUpdate, session: SessionDep, principal: PrincipalDep):
    require_scope(principal, "document:write")
    item = await session.get(DocumentChunk, chunk_id)
    if not item or item.tenant_id != principal.tenant_id:
        raise NotFoundError("Chunk 不存在")
    document = await DocumentRepository(session).get(item.document_id, principal.tenant_id)
    if not document:
        raise NotFoundError("文档不存在")
    knowledge = await KnowledgeBaseService(session, principal).get_allowed(document.knowledge_base_id, "edit")
    if not knowledge:
        raise PermissionDeniedError("不能修改 Chunk")
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(item, key, value)
    await session.commit()
    return await chunk(chunk_id, session, principal)


@router.post("/chunks/{chunk_id}/re-embed", status_code=202)
async def reembed_chunk(chunk_id: UUID, session: SessionDep, principal: PrincipalDep):
    require_scope(principal, "document:write")
    item = await session.get(DocumentChunk, chunk_id)
    if not item or item.tenant_id != principal.tenant_id:
        raise NotFoundError("Chunk 不存在")
    document = await DocumentRepository(session).get(item.document_id, principal.tenant_id)
    if not document:
        raise NotFoundError("文档不存在")
    await KnowledgeBaseService(session, principal).get_allowed(document.knowledge_base_id, "reindex")
    task = IngestionTask(
        document_id=document.id,
        task_type="reembed",
        status="queued",
        progress=0,
        current_stage="queued",
        retry_count=0,
        created_at=datetime.now(UTC),
    )
    document.status = "queued"
    session.add(task)
    await session.commit()
    ingest_task.delay(str(task.id))
    return {"message": "已提交一致性重新索引", "document_id": item.document_id, "task_id": task.id}
