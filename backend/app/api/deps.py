from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedError
from app.core.security import Principal, decode_token, hash_api_key
from app.db import get_session
from app.models import User
from app.repositories import UserRepository

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_principal(
    session: SessionDep,
    authorization: Annotated[str, Header()] = "",
    x_api_key: Annotated[str, Header()] = "",
) -> Principal:
    users = UserRepository(session)
    if x_api_key:
        item = await users.api_key_by_hash(hash_api_key(x_api_key))
        if not item or (item.expires_at and item.expires_at <= datetime.now(UTC)):
            raise PermissionDeniedError("API Key 无效或已过期")
        user = await users.get(item.created_by, item.tenant_id)
        if not user or user.status != "active":
            raise PermissionDeniedError("API Key 所属用户不可用")
        item.last_used_at = datetime.now(UTC)
        return Principal(
            user.id, user.tenant_id, user.username, user.is_tenant_admin, frozenset(item.scopes), "api_key"
        )
    if not authorization.startswith("Bearer "):
        raise PermissionDeniedError("需要登录")
    try:
        payload = decode_token(authorization[7:])
        user_id, tenant_id = UUID(payload["sub"]), UUID(payload["tenant_id"])
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise PermissionDeniedError("登录凭据无效或已过期") from exc
    user = await users.get(user_id, tenant_id)
    if not user or user.status != "active":
        raise PermissionDeniedError("用户已禁用")
    return Principal(user.id, user.tenant_id, user.username, user.is_tenant_admin)


PrincipalDep = Annotated[Principal, Depends(get_principal)]


async def get_current_user(session: SessionDep, principal: PrincipalDep) -> User:
    user = await UserRepository(session).get(principal.user_id, principal.tenant_id)
    if not user:
        raise PermissionDeniedError("用户不存在")
    return user


def require_scope(principal: Principal, scope: str) -> None:
    if principal.auth_type == "api_key" and scope not in principal.scopes:
        raise PermissionDeniedError(f"API Key 缺少 scope：{scope}")
