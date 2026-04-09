import json

from redis.asyncio import Redis

_RATE_LIMIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
if count > tonumber(ARGV[2]) then
    return 0
else
    return 1
end
"""


class RedisCache:
    def __init__(self, redis_url: str, max_connections: int = 50):
        from redis.asyncio import ConnectionPool

        pool = ConnectionPool.from_url(redis_url, max_connections=max_connections)
        self.client = Redis(connection_pool=pool)
        self._rate_limit_script = self.client.register_script(_RATE_LIMIT_SCRIPT)

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

    async def check_rate_limit(self, user_id: str, max_requests: int = 60, window_seconds: int = 60) -> bool:
        key = f"rate:{user_id}"
        result = await self._rate_limit_script(keys=[key], args=[str(window_seconds), str(max_requests)])
        return bool(result)

    async def get_rate_limit_count(self, user_id: str) -> int:
        key = f"rate:{user_id}"
        count = await self.client.get(key)
        return int(count) if count else 0

    async def blacklist_token(self, jti: str, ttl: int) -> None:
        key = f"blacklist:{jti}"
        await self.client.setex(key, ttl, "1")

    async def is_token_blacklisted(self, jti: str) -> bool:
        key = f"blacklist:{jti}"
        return await self.client.exists(key) > 0

    async def set_guest_session(self, session_id: str, messages: list[dict], ttl: int = 3600) -> None:
        key = f"guest:{session_id}:session"
        await self.client.setex(key, ttl, json.dumps(messages))

    async def get_guest_session(self, session_id: str) -> list[dict] | None:
        key = f"guest:{session_id}:session"
        data = await self.client.get(key)
        return json.loads(data) if data else None

    async def delete_guest_session(self, session_id: str) -> None:
        key = f"guest:{session_id}:session"
        await self.client.delete(key)


def create_redis_client(redis_url: str) -> RedisCache:
    return RedisCache(redis_url)
