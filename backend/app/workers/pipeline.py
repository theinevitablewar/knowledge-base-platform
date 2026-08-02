import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from langsmith import traceable
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db import SessionFactory
from app.models import Document, DocumentChunk, IngestionTask, KnowledgeBase
from app.rag.embeddings import embedding_provider
from app.rag.embeddings.providers import EmbeddingsAdapter
from app.rag.parsers import parser_for
from app.rag.splitters import chunker_for
from app.rag.types import ChunkingStrategy, DocumentChunkData, DocumentParser, ParsedDocument
from app.rag.vectorstores import QdrantVectorStoreProvider
from app.storage import MinioStorage


def _trace_identity(inputs: dict[str, Any]) -> dict[str, Any]:
    return {"document_id": str(inputs.get("document_id", ""))}


@traceable(
    name="document_parse",
    run_type="tool",
    process_inputs=_trace_identity,
    process_outputs=lambda output: {"page_count": len(output.pages)},
)
async def _parse_traced(parser: DocumentParser, path: str, document_id: UUID) -> ParsedDocument:
    return await parser.parse(path)


@traceable(
    name="document_split",
    run_type="tool",
    process_inputs=_trace_identity,
    process_outputs=lambda output: {"chunk_count": len(output)},
)
async def _split_traced(
    strategy: ChunkingStrategy, parsed: ParsedDocument, document_id: UUID
) -> list[DocumentChunkData]:
    return strategy.split(parsed)


@traceable(
    name="document_embedding",
    run_type="embedding",
    process_inputs=_trace_identity,
    process_outputs=lambda output: {"vector_count": len(output)},
)
async def _embed_traced(
    embeddings: EmbeddingsAdapter, texts: list[str], document_id: UUID
) -> list[list[float]]:
    return await embeddings.embed_documents(texts)


async def _stage(task_id: UUID, status: str, stage: str, progress: int) -> None:
    async with SessionFactory() as session:
        task = await session.get(IngestionTask, task_id)
        if task:
            task.status, task.current_stage, task.progress = status, stage, progress
            if status == "processing" and not task.started_at:
                task.started_at = datetime.now(UTC)
            await session.commit()


