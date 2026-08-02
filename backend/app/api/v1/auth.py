from uuid import UUID

import jwt
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import PrincipalDep, SessionDep, get_current_user
from app.core.exceptions import PermissionDeniedError
from app.core.security import create_token, decode_token
from app.models import User
from app.repositories import UserRepository
from app.schemas.auth import (
    ApiKeyCreate,
    ApiKeyCreated,
    LoginRequest,
    PasswordChange,
    RefreshRequest,
    TokenPair,
    UserCreate,
    UserOut,
)
from app.services import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenPair)
async def login(body: LoginRequest, session: SessionDep):
    tokens, _ = await AuthService(session).login(body.username, body.password)
    await session.commit()
    return tokens


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, session: SessionDep):
    try:
        payload = decode_token(body.refresh_token, "refresh")
        user = await UserRepository(session).get(
            __import__("uuid").UUID(payload["sub"]), __import__("uuid").UUID(payload["tenant_id"])
        )
        if not user or user.status != "active":
            raise PermissionDeniedError("用户不可用")
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise PermissionDeniedError("Refresh Token 无效") from exc
    return TokenPair(
        access_token=create_token(user.id, user.tenant_id, "access"),
        refresh_token=create_token(user.id, user.tenant_id, "refresh"),
    )


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password", status_code=204)
async def change_password(body: PasswordChange, session: SessionDep, user: User = Depends(get_current_user)):
    await AuthService(session).change_password(user, body.current_password, body.new_password)
    await session.commit()


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(body: UserCreate, session: SessionDep, principal: PrincipalDep):
    if not principal.is_tenant_admin:
        raise PermissionDeniedError("仅租户管理员可以创建用户")
    item = await AuthService(session).create_user(principal.tenant_id, body)
    await session.commit()
    return item


@router.get("/users", response_model=list[UserOut])
async def list_users(session: SessionDep, principal: PrincipalDep) -> list[User]:
    if not principal.is_tenant_admin:
        raise PermissionDeniedError("仅租户管理员可以查看用户")
    return list(
        await session.scalars(
            select(User).where(User.tenant_id == principal.tenant_id).order_by(User.username)
        )
    )


@router.post("/users/{user_id}/disable", response_model=UserOut)
async def disable_user(user_id: UUID, session: SessionDep, principal: PrincipalDep) -> User:
    if not principal.is_tenant_admin:
        raise PermissionDeniedError("仅租户管理员可以禁用用户")
    user = await UserRepository(session).get(user_id, principal.tenant_id)
    if not user:
        raise PermissionDeniedError("用户不存在")
    if user.id == principal.user_id:
        raise PermissionDeniedError("不能禁用当前登录用户")
    user.status = "disabled"
    await session.commit()
    return user


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=201)
async def create_key(body: ApiKeyCreate, session: SessionDep, user: User = Depends(get_current_user)):
    result = await AuthService(session).create_api_key(user, body)
    await session.commit()
    return result
