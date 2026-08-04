import pytest

from app.core.security import Principal
from app.rag.retrievers import SecureRetriever
from app.rag.retrievers.bm25 import BM25, tokenize
from app.rag.retrievers.secure import _rrf_rank
from tests.conftest import FakeEmbeddings
from tests.test_retrieval_rag import _indexed


def test_tokenize_cjk_bigrams_and_ascii_words():
    tokens = tokenize("预付款支付 payment-2026")
    assert "预付" in tokens
    assert "付款" in tokens
    assert "payment" in tokens
    assert "2026" in tokens


def test_bm25_ranks_exact_term_higher():
    corpus = [tokenize("预付款必须在支付前提交申请"), tokenize("今天天气不错")]
    index = BM25(corpus)
    scores = index.get_scores(tokenize("预付款"))
    assert scores[0] > scores[1]
    assert scores[0] > 0


def test_rrf_fusion_merges_channels():
    ranked = _rrf_rank([{"a": 0.9, "b": 0.5}, {"b": 5.0, "c": 4.0}])
    assert ranked[0] == "b"
    assert set(ranked) == {"a", "b", "c"}


@pytest.mark.asyncio
async def test_hybrid_recalls_keyword_when_vector_misses(seeded, session_factory, vectors):
    async with session_factory() as session:
        kb, _, chunk, _ = await _indexed(session, seeded)
        vectors.candidates = []
        principal = Principal(seeded["admin"].id, seeded["tenant_a"].id, "admin", True)
        result = await SecureRetriever(session, principal, FakeEmbeddings(), vectors).retrieve(
            user_id=str(principal.user_id),
            query="预付款",
            knowledge_base_ids=[str(kb.id)],
            top_k=8,
            score_threshold=None,
            metadata_filter=None,
        )
        assert [item.chunk_id for item in result.items] == [chunk.id]


@pytest.mark.asyncio
async def test_vector_only_mode_ignores_keyword_channel(seeded, session_factory, vectors):
    async with session_factory() as session:
        kb, _, _, _ = await _indexed(session, seeded)
        vectors.candidates = []
        principal = Principal(seeded["admin"].id, seeded["tenant_a"].id, "admin", True)
        result = await SecureRetriever(session, principal, FakeEmbeddings(), vectors).retrieve(
            user_id=str(principal.user_id),
            query="预付款",
            knowledge_base_ids=[str(kb.id)],
            top_k=8,
            score_threshold=None,
            metadata_filter=None,
            retrieval_mode="vector",
        )
        assert result.items == []
