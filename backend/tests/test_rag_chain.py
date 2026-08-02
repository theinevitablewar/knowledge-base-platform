import pytest

from app.core.config import Settings
from app.rag.chains import RagAnswerChain
from app.schemas.retrieval import RetrievedChunk, SearchResponse


@pytest.mark.asyncio
async def test_mock_rag_citations_are_derived_from_results():
    item = RetrievedChunk(
        chunk_id=__import__("uuid").uuid4(),
        document_id=__import__("uuid").uuid4(),
        document_name="real.md",
        content="真实资料",
        page_number=2,
        score=0.8,
        metadata={},
    )
    response = await RagAnswerChain(Settings(ai_mock_mode=True)).answer(
        "问题", SearchResponse(query="问题", items=[item], duration_ms=1, trace_id="trace")
    )
    assert response.citations[0].chunk_id == item.chunk_id
    assert response.citations[0].quote == "真实资料"


@pytest.mark.asyncio
async def test_empty_context_refuses_to_guess():
    response = await RagAnswerChain(Settings(ai_mock_mode=True)).answer(
        "问题", SearchResponse(query="问题", items=[], duration_ms=1, trace_id="trace")
    )
    assert "无法" in response.answer
