from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, PermissionDeniedError
from app.core.security import create_token, generate_api_key, hash_password, verify_password
from app.models import ApiKey, User
from app.repositories import UserRepository
from app.schemas.auth import ApiKeyCreate, ApiKeyCreated, TokenPair, UserCreate


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def login(self, username: str, password: str) -> tuple[TokenPair, User]:
        user = await self.users.by_login(username)
        if not user or user.status != "active" or not verify_password(password, user.password_hash):
            raise PermissionDeniedError("用户名或密码错误")
        return TokenPair(
            access_token=create_token(user.id, user.tenant_id, "access"),
            refresh_token=create_token(user.id, user.tenant_id, "refresh"),
        ), user

    async def create_user(self, tenant_id: UUID, body: UserCreate) -> User:
        exists = await self.session.scalar(
            select(User).where(
                User.tenant_id == tenant_id,
                (User.username == body.username) | (User.email == body.email),
            )
        )
        if exists:
            raise ConflictError("用户名或邮箱已存在")
        user = User(
            tenant_id=tenant_id,
            username=body.username,
            email=str(body.email),
            password_hash=hash_password(body.password),
            display_name=body.display_name,
            is_tenant_admin=body.is_tenant_admin,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def change_password(self, user: User, current: str, new: str) -> None:
        if not verify_password(current, user.password_hash):
            raise PermissionDeniedError("当前密码不正确")
        user.password_hash = hash_password(new)

    async def create_api_key(self, user: User, body: ApiKeyCreate) -> ApiKeyCreated:
        raw, prefix, digest = generate_api_key()
        item = ApiKey(
            tenant_id=user.tenant_id,
            name=body.name,
            key_hash=digest,
            prefix=prefix,
            scopes=body.scopes,
            enabled=True,
            created_by=user.id,
            created_at=datetime.now(UTC),
        )
        self.session.add(item)
        await self.session.flush()
        return ApiKeyCreated(id=item.id, name=item.name, key=raw, prefix=prefix, scopes=item.scopes)
