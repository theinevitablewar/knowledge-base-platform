from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.models import KnowledgeBase, KnowledgeBaseMember, WorkspaceMember

ROLE_PERMISSIONS = {
    "owner": {"view", "search", "upload", "edit", "delete", "members", "settings"},
    "admin": {"view", "search", "upload", "edit", "delete", "members"},
    "editor": {"view", "search", "upload", "edit", "reindex"},
    "contributor": {"view", "search", "upload"},
    "viewer": {"view", "search"},
}


@dataclass(frozen=True)
class RetrievalScope:
    tenant_id: UUID
    user_id: UUID
    knowledge_base_ids: tuple[UUID, ...]


class PermissionService:
    def __init__(self, session: AsyncSession, principal: Principal) -> None:
        self.session = session
        self.principal = principal

    async def _role(self, knowledge_base: KnowledgeBase) -> str | None:
        if knowledge_base.tenant_id != self.principal.tenant_id:
            return None
        if self.principal.is_tenant_admin or knowledge_base.created_by == self.principal.user_id:
            return "owner"
        member = await self.session.scalar(
            select(KnowledgeBaseMember).where(
                KnowledgeBaseMember.knowledge_base_id == knowledge_base.id,
                KnowledgeBaseMember.user_id == self.principal.user_id,
            )
        )
        if member:
            return member.role
        workspace_member = await self.session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == knowledge_base.workspace_id,
                WorkspaceMember.user_id == self.principal.user_id,
            )
        )
        if knowledge_base.visibility == "tenant":
            return "viewer"
        if knowledge_base.visibility == "workspace" and workspace_member:
            return "viewer"
        return None

    async def _can(self, knowledge_base: KnowledgeBase, action: str) -> bool:
        role = await self._role(knowledge_base)
        return bool(role and action in ROLE_PERMISSIONS.get(role, set()))

    async def can_view_knowledge_base(self, knowledge_base: KnowledgeBase) -> bool:
        return await self._can(knowledge_base, "view")

    async def can_edit_knowledge_base(self, knowledge_base: KnowledgeBase) -> bool:
        return await self._can(knowledge_base, "edit")

    async def can_upload_document(self, knowledge_base: KnowledgeBase) -> bool:
        return await self._can(knowledge_base, "upload")

    async def can_delete_document(self, knowledge_base: KnowledgeBase) -> bool:
        return await self._can(knowledge_base, "delete")

    async def can_read_document(self, knowledge_base: KnowledgeBase) -> bool:
        return await self.can_view_knowledge_base(knowledge_base)

    async def get_allowed_knowledge_base_ids(self, requested_ids: list[UUID] | None = None) -> list[UUID]:
        query = select(KnowledgeBase).where(
            KnowledgeBase.tenant_id == self.principal.tenant_id,
            KnowledgeBase.status == "active",
        )
        if requested_ids is not None:
            query = query.where(KnowledgeBase.id.in_(requested_ids))
        candidates = list(await self.session.scalars(query))
        return [item.id for item in candidates if await self.can_view_knowledge_base(item)]

    async def build_retrieval_scope(self, requested_ids: list[UUID]) -> RetrievalScope:
        allowed = await self.get_allowed_knowledge_base_ids(requested_ids)
        return RetrievalScope(self.principal.tenant_id, self.principal.user_id, tuple(allowed))

    @staticmethod
    def merge_metadata_filter(scope: RetrievalScope, user_filter: dict[str, Any] | None) -> dict[str, Any]:
        unsafe = {"tenant_id", "workspace_id", "knowledge_base_id", "owner_id", "enabled", "is_deleted"}
        safe = {key: value for key, value in (user_filter or {}).items() if key not in unsafe}
        return {
            **safe,
            "tenant_id": str(scope.tenant_id),
            "knowledge_base_id": [str(value) for value in scope.knowledge_base_ids],
            "enabled": True,
            "is_deleted": False,
        }
