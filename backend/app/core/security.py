import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

password_hasher = PasswordHash.recommended()


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    tenant_id: UUID
    username: str
    is_tenant_admin: bool = False
    scopes: frozenset[str] = frozenset()
    auth_type: Literal["jwt", "api_key"] = "jwt"


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_token(user_id: UUID, tenant_id: UUID, token_type: str) -> str:
    settings = get_settings()
    lifetime = (
        timedelta(minutes=settings.jwt_access_token_expire_minutes)
        if token_type == "access"
        else timedelta(days=settings.jwt_refresh_token_expire_days)
    )
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "type": token_type,
        "iat": now,
        "exp": now + lifetime,
        "jti": secrets.token_hex(12),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("token type mismatch")
    return payload


def generate_api_key() -> tuple[str, str, str]:
    raw = f"kbp_{secrets.token_urlsafe(36)}"
    return raw, raw[:12], hash_api_key(raw)


def hash_api_key(raw: str) -> str:
    secret = get_settings().app_secret_key
    return hashlib.sha256(f"{secret}:{raw}".encode()).hexdigest()
