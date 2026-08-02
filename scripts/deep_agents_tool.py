from typing import Any

from langchain_core.tools import tool

from knowledge_base_client import KnowledgeBaseClient


def build_search_tool(client: KnowledgeBaseClient):
    @tool
    async def search_knowledge(
        query: str, knowledge_base_ids: list[str], top_k: int = 8
    ) -> list[dict[str, Any]]:
        """Search only knowledge bases explicitly supplied by the caller."""
        result = await client.search(query, knowledge_base_ids, top_k)
        return list(result["items"])

    return search_knowledge
