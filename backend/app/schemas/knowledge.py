from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from .common import ORMModel


class KnowledgeBaseCreate(BaseModel):
    workspace_id: UUID
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    visibility: Literal["private", "members", "workspace", "tenant"] = "members"
    chunk_strategy: Literal["recursive", "page", "markdown"] = "recursive"
    chunk_size: int = Field(default=800, ge=100, le=8000)
    chunk_overlap: int = Field(default=120, ge=0, le=2000)
    top_k: int = Field(default=8, ge=1, le=50)
    score_threshold: float | None = Field(default=None, ge=0, le=1)


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    visibility: Literal["private", "members", "workspace", "tenant"] | None = None
    status: Literal["active", "archived"] | None = None
    chunk_strategy: Literal["recursive", "page", "markdown"] | None = None
    chunk_size: int | None = Field(default=None, ge=100, le=8000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=2000)
    top_k: int | None = Field(default=None, ge=1, le=50)
    score_threshold: float | None = Field(default=None, ge=0, le=1)


class KnowledgeBaseOut(ORMModel):
    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    name: str
    description: str
    status: str
    visibility: str
    chunk_strategy: str
    chunk_size: int
    chunk_overlap: int
    top_k: int
    score_threshold: float | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class StatisticsOut(BaseModel):
    document_count: int
    chunk_count: int
    ready_documents: int
    failed_documents: int


class MemberUpsert(BaseModel):
    user_id: UUID
    role: Literal["owner", "admin", "editor", "contributor", "viewer"]


class MemberOut(ORMModel):
    user_id: UUID
    role: str
    created_at: datetime
