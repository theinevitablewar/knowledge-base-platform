import json
from typing import Any, cast

from redis.asyncio import Redis


class RedisCache:
    def __init__(self, url: str) -> None:
        self.client = Redis.from_url(url, decode_responses=True)

    async def get_json(self, key: str) -> dict[str, Any] | None:
        value = await self.client.get(key)
        return cast(dict[str, Any], json.loads(value)) if value else None

    async def set_json(self, key: str, value: dict[str, Any], ttl: int = 300) -> None:
        await self.client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)

    async def invalidate_prefix(self, prefix: str) -> None:
        async for key in self.client.scan_iter(f"{prefix}*"):
            await self.client.delete(key)
