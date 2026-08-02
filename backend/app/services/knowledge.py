from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.security import Principal
from app.models import KnowledgeBase, KnowledgeBaseMember, User, Workspace
from app.permissions import PermissionService
from app.repositories import KnowledgeRepository
from app.schemas.knowledge import KnowledgeBaseCreate, KnowledgeBaseUpdate, MemberUpsert


class KnowledgeBaseService:
    def __init__(self, session: AsyncSession, principal: Principal) -> None:
        self.session = session
        self.principal = principal
        self.permissions = PermissionService(session, principal)
        self.repository = KnowledgeRepository(session)

    async def create(self, body: KnowledgeBaseCreate) -> KnowledgeBase:
        workspace = await self.session.scalar(
            select(Workspace).where(
                Workspace.id == body.workspace_id,
                Workspace.tenant_id == self.principal.tenant_id,
                Workspace.status == "active",
            )
        )
        if not workspace:
            raise NotFoundError("工作空间不存在")
        item = KnowledgeBase(
            tenant_id=self.principal.tenant_id,
            created_by=self.principal.user_id,
            embedding_provider="openai",
            embedding_model="text-embedding-3-small",
            embedding_dimension=1536,
            retrieval_mode="vector",
            icon="book",
            **body.model_dump(),
        )
        self.session.add(item)
        await self.session.flush()
        self.session.add(
            KnowledgeBaseMember(
                knowledge_base_id=item.id,
                user_id=self.principal.user_id,
                role="owner",
                created_at=datetime.now(UTC),
            )
        )
        return item

    async def get_allowed(self, knowledge_base_id: UUID, action: str = "view") -> KnowledgeBase:
        item = await self.repository.get(knowledge_base_id, self.principal.tenant_id)
        if not item:
            raise NotFoundError("知识库不存在")
        allowed = await self.permissions._can(item, action)
        if not allowed:
            raise PermissionDeniedError("没有知识库访问权限")
        return item

    async def list_allowed(self) -> list[KnowledgeBase]:
        ids = await self.permissions.get_allowed_knowledge_base_ids()
        return await self.repository.list(self.principal.tenant_id, ids)

    async def update(self, knowledge_base_id: UUID, body: KnowledgeBaseUpdate) -> KnowledgeBase:
        item = await self.get_allowed(knowledge_base_id, "edit")
        for name, value in body.model_dump(exclude_none=True).items():
            setattr(item, name, value)
        item.updated_at = datetime.now(UTC)
        return item

    async def archive_delete(self, knowledge_base_id: UUID) -> KnowledgeBase:
        item = await self.get_allowed(knowledge_base_id, "delete")
        item.status = "archived"
        return item

    async def members(self, knowledge_base_id: UUID) -> list[KnowledgeBaseMember]:
        await self.get_allowed(knowledge_base_id, "members")
        return list(
            await self.session.scalars(
                select(KnowledgeBaseMember).where(KnowledgeBaseMember.knowledge_base_id == knowledge_base_id)
            )
        )

    async def upsert_member(self, knowledge_base_id: UUID, body: MemberUpsert) -> KnowledgeBaseMember:
        knowledge_base = await self.get_allowed(knowledge_base_id, "members")
        target = await self.session.scalar(
            select(User).where(
                User.id == body.user_id,
                User.tenant_id == self.principal.tenant_id,
                User.status == "active",
            )
        )
        if not target:
            raise NotFoundError("目标用户不存在")
        actor_role = await self.permissions._role(knowledge_base)
        if body.role == "owner" and actor_role != "owner":
            raise PermissionDeniedError("仅 Owner 可以授予 Owner 角色")
        member = await self.repository.member(knowledge_base_id, body.user_id)
        if member:
            member.role = body.role
            return member
        member = KnowledgeBaseMember(
            knowledge_base_id=knowledge_base_id,
            user_id=body.user_id,
            role=body.role,
            created_at=datetime.now(UTC),
        )
        self.session.add(member)
        await self.session.flush()
        return member
