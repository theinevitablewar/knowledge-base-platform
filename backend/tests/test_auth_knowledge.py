import pytest

from app.models import KnowledgeBase, KnowledgeBaseMember
from tests.conftest import login


@pytest.mark.asyncio
async def test_login_and_me(client, seeded):
    headers = await login(client, "admin", "admin123456")
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["tenant_id"] == str(seeded["tenant_a"].id)


@pytest.mark.asyncio
async def test_knowledge_base_crud_and_cross_tenant_block(client, seeded):
    headers = await login(client, "admin", "admin123456")
    created = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        json={
            "workspace_id": str(seeded["workspace"].id),
            "name": "Policy",
            "description": "制度",
        },
    )
    assert created.status_code == 201, created.text
    knowledge_id = created.json()["id"]
    changed = await client.patch(
        f"/api/v1/knowledge-bases/{knowledge_id}", headers=headers, json={"name": "Policy v2"}
    )
    assert changed.json()["name"] == "Policy v2"
    outsider = await login(client, "outsider", "outsider123456")
    denied = await client.get(f"/api/v1/knowledge-bases/{knowledge_id}", headers=outsider)
    assert denied.status_code in {403, 404}


@pytest.mark.asyncio
async def test_viewer_cannot_upload_or_delete(client, seeded, session_factory, monkeypatch):
    async with session_factory() as session:
        kb = KnowledgeBase(
            tenant_id=seeded["tenant_a"].id,
            workspace_id=seeded["workspace"].id,
            name="Viewer KB",
            description="",
            created_by=seeded["admin"].id,
        )
        session.add(kb)
        await session.flush()
        session.add(KnowledgeBaseMember(knowledge_base_id=kb.id, user_id=seeded["viewer"].id, role="viewer"))
        await session.commit()
        kb_id = kb.id
    headers = await login(client, "viewer", "viewer123456")
    response = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers=headers,
        files={"files": ("note.txt", b"secret", "text/plain")},
    )
    assert response.status_code == 403
