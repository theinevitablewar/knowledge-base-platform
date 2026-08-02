from typing import cast
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiKey, User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def by_login(self, login: str) -> User | None:
        return cast(
            User | None,
            await self.session.scalar(select(User).where(or_(User.username == login, User.email == login))),
        )

    async def get(self, user_id: UUID, tenant_id: UUID) -> User | None:
        return cast(
            User | None,
            await self.session.scalar(select(User).where(User.id == user_id, User.tenant_id == tenant_id)),
        )

    async def api_key_by_hash(self, key_hash: str) -> ApiKey | None:
        return cast(
            ApiKey | None,
            await self.session.scalar(
                select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.enabled.is_(True))
            ),
        )
