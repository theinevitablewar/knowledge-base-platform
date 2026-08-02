import os
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["AI_MOCK_MODE"] = "true"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-at-least-32-bytes-long"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.providers import embeddings_provider, storage_provider, vector_provider
from app.core.security import hash_password
from app.db import get_session
from app.db.base import Base
from app.main import app
from app.models import Tenant, User, Workspace, WorkspaceMember


class FakeStorage:
    def __init__(self) -> None:
        self.bucket = "test-bucket"
        self.objects: dict[str, bytes] = {}

    async def put_bytes(self, key: str, content: bytes, content_type: str) -> None:
        self.objects[key] = content

    async def get_bytes(self, key: str) -> bytes:
        return self.objects[key]

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def presigned_download(self, key: str) -> str:
        return f"https://storage.test/{key}"


class FakeEmbeddings:
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), 1.0] for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return [float(len(text)), 1.0]


class FakeVectorStore:
    def __init__(self) -> None:
        self.candidates: list[tuple[str, float, dict[str, Any]]] = []
        self.last_filter: dict[str, Any] = {}
        self.deleted_documents: list[str] = []

    async def ensure_collection(self, dimension: int) -> None:
        pass

    async def add_chunks(self, chunks, vectors, payloads) -> None:
        self.candidates = [
            (chunk.vector_id, 0.9, payload) for chunk, payload in zip(chunks, payloads, strict=True)
        ]

    async def delete_document(self, tenant_id, document_id) -> None:
        self.deleted_documents.append(str(document_id))

    async def delete_chunk(self, tenant_id, chunk_id) -> None:
        pass

    async def delete_ids(self, vector_ids) -> None:
        pass

    async def search(self, vector, security_filter, top_k):
        self.last_filter = security_filter
        return self.candidates[:top_k]

    async def collection_status(self):
        return {"exists": True}


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def vectors() -> FakeVectorStore:
    return FakeVectorStore()


@pytest_asyncio.fixture
async def session_factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded(session_factory):
    async with session_factory() as session:
        tenant_a = Tenant(name="Tenant A", code=f"a-{uuid4()}", status="active")
        tenant_b = Tenant(name="Tenant B", code=f"b-{uuid4()}", status="active")
        session.add_all([tenant_a, tenant_b])
        await session.flush()
        admin = User(
            tenant_id=tenant_a.id,
            username="admin",
            email="admin@test.local",
            password_hash=hash_password("admin123456"),
            display_name="Admin",
            status="active",
            is_tenant_admin=True,
        )
        viewer = User(
            tenant_id=tenant_a.id,
            username="viewer",
            email="viewer@test.local",
            password_hash=hash_password("viewer123456"),
            display_name="Viewer",
            status="active",
            is_tenant_admin=False,
        )
        outsider = User(
            tenant_id=tenant_b.id,
            username="outsider",
            email="out@test.local",
            password_hash=hash_password("outsider123456"),
            display_name="Outsider",
            status="active",
            is_tenant_admin=True,
        )
        session.add_all([admin, viewer, outsider])
        await session.flush()
        workspace = Workspace(
            tenant_id=tenant_a.id, name="Workspace", description="", status="active", created_by=admin.id
        )
        other_workspace = Workspace(
            tenant_id=tenant_b.id, name="Other", description="", status="active", created_by=outsider.id
        )
        session.add_all([workspace, other_workspace])
        await session.flush()
        session.add_all(
            [
                WorkspaceMember(workspace_id=workspace.id, user_id=admin.id, role="owner"),
                WorkspaceMember(workspace_id=workspace.id, user_id=viewer.id, role="viewer"),
            ]
        )
        await session.commit()
        return {
            "tenant_a": tenant_a,
            "tenant_b": tenant_b,
            "admin": admin,
            "viewer": viewer,
            "outsider": outsider,
            "workspace": workspace,
            "other_workspace": other_workspace,
        }


@pytest_asyncio.fixture
async def client(session_factory, storage, vectors) -> AsyncIterator[AsyncClient]:
    async def override_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[storage_provider] = lambda: storage
    app.dependency_overrides[embeddings_provider] = lambda: FakeEmbeddings()
    app.dependency_overrides[vector_provider] = lambda: vectors
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


async def login(client: AsyncClient, username: str, password: str) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
