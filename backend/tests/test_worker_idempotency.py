from datetime import UTC, datetime

import pytest

from app.core.config import Settings
from app.core.security import Principal
from app.models import Document, IngestionTask, KnowledgeBase
from app.rag.chains import RagAnswerChain
from app.rag.retrievers import SecureRetriever
from app.workers import pipeline
from tests.conftest import FakeEmbeddings


@pytest.mark.asyncio
async def test_completed_ingestion_is_idempotent(seeded, session_factory, storage, vectors, monkeypatch):
    async with session_factory() as session:
        kb = KnowledgeBase(
            tenant_id=seeded["tenant_a"].id,
            workspace_id=seeded["workspace"].id,
            name="Idempotent",
            description="",
            created_by=seeded["admin"].id,
        )
        session.add(kb)
        await session.flush()
        document = Document(
            tenant_id=seeded["tenant_a"].id,
            workspace_id=seeded["workspace"].id,
            knowledge_base_id=kb.id,
            owner_id=seeded["admin"].id,
            original_name="a.txt",
            stored_name="a.txt",
            mime_type="text/plain",
            extension=".txt",
            file_size=1,
            storage_bucket="test",
            storage_key="a",
            checksum="a" * 64,
            status="ready",
            enabled=True,
        )
        session.add(document)
        await session.flush()
        task = IngestionTask(
            document_id=document.id,
            task_type="ingest",
            status="completed",
            progress=100,
            current_stage="completed",
            retry_count=0,
            completed_at=datetime.now(UTC),
        )
        session.add(task)
        await session.commit()
        task_id = task.id
    monkeypatch.setattr(pipeline, "SessionFactory", session_factory)
    monkeypatch.setattr(pipeline, "MinioStorage", lambda _settings: storage)
    monkeypatch.setattr(pipeline, "QdrantVectorStoreProvider", lambda _settings: vectors)
    await pipeline.ingest_document(task_id)
    assert storage.objects == {}


@pytest.mark.asyncio
async def test_delete_removes_vectors_and_disables_document(
    seeded, session_factory, storage, vectors, monkeypatch
):
    async with session_factory() as session:
        kb = KnowledgeBase(
            tenant_id=seeded["tenant_a"].id,
            workspace_id=seeded["workspace"].id,
            name="Delete",
            description="",
            created_by=seeded["admin"].id,
        )
        session.add(kb)
        await session.flush()
        document = Document(
            tenant_id=seeded["tenant_a"].id,
            workspace_id=seeded["workspace"].id,
            knowledge_base_id=kb.id,
            owner_id=seeded["admin"].id,
            original_name="a.txt",
            stored_name="a.txt",
            mime_type="text/plain",
            extension=".txt",
            file_size=1,
            storage_bucket="test",
            storage_key="a",
            checksum="a" * 64,
            status="deleting",
            enabled=False,
        )
        session.add(document)
        await session.commit()
        document_id = document.id
    storage.objects["a"] = b"x"
    monkeypatch.setattr(pipeline, "SessionFactory", session_factory)
    monkeypatch.setattr(pipeline, "MinioStorage", lambda _settings: storage)
    monkeypatch.setattr(pipeline, "QdrantVectorStoreProvider", lambda _settings: vectors)
    await pipeline.delete_document_resources(document_id)
    async with session_factory() as session:
        deleted = await session.get(Document, document_id)
        assert deleted and deleted.status == "deleted" and not deleted.enabled
    assert str(document_id) in vectors.deleted_documents


@pytest.mark.asyncio
async def test_complete_ingestion_retrieval_and_answer_flow(
    seeded, session_factory, storage, vectors, monkeypatch
):
    async with session_factory() as session:
        kb = KnowledgeBase(
            tenant_id=seeded["tenant_a"].id,
            workspace_id=seeded["workspace"].id,
            name="Flow",
            description="",
            created_by=seeded["admin"].id,
            embedding_dimension=16,
        )
        session.add(kb)
        await session.flush()
        document = Document(
            tenant_id=seeded["tenant_a"].id,
            workspace_id=seeded["workspace"].id,
            knowledge_base_id=kb.id,
            owner_id=seeded["admin"].id,
            original_name="policy.md",
            stored_name="policy.md",
            mime_type="text/markdown",
            extension=".md",
            file_size=30,
            storage_bucket="test",
            storage_key="original/policy.md",
            checksum="b" * 64,
            status="queued",
            enabled=True,
        )
        session.add(document)
        await session.flush()
        task = IngestionTask(
            document_id=document.id,
            task_type="ingest",
            status="queued",
            progress=0,
            current_stage="queued",
            retry_count=0,
        )
        session.add(task)
        await session.commit()
        task_id, kb_id, document_id = task.id, kb.id, document.id
    storage.objects["original/policy.md"] = "# 预付款\n\n支付前必须提交申请。".encode()
    monkeypatch.setattr(pipeline, "SessionFactory", session_factory)
    monkeypatch.setattr(pipeline, "MinioStorage", lambda _settings: storage)
    monkeypatch.setattr(pipeline, "QdrantVectorStoreProvider", lambda _settings: vectors)
    await pipeline.ingest_document(task_id)

    async with session_factory() as session:
        ready = await session.get(Document, document_id)
        assert ready and ready.status == "ready" and ready.chunk_count > 0
        principal = Principal(seeded["admin"].id, seeded["tenant_a"].id, "admin", True)
        search = await SecureRetriever(session, principal, FakeEmbeddings(), vectors).retrieve(
            user_id=str(principal.user_id),
            query="预付款流程",
            knowledge_base_ids=[str(kb_id)],
            top_k=8,
            score_threshold=0.2,
            metadata_filter=None,
        )
        answer = await RagAnswerChain(Settings(ai_mock_mode=True)).answer("预付款流程", search)
    assert search.items and search.items[0].document_name == "policy.md"
    assert answer.citations and answer.citations[0].chunk_id == search.items[0].chunk_id
