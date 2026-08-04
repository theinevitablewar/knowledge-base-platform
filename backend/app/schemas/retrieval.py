from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=5000)
    knowledge_base_ids: list[UUID] = Field(min_length=1, max_length=20)
    top_k: int = Field(default=8, ge=1, le=50)
    score_threshold: float | None = Field(default=None, ge=0, le=1)
    metadata_filter: dict[str, Any] | None = None
    retrieval_mode: str = Field(default="hybrid", pattern="^(vector|hybrid)$")


class RetrievedChunk(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_name: str
    chunk_index: int = 0
    content: str
    page_number: int | None
    score: float
    metadata: dict[str, Any]


class SearchResponse(BaseModel):
    query: str
    items: list[RetrievedChunk]
    duration_ms: int
    trace_id: str


class AnswerRequest(SearchRequest):
    pass


class Citation(BaseModel):
    document_id: UUID
    document_name: str
    chunk_id: UUID
    page_number: int | None
    quote: str
    score: float


class AnswerResponse(BaseModel):
    answer: str
    citations: list[Citation]
    trace_id: str
