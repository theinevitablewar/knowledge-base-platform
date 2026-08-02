from uuid import uuid4

import pytest

from app.core.security import Principal
from app.models import Document, DocumentChunk, KnowledgeBase
from app.rag.retrievers import SecureRetriever
from tests.conftest import FakeEmbeddings, login


async def _indexed(session, seeded, *, enabled=True):
    kb = KnowledgeBase(
        tenant_id=seeded["tenant_a"].id,
        workspace_id=seeded["workspace"].id,
        name="Search",
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
        original_name="policy.pdf",
        stored_name="x.pdf",
        mime_type="application/pdf",
        extension=".pdf",
        file_size=10,
        storage_bucket="x",
        storage_key="x",
        checksum="a" * 64,
        status="ready" if enabled else "disabled",
        enabled=enabled,
    )
    session.add(document)
    await session.flush()
    vector_id = str(uuid4())
    chunk = DocumentChunk(
        tenant_id=seeded["tenant_a"].id,
        workspace_id=seeded["workspace"].id,
        knowledge_base_id=kb.id,
        document_id=document.id,
        chunk_index=0,
        content="预付款必须在支付前提交申请。",
        page_number=6,
        token_count=12,
        metadata_json={"document_type": "policy"},
        enabled=True,
        vector_id=vector_id,
    )
    session.add(chunk)
    await session.commit()
    return kb, document, chunk, vector_id


@pytest.mark.asyncio
async def test_secure_retriever_forces_scope_and_blocks_filter_override(seeded, session_factory, vectors):
    async with session_factory() as session:
        kb, _, chunk, vector_id = await _indexed(session, seeded)
        vectors.candidates = [(vector_id, 0.91, {})]
        principal = Principal(seeded["admin"].id, seeded["tenant_a"].id, "admin", True)
        result = await SecureRetriever(session, principal, FakeEmbeddings(), vectors).retrieve(
            user_id=str(principal.user_id),
            query="流程",
            knowledge_base_ids=[str(kb.id)],
            top_k=8,
            score_threshold=0.2,
            metadata_filter={
                "tenant_id": str(seeded["tenant_b"].id),
                "enabled": False,
                "document_type": "policy",
            },
        )
        assert result.items[0].chunk_id == chunk.id
        assert vectors.last_filter["tenant_id"] == str(seeded["tenant_a"].id)
        assert vectors.last_filter["enabled"] is True


@pytest.mark.asyncio
async def test_disabled_document_is_not_retrieved(seeded, session_factory, vectors):
    async with session_factory() as session:
        kb, _, _, vector_id = await _indexed(session, seeded, enabled=False)
        vectors.candidates = [(vector_id, 0.9, {})]
        principal = Principal(seeded["admin"].id, seeded["tenant_a"].id, "admin", True)
        result = await SecureRetriever(session, principal, FakeEmbeddings(), vectors).retrieve(
            user_id=str(principal.user_id),
            query="流程",
            knowledge_base_ids=[str(kb.id)],
            top_k=8,
            score_threshold=None,
            metadata_filter=None,
        )
        assert result.items == []


@pytest.mark.asyncio
async def test_rag_returns_real_citation(client, seeded, session_factory, vectors):
    async with session_factory() as session:
        kb, _, chunk, vector_id = await _indexed(session, seeded)
    vectors.candidates = [(vector_id, 0.93, {})]
    headers = await login(client, "admin", "admin123456")
    response = await client.post(
        "/api/v1/rag/answer",
        headers=headers,
        json={
            "query": "预付款流程？",
            "knowledge_base_ids": [str(kb.id)],
            "top_k": 8,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["citations"][0]["chunk_id"] == str(chunk.id)
    assert "预付款" in response.json()["answer"]


@pytest.mark.asyncio
async def test_cross_tenant_retrieval_is_blocked(client, seeded, session_factory):
    async with session_factory() as session:
        kb, *_ = await _indexed(session, seeded)
    headers = await login(client, "outsider", "outsider123456")
    response = await client.post(
        "/api/v1/retrieval/search",
        headers=headers,
        json={"query": "secret", "knowledge_base_ids": [str(kb.id)]},
    )
    assert response.status_code == 403
