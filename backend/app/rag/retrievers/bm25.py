import math
import re
import threading
import time
from collections import Counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, DocumentChunk

_CJK = re.compile(r"[\u4e00-\u9fff]+")
_SPLIT = re.compile(r"[^0-9a-z\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    """Tokenize for BM25: ASCII words plus CJK character bigrams (no external deps)."""
    lowered = text.casefold()
    tokens: list[str] = []
    for part in _SPLIT.split(lowered):
        if not part:
            continue
        if _CJK.fullmatch(part):
            if len(part) == 1:
                tokens.append(part)
            else:
                tokens.extend(part[index : index + 2] for index in range(len(part) - 1))
        else:
            tokens.append(part)
    return tokens


class BM25:
    """Okapi BM25 implementation with k1=1.5, b=0.75 (matching BM25Okapi defaults)."""

    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.documents: list[list[str]] = corpus
        self.k1 = k1
        self.b = b
        self.doc_len = [len(doc) for doc in corpus]
        self.avgdl = sum(self.doc_len) / len(corpus) if corpus else 0.0
        self.doc_freq: Counter[str] = Counter()
        for doc in corpus:
            self.doc_freq.update(set(doc))
        self.total = len(corpus)

    def get_scores(self, query_tokens: list[str]) -> list[float]:
        if not self.documents or not query_tokens:
            return []
        scores = [0.0] * self.total
        for token in set(query_tokens):
            df = self.doc_freq.get(token, 0)
            if df == 0:
                continue
            idf = math.log(1 + (self.total - df + 0.5) / (df + 0.5))
            for index, doc in enumerate(self.documents):
                frequency = doc.count(token)
                if frequency == 0:
                    continue
                denom = frequency + self.k1 * (
                    1 - self.b + self.b * self.doc_len[index] / self.avgdl
                )
                scores[index] += idf * frequency * (self.k1 + 1) / denom
        return scores


class BM25IndexCache:
    """Small in-memory BM25 cache keyed by tenant + knowledge-base scope, with TTL."""

    def __init__(self, ttl_seconds: float = 30.0, max_entries: int = 8) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._entries: dict[tuple[UUID, frozenset[UUID]], tuple[float, BM25 | None, list[DocumentChunk]]] = {}
        self._lock = threading.Lock()

    async def search(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        knowledge_base_ids: set[UUID] | frozenset[UUID],
        query: str,
        top_k: int,
    ) -> list[tuple[str, float]]:
        key = (tenant_id, frozenset(knowledge_base_ids))
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and now - entry[0] < self._ttl:
                index, rows = entry[1], entry[2]
            else:
                index, rows = await self._build(session, tenant_id, knowledge_base_ids)
                self._entries[key] = (now, index, rows)
                if len(self._entries) > self._max:
                    oldest = min(self._entries, key=lambda item: self._entries[item][0])
                    self._entries.pop(oldest, None)
        if index is None:
            return []
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = index.get_scores(tokens)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [
            (rows[i].vector_id, float(scores[i]))
            for i in ranked
            if scores[i] > 0
        ][:top_k]

    async def _build(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        knowledge_base_ids: set[UUID] | frozenset[UUID],
    ) -> tuple[BM25 | None, list[DocumentChunk]]:
        rows = list(
            (
                await session.execute(
                    select(DocumentChunk)
                    .join(Document, Document.id == DocumentChunk.document_id)
                    .where(
                        DocumentChunk.tenant_id == tenant_id,
                        DocumentChunk.knowledge_base_id.in_(knowledge_base_ids),
                        DocumentChunk.enabled.is_(True),
                        Document.enabled.is_(True),
                        Document.status == "ready",
                    )
                )
            ).scalars()
        )
        if not rows:
            return None, []
        corpus = [tokenize(row.content) for row in rows]
        return BM25(corpus), rows
