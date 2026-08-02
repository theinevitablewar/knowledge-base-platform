from uuid import UUID

from fastapi import APIRouter

from app.api.deps import PrincipalDep, SessionDep, require_scope
from app.api.providers import EmbeddingsDep, SettingsDep, StorageDep, VectorDep
from app.api.v1.retrieval import _search
from app.core.exceptions import NotFoundError
from app.models import DocumentChunk
from app.rag.chains import RagAnswerChain
from app.repositories import DocumentRepository
from app.schemas.document import DocumentOut
from app.schemas.knowledge import KnowledgeBaseOut
from app.schemas.retrieval import AnswerRequest, AnswerResponse, SearchRequest, SearchResponse
from app.services import DocumentService, KnowledgeBaseService

router = APIRouter(prefix="/agent", tags=["Agent API"])


@router.get("/knowledge-bases", response_model=list[KnowledgeBaseOut])
async def knowledge_bases(session: SessionDep, principal: PrincipalDep):
    require_scope(principal, "knowledge_base:read")
    return await KnowledgeBaseService(session, principal).list_allowed()


@router.post("/search", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    session: SessionDep,
    principal: PrincipalDep,
    embeddings: EmbeddingsDep,
    vector_store: VectorDep,
) -> SearchResponse:
    require_scope(principal, "retrieval:search")
    return await _search(body, session, principal, embeddings, vector_store)


@router.post("/answer", response_model=AnswerResponse)
async def answer(
    body: AnswerRequest,
    session: SessionDep,
    principal: PrincipalDep,
    embeddings: EmbeddingsDep,
    vector_store: VectorDep,
    settings: SettingsDep,
) -> AnswerResponse:
    require_scope(principal, "rag:answer")
    result = await _search(body, session, principal, embeddings, vector_store)
    return await RagAnswerChain(settings).answer(body.query, result)


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def document(
    document_id: UUID,
    session: SessionDep,
    principal: PrincipalDep,
    settings: SettingsDep,
    storage: StorageDep,
):
    require_scope(principal, "document:read")
    return await DocumentService(session, principal, settings, storage).get_allowed(document_id)


@router.get("/chunks/{chunk_id}")
async def chunk(chunk_id: UUID, session: SessionDep, principal: PrincipalDep):
    require_scope(principal, "document:read")
    item = await session.get(DocumentChunk, chunk_id)
    if not item or item.tenant_id != principal.tenant_id:
        raise NotFoundError("Chunk 不存在")
    document = await DocumentRepository(session).get(item.document_id, principal.tenant_id)
    if not document or not await KnowledgeBaseService(session, principal).get_allowed(
        document.knowledge_base_id
    ):
        raise NotFoundError("Chunk 不存在")
    return {
        "id": item.id,
        "document_id": item.document_id,
        "content": item.content,
        "page_number": item.page_number,
        "metadata": item.metadata_json,
    }
