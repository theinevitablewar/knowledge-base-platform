from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from .common import ORMModel


class LoginRequest(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=8, max_length=200)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(ORMModel):
    id: UUID
    tenant_id: UUID
    username: str
    email: str
    display_name: str
    status: str
    is_tenant_admin: bool


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(min_length=1, max_length=120)
    is_tenant_admin: bool = False


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[str] = Field(min_length=1)

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, value: list[str]) -> list[str]:
        allowed = {
            "knowledge_base:read",
            "document:read",
            "document:write",
            "retrieval:search",
            "rag:answer",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"不支持的 scopes: {', '.join(sorted(unknown))}")
        return sorted(set(value))


class ApiKeyCreated(BaseModel):
    id: UUID
    name: str
    key: str
    prefix: str
    scopes: list[str]
