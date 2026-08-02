from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    message: str


class AuditOut(ORMModel):
    id: UUID
    action: str
    resource_type: str
    resource_id: UUID | None
    request_id: str
    details: dict[str, Any]
    created_at: datetime
