from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from .common import ORMModel


class DocumentOut(ORMModel):
    id: UUID
    knowledge_base_id: UUID
    original_name: str
    mime_type: str
    file_size: int
    checksum: str
    page_count: int
    chunk_count: int
    status: str
    enabled: bool
    version: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class UploadResult(BaseModel):
    document_id: UUID
    task_id: UUID
    status: str


class ChunkOut(ORMModel):
    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    page_number: int | None
    token_count: int
    metadata: dict[str, Any]
    enabled: bool


class ChunkUpdate(BaseModel):
    content: str | None = None
    enabled: bool | None = None


class TaskOut(ORMModel):
    id: UUID
    document_id: UUID
    task_type: str
    status: str
    progress: int
    current_stage: str
    retry_count: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
