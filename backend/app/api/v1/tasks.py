from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import PrincipalDep, SessionDep
from app.core.exceptions import ConflictError, NotFoundError
from app.models import Document, IngestionTask, KnowledgeBase
from app.permissions import PermissionService
from app.schemas.document import TaskOut
from app.workers.tasks import ingest_task

router = APIRouter(prefix="/tasks", tags=["Tasks"])


async def _allowed_task(task_id: UUID, session: SessionDep, principal: PrincipalDep) -> IngestionTask:
    row = (
        await session.execute(
            select(IngestionTask)
            .join(Document, Document.id == IngestionTask.document_id)
            .where(
                IngestionTask.id == task_id,
                Document.tenant_id == principal.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise NotFoundError("任务不存在")
    return row


@router.get("", response_model=list[TaskOut])
async def list_tasks(session: SessionDep, principal: PrincipalDep) -> list[IngestionTask]:
    return list(
        await session.scalars(
            select(IngestionTask)
            .join(Document, Document.id == IngestionTask.document_id)
            .where(Document.tenant_id == principal.tenant_id)
            .order_by(IngestionTask.created_at.desc())
            .limit(200)
        )
    )


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(task_id: UUID, session: SessionDep, principal: PrincipalDep) -> IngestionTask:
    return await _allowed_task(task_id, session, principal)


@router.post("/{task_id}/retry", response_model=TaskOut, status_code=202)
async def retry_task(task_id: UUID, session: SessionDep, principal: PrincipalDep) -> IngestionTask:
    task = await _allowed_task(task_id, session, principal)
    document = await session.get(Document, task.document_id)
    if not document:
        raise NotFoundError("文档不存在")
    knowledge_base = await session.get(KnowledgeBase, document.knowledge_base_id)
    if not knowledge_base or not await PermissionService(session, principal).can_edit_knowledge_base(
        knowledge_base
    ):
        raise NotFoundError("文档不存在")
    if task.status not in {"failed", "cancelled"}:
        raise ConflictError("仅失败或已取消任务可重试")
    task.status, task.current_stage, task.progress = "queued", "queued", 0
    task.retry_count += 1
    task.error_message = None
    await session.commit()
    ingest_task.delay(str(task.id))
    return task


@router.post("/{task_id}/cancel", response_model=TaskOut)
async def cancel_task(task_id: UUID, session: SessionDep, principal: PrincipalDep) -> IngestionTask:
    task = await _allowed_task(task_id, session, principal)
    if task.status in {"completed", "failed", "cancelled"}:
        raise ConflictError("任务已结束")
    task.status, task.current_stage = "cancelled", "cancelled"
    await session.commit()
    return task
