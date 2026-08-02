import pytest
from sqlalchemy import select

from app.models import Document, KnowledgeBase
from tests.conftest import login


@pytest.mark.asyncio
async def test_upload_is_async_and_stores_original(client, seeded, session_factory, storage, monkeypatch):
    async with session_factory() as session:
        kb = KnowledgeBase(
            tenant_id=seeded["tenant_a"].id,
            workspace_id=seeded["workspace"].id,
            name="Docs",
            description="",
            created_by=seeded["admin"].id,
        )
        session.add(kb)
        await session.commit()
        kb_id = kb.id
    from app.api.v1 import documents as routes

    monkeypatch.setattr(routes.ingest_task, "delay", lambda _: None)
    headers = await login(client, "admin", "admin123456")
    response = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers=headers,
        files={"files": ("policy.md", b"# Policy\nApprove first.", "text/markdown")},
    )
    assert response.status_code == 202, response.text
    assert response.json()[0]["status"] == "queued"
    document_id = response.json()[0]["document_id"]
    async with session_factory() as session:
        document = await session.scalar(select(Document).where(Document.knowledge_base_id == kb_id))
        assert document and document.storage_key in storage.objects
    original = await client.get(f"/api/v1/documents/{document_id}/content", headers=headers)
    assert original.status_code == 200
    assert original.content == b"# Policy\nApprove first."
    assert original.headers["content-type"].startswith("text/markdown")
    assert original.headers["content-disposition"] == "inline; filename*=UTF-8''policy.md"


@pytest.mark.asyncio
async def test_unsupported_upload_rejected(client, seeded, session_factory):
    async with session_factory() as session:
        kb = KnowledgeBase(
            tenant_id=seeded["tenant_a"].id,
            workspace_id=seeded["workspace"].id,
            name="Docs2",
            description="",
            created_by=seeded["admin"].id,
        )
        session.add(kb)
        await session.commit()
        kb_id = kb.id
    headers = await login(client, "admin", "admin123456")
    response = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers=headers,
        files={"files": ("payload.exe", b"MZ", "application/octet-stream")},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_read_only_api_key_cannot_upload(client, seeded, session_factory):
    async with session_factory() as session:
        kb = KnowledgeBase(
            tenant_id=seeded["tenant_a"].id,
            workspace_id=seeded["workspace"].id,
            name="Read only",
            description="",
            created_by=seeded["admin"].id,
        )
        session.add(kb)
        await session.commit()
        kb_id = kb.id
    headers = await login(client, "admin", "admin123456")
    created = await client.post(
        "/api/v1/auth/api-keys",
        headers=headers,
        json={"name": "reader", "scopes": ["document:read"]},
    )
    assert created.status_code == 201, created.text
    response = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers={"X-API-Key": created.json()["key"]},
        files={"files": ("policy.md", b"read only", "text/markdown")},
    )
    assert response.status_code == 403
    assert "document:write" in response.text
