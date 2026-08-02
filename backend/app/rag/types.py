from typing import Any, Protocol

from pydantic import BaseModel, Field


class ParsedPage(BaseModel):
    page_number: int | None
    title: str | None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParsedDocument(BaseModel):
    title: str | None
    pages: list[ParsedPage]
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentChunkData(BaseModel):
    content: str
    page_number: int | None
    start_index: int | None = None
    end_index: int | None = None
    token_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentParser(Protocol):
    async def parse(self, file_path: str) -> ParsedDocument: ...


class ChunkingStrategy(Protocol):
    def split(self, parsed_document: ParsedDocument) -> list[DocumentChunkData]: ...


class EmbeddingProvider(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...
