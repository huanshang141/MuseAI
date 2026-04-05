import json
from typing import Any

from redis.asyncio import Redis


class RedisCache:
    def __init__(self, redis_url: str):
        self.client = Redis.from_url(redis_url)

    @classmethod
    def from_url(cls, redis_url: str) -> "RedisCache":
        return cls(redis_url)

    async def close(self) -> None:
        await self.client.close()

    async def get_session_context(self, session_id: str) -> list[dict] | None:
        key = f"session:{session_id}:context"
        data = await self.client.get(key)
        return json.loads(data) if data else None

    async def set_session_context(self, session_id: str, messages: list[dict], ttl: int = 3600) -> None:
        key = f"session:{session_id}:context"
        await self.client.setex(key, ttl, json.dumps(messages))

    async def delete_session_context(self, session_id: str) -> None:
        key = f"session:{session_id}:context"
        await self.client.delete(key)

    async def get_embedding(self, text_hash: str) -> list[float] | None:
        key = f"embed:{text_hash}"
        data = await self.client.get(key)
        return json.loads(data) if data else None

    async def set_embedding(self, text_hash: str, embedding: list[float], ttl: int = 86400) -> None:
        key = f"embed:{text_hash}"
        await self.client.setex(key, ttl, json.dumps(embedding))

    async def get_retrieval(self, query_hash: str) -> list[dict] | None:
        key = f"retrieve:{query_hash}"
        data = await self.client.get(key)
        return json.loads(data) if data else None

    async def set_retrieval(self, query_hash: str, results: list[dict], ttl: int = 600) -> None:
        key = f"retrieve:{query_hash}"
        await self.client.setex(key, ttl, json.dumps(results))

    async def check_rate_limit(self, user_id: str, max_requests: int = 60) -> bool:
        key = f"rate:{user_id}"
        first_request = await self.client.set(key, 1, ex=60, nx=True)
        if first_request:
            return True
        count = await self.client.incr(key)
        return count <= max_requests

    async def get_rate_limit_count(self, user_id: str) -> int:
        key = f"rate:{user_id}"
        count = await self.client.get(key)
        return int(count) if count else 0


def create_redis_client(redis_url: str) -> RedisCache:
    return RedisCache(redis_url)
