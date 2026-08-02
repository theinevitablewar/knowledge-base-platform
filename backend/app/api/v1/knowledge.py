from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Request
from sqlalchemy import delete, select

from app.api.deps import PrincipalDep, SessionDep
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.models import KnowledgeBaseMember, Workspace, WorkspaceMember
from app.schemas.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeBaseUpdate,
    MemberOut,
    MemberUpsert,
    StatisticsOut,
)
from app.services import KnowledgeBaseService
from app.services.audit import write_audit
from app.workers.tasks import cleanup_knowledge_base_task

router = APIRouter(tags=["Knowledge Bases"])


@router.get("/workspaces")
async def workspaces(session: SessionDep, principal: PrincipalDep):
    return list(
        await session.scalars(
            select(Workspace)
            .where(Workspace.tenant_id == principal.tenant_id, Workspace.status == "active")
            .order_by(Workspace.updated_at.desc())
        )
    )


@router.post("/workspaces", status_code=201)
async def create_workspace(body: dict, session: SessionDep, principal: PrincipalDep):
    item = Workspace(
        tenant_id=principal.tenant_id,
        name=str(body.get("name", "新工作空间"))[:120],
        description=str(body.get("description", ""))[:4000],
        status="active",
        created_by=principal.user_id,
    )
    session.add(item)
    await session.flush()
    session.add(
        WorkspaceMember(
            workspace_id=item.id,
            user_id=principal.user_id,
            role="owner",
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()
    return {"id": item.id, "name": item.name, "description": item.description}


@router.post("/knowledge-bases", response_model=KnowledgeBaseOut, status_code=201)
async def create_knowledge_base(
    body: KnowledgeBaseCreate,
    request: Request,
    session: SessionDep,
    principal: PrincipalDep,
):
    item = await KnowledgeBaseService(session, principal).create(body)
    await write_audit(
        session,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        action="knowledge_base.create",
        resource_type="knowledge_base",
        resource_id=item.id,
        request_id=request.state.request_id,
    )
    await session.commit()
    return item


@router.get("/knowledge-bases", response_model=list[KnowledgeBaseOut])
async def list_knowledge_bases(session: SessionDep, principal: PrincipalDep):
    return await KnowledgeBaseService(session, principal).list_allowed()


@router.get("/knowledge-bases/{knowledge_base_id}", response_model=KnowledgeBaseOut)
async def get_knowledge_base(knowledge_base_id: UUID, session: SessionDep, principal: PrincipalDep):
    return await KnowledgeBaseService(session, principal).get_allowed(knowledge_base_id)


@router.patch("/knowledge-bases/{knowledge_base_id}", response_model=KnowledgeBaseOut)
async def update_knowledge_base(
    knowledge_base_id: UUID,
    body: KnowledgeBaseUpdate,
    request: Request,
    session: SessionDep,
    principal: PrincipalDep,
):
    item = await KnowledgeBaseService(session, principal).update(knowledge_base_id, body)
    await write_audit(
        session,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        action="knowledge_base.update",
        resource_type="knowledge_base",
        resource_id=item.id,
        request_id=request.state.request_id,
        details={"fields": list(body.model_dump(exclude_none=True))},
    )
    await session.commit()
    return item


@router.delete("/knowledge-bases/{knowledge_base_id}", status_code=202)
async def delete_knowledge_base(
    knowledge_base_id: UUID,
    request: Request,
    session: SessionDep,
    principal: PrincipalDep,
):
    item = await KnowledgeBaseService(session, principal).archive_delete(knowledge_base_id)
    await write_audit(
        session,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        action="knowledge_base.delete.requested",
        resource_type="knowledge_base",
        resource_id=item.id,
        request_id=request.state.request_id,
    )
    await session.commit()
    cleanup_knowledge_base_task.delay(str(item.id))
    return {"message": "知识库删除任务已提交"}


@router.get("/knowledge-bases/{knowledge_base_id}/statistics", response_model=StatisticsOut)
async def statistics(knowledge_base_id: UUID, session: SessionDep, principal: PrincipalDep):
    service = KnowledgeBaseService(session, principal)
    await service.get_allowed(knowledge_base_id)
    return await service.repository.statistics(knowledge_base_id)


@router.get("/knowledge-bases/{knowledge_base_id}/members", response_model=list[MemberOut])
async def members(knowledge_base_id: UUID, session: SessionDep, principal: PrincipalDep):
    return await KnowledgeBaseService(session, principal).members(knowledge_base_id)


@router.post("/knowledge-bases/{knowledge_base_id}/members", response_model=MemberOut)
async def add_member(
    knowledge_base_id: UUID,
    body: MemberUpsert,
    request: Request,
    session: SessionDep,
    principal: PrincipalDep,
):
    item = await KnowledgeBaseService(session, principal).upsert_member(knowledge_base_id, body)
    await write_audit(
        session,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        action="knowledge_base.member.upsert",
        resource_type="knowledge_base",
        resource_id=knowledge_base_id,
        request_id=request.state.request_id,
        details={"member_user_id": str(body.user_id), "role": body.role},
    )
    await session.commit()
    return item


@router.patch("/knowledge-bases/{knowledge_base_id}/members/{user_id}", response_model=MemberOut)
async def update_member(
    knowledge_base_id: UUID,
    user_id: UUID,
    body: MemberUpsert,
    request: Request,
    session: SessionDep,
    principal: PrincipalDep,
):
    if body.user_id != user_id:
        raise PermissionDeniedError("成员身份不匹配")
    item = await KnowledgeBaseService(session, principal).upsert_member(knowledge_base_id, body)
    await write_audit(
        session,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        action="knowledge_base.member.update",
        resource_type="knowledge_base",
        resource_id=knowledge_base_id,
        request_id=request.state.request_id,
        details={"member_user_id": str(user_id), "role": body.role},
    )
    await session.commit()
    return item


@router.delete("/knowledge-bases/{knowledge_base_id}/members/{user_id}", status_code=204)
async def remove_member(
    knowledge_base_id: UUID,
    user_id: UUID,
    request: Request,
    session: SessionDep,
    principal: PrincipalDep,
):
    await KnowledgeBaseService(session, principal).get_allowed(knowledge_base_id, "members")
    result = await session.execute(
        delete(KnowledgeBaseMember).where(
            KnowledgeBaseMember.knowledge_base_id == knowledge_base_id,
            KnowledgeBaseMember.user_id == user_id,
            KnowledgeBaseMember.role != "owner",
        )
    )
    if not result.rowcount:
        raise NotFoundError("成员不存在或不能移除 Owner")
    await write_audit(
        session,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        action="knowledge_base.member.remove",
        resource_type="knowledge_base",
        resource_id=knowledge_base_id,
        request_id=request.state.request_id,
        details={"member_user_id": str(user_id)},
    )
    await session.commit()
