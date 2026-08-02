import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from langsmith import traceable

from app.api.deps import PrincipalDep, SessionDep, require_scope
from app.api.providers import EmbeddingsDep, SettingsDep, VectorDep
from app.rag.chains import RagAnswerChain
from app.rag.retrievers import SecureRetriever
from app.schemas.retrieval import AnswerRequest, AnswerResponse, SearchRequest, SearchResponse
from app.services.audit import write_audit

router = APIRouter(tags=["Retrieval and RAG"])


async def _search(
    body: SearchRequest,
    session: SessionDep,
    principal: PrincipalDep,
    embeddings: EmbeddingsDep,
    vector_store: VectorDep,
) -> SearchResponse:
    retriever = SecureRetriever(session, principal, embeddings, vector_store)
    return await retriever.retrieve(
        user_id=str(principal.user_id),
        query=body.query,
        knowledge_base_ids=[str(item) for item in body.knowledge_base_ids],
        top_k=body.top_k,
        score_threshold=body.score_threshold,
        metadata_filter=body.metadata_filter,
    )


@router.post("/retrieval/search", response_model=SearchResponse)
@traceable(name="secure_retrieval", run_type="retriever")
async def search(
    body: SearchRequest,
    request: Request,
    session: SessionDep,
    principal: PrincipalDep,
    embeddings: EmbeddingsDep,
    vector_store: VectorDep,
) -> SearchResponse:
    require_scope(principal, "retrieval:search")
    result = await _search(body, session, principal, embeddings, vector_store)
    await write_audit(
        session,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        action="retrieval.search",
        resource_type="knowledge_base",
        resource_id=body.knowledge_base_ids[0],
        request_id=request.state.request_id,
        details={
            "knowledge_base_ids": [str(item) for item in body.knowledge_base_ids],
            "result_count": len(result.items),
            "trace_id": result.trace_id,
        },
    )
    await session.commit()
    return result


@router.post("/rag/answer", response_model=AnswerResponse)
@traceable(name="rag_answer", run_type="chain")
async def answer(
    body: AnswerRequest,
    request: Request,
    session: SessionDep,
    principal: PrincipalDep,
    embeddings: EmbeddingsDep,
    vector_store: VectorDep,
    settings: SettingsDep,
) -> AnswerResponse:
    require_scope(principal, "rag:answer")
    found = await _search(body, session, principal, embeddings, vector_store)
    result = await RagAnswerChain(settings).answer(body.query, found)
    await write_audit(
        session,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        action="rag.answer",
        resource_type="knowledge_base",
        resource_id=body.knowledge_base_ids[0],
        request_id=request.state.request_id,
        details={"citation_count": len(result.citations), "trace_id": result.trace_id},
    )
    await session.commit()
    return result


@router.post("/rag/answer/stream")
async def stream_answer(
    body: AnswerRequest,
    request: Request,
    session: SessionDep,
    principal: PrincipalDep,
    embeddings: EmbeddingsDep,
    vector_store: VectorDep,
    settings: SettingsDep,
) -> StreamingResponse:
    result = await answer(body, request, session, principal, embeddings, vector_store, settings)

    async def events():
        for offset in range(0, len(result.answer), 24):
            if await request.is_disconnected():
                return
            delta = json.dumps({"delta": result.answer[offset : offset + 24]}, ensure_ascii=False)
            yield f"event: answer.delta\ndata: {delta}\n\n"
            await asyncio.sleep(0)
        payload = result.model_dump(mode="json")
        yield f"event: answer.completed\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