@traceable(name="document_ingestion", run_type="chain")
async def ingest_document(task_id: UUID) -> None:
    settings = get_settings()
    storage = MinioStorage(settings)
    vector_store = QdrantVectorStoreProvider(settings)
    new_vector_ids: list[str] = []
    try:
        async with SessionFactory() as session:
            task = await session.get(IngestionTask, task_id)
            if not task or task.status in {"completed", "cancelled"}:
                return
            document = await session.get(Document, task.document_id)
            if not document or document.status == "deleted":
                return
            knowledge_base = await session.get(KnowledgeBase, document.knowledge_base_id)
            if not knowledge_base:
                raise RuntimeError("knowledge base missing")
            document.status = "parsing"
            await session.commit()
            document_values = {
                "id": document.id,
                "tenant_id": document.tenant_id,
                "workspace_id": document.workspace_id,
                "knowledge_base_id": document.knowledge_base_id,
                "owner_id": document.owner_id,
                "original_name": document.original_name,
                "storage_key": document.storage_key,
                "version": document.version,
            }
            kb_values = {
                "chunk_strategy": knowledge_base.chunk_strategy,
                "chunk_size": knowledge_base.chunk_size,
                "chunk_overlap": knowledge_base.chunk_overlap,
                "embedding_dimension": knowledge_base.embedding_dimension,
                "visibility": knowledge_base.visibility,
            }
        await _stage(task_id, "processing", "parsing", 15)
        raw = await storage.get_bytes(document_values["storage_key"])
        suffix = Path(document_values["original_name"]).suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
            temporary.write(raw)
            path = temporary.name
        try:
            parsed = await _parse_traced(
                parser_for(document_values["original_name"]), path, document_values["id"]
            )
            if parsed.title == Path(path).stem:
                parsed.title = Path(document_values["original_name"]).stem
            parsed.metadata["source_file"] = document_values["original_name"]
        finally:
            Path(path).unlink(missing_ok=True)
        parsed_key = (
            f"parsed/{document_values['tenant_id']}/{document_values['knowledge_base_id']}"
            f"/{document_values['id']}/parsed.json"
        )
        await storage.put_bytes(parsed_key, parsed.model_dump_json().encode(), "application/json")
        await _stage(task_id, "processing", "chunking", 35)
        chunks_data = await _split_traced(
            chunker_for(kb_values["chunk_strategy"], kb_values["chunk_size"], kb_values["chunk_overlap"]),
            parsed,
            document_values["id"],
        )
        await _stage(task_id, "processing", "embedding", 55)
        embeddings = embedding_provider(settings, kb_values["embedding_dimension"])
        vectors = await _embed_traced(
            embeddings, [chunk.content for chunk in chunks_data], document_values["id"]
        )
        async with SessionFactory() as session:
            old_chunks = list(
                await session.scalars(
                    select(DocumentChunk).where(DocumentChunk.document_id == document_values["id"])
                )
            )
            records: list[DocumentChunk] = []
            payloads: list[dict] = []
            for index, chunk in enumerate(chunks_data):
                chunk_id, vector_id = uuid4(), str(uuid4())
                new_vector_ids.append(vector_id)
                metadata = {**chunk.metadata, "source_file": document_values["original_name"]}
                record = DocumentChunk(
                    id=chunk_id,
                    tenant_id=document_values["tenant_id"],
                    workspace_id=document_values["workspace_id"],
                    knowledge_base_id=document_values["knowledge_base_id"],
                    document_id=document_values["id"],
                    chunk_index=index,
                    content=chunk.content,
                    page_number=chunk.page_number,
                    start_index=chunk.start_index,
                    end_index=chunk.end_index,
                    token_count=chunk.token_count,
                    metadata_json=metadata,
                    enabled=True,
                    vector_id=vector_id,
                )
                records.append(record)
                payloads.append(
                    {
                        "tenant_id": str(document_values["tenant_id"]),
                        "workspace_id": str(document_values["workspace_id"]),
                        "knowledge_base_id": str(document_values["knowledge_base_id"]),
                        "document_id": str(document_values["id"]),
                        "chunk_id": str(chunk_id),
                        "owner_id": str(document_values["owner_id"]),
                        "visibility": kb_values["visibility"],
                        "page_number": chunk.page_number,
                        "source_file": document_values["original_name"],
                        "enabled": True,
                        "is_deleted": False,
                        "index_version": document_values["version"],
                    }
                )
            await _stage(task_id, "processing", "indexing", 80)
            await vector_store.add_chunks(records, vectors, payloads)
            await session.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == document_values["id"])
            )
            session.add_all(records)
            document = await session.get(Document, document_values["id"])
            task = await session.get(IngestionTask, task_id)
            if document and task:
                document.page_count, document.chunk_count = len(parsed.pages), len(records)
                document.status, document.error_message = "ready", None
                task.status, task.current_stage, task.progress = "completed", "completed", 100
                task.completed_at = datetime.now(UTC)
            await session.commit()
            await vector_store.delete_ids([item.vector_id for item in old_chunks])
    except Exception as exc:
        if new_vector_ids:
            try:
                await vector_store.delete_ids(new_vector_ids)
            except Exception:
                pass
        async with SessionFactory() as session:
            task = await session.get(IngestionTask, task_id)
            if task:
                document = await session.get(Document, task.document_id)
                task.status, task.current_stage, task.error_message = "failed", "failed", str(exc)[:2000]
                task.completed_at = datetime.now(UTC)
                if document:
                    document.status, document.error_message = "failed", str(exc)[:2000]
                await session.commit()
        raise


async def delete_document_resources(document_id: UUID) -> None:
    settings = get_settings()
    storage, vector_store = MinioStorage(settings), QdrantVectorStoreProvider(settings)
    async with SessionFactory() as session:
        document = await session.get(Document, document_id)
        if not document or document.status == "deleted":
            return
        await vector_store.delete_document(document.tenant_id, document.id)
        await storage.delete(document.storage_key)
        parsed_key = f"parsed/{document.tenant_id}/{document.knowledge_base_id}/{document.id}/parsed.json"
        try:
            await storage.delete(parsed_key)
        except Exception:
            pass
        await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        document.status, document.enabled = "deleted", False
        await session.commit()


async def cleanup_knowledge_base(knowledge_base_id: UUID) -> None:
    """Remove every external resource before marking a knowledge base deleted."""
    async with SessionFactory() as session:
        knowledge_base = await session.get(KnowledgeBase, knowledge_base_id)
        if not knowledge_base or knowledge_base.status == "deleted":
            return
        document_ids = list(
            await session.scalars(select(Document.id).where(Document.knowledge_base_id == knowledge_base_id))
        )
    for document_id in document_ids:
        await delete_document_resources(document_id)
    async with SessionFactory() as session:
        knowledge_base = await session.get(KnowledgeBase, knowledge_base_id)
        if knowledge_base:
            knowledge_base.status = "deleted"
            await session.commit()
