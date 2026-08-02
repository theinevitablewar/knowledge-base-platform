from typing import Any

import httpx


class KnowledgeBaseClient:
    """Async client for LangGraph, Deep Agents, and other trusted callers."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), headers={"X-API-Key": api_key}, timeout=30
        )

    async def list_knowledge_bases(self) -> list[dict[str, Any]]:
        response = await self.client.get("/api/v1/agent/knowledge-bases")
        response.raise_for_status()
        return list(response.json())

    async def search(
        self, query: str, knowledge_base_ids: list[str], top_k: int = 8
    ) -> dict[str, Any]:
        response = await self.client.post(
            "/api/v1/agent/search",
            json={"query": query, "knowledge_base_ids": knowledge_base_ids, "top_k": top_k},
        )
        response.raise_for_status()
        return dict(response.json())

    async def answer(
        self, query: str, knowledge_base_ids: list[str], top_k: int = 8
    ) -> dict[str, Any]:
        response = await self.client.post(
            "/api/v1/agent/answer",
            json={"query": query, "knowledge_base_ids": knowledge_base_ids, "top_k": top_k},
        )
        response.raise_for_status()
        return dict(response.json())

    async def close(self) -> None:
        await self.client.aclose()
