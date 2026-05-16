"""Redis-backed session store for multi-instance deployments."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from interview_simulator.engineering.session_codec import decode_session, encode_session

if TYPE_CHECKING:
    from interview_simulator.engineering.service import SessionRecord


class RedisSessionStore:
    """Persist sessions as JSON strings under ``{prefix}{session_id}``."""

    def __init__(
        self,
        redis_url: str,
        *,
        ttl_seconds: int = 86_400,
        key_prefix: str = "interview:session:",
        client: Any | None = None,
    ) -> None:
        self._redis_url = redis_url
        self._ttl_seconds = ttl_seconds
        self._prefix = key_prefix
        self._client = client
        self._owns_client = client is None

    @classmethod
    def from_client(
        cls,
        client: Any,
        *,
        ttl_seconds: int = 86_400,
        key_prefix: str = "interview:session:",
    ) -> RedisSessionStore:
        return cls(
            redis_url="",
            ttl_seconds=ttl_seconds,
            key_prefix=key_prefix,
            client=client,
        )

    def _key(self, session_id: str) -> str:
        return f"{self._prefix}{session_id}"

    async def connect(self) -> None:
        if self._client is not None:
            return
        from redis import asyncio as aioredis

        self._client = aioredis.from_url(self._redis_url, decode_responses=True)

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
        self._client = None

    async def ping(self) -> bool:
        if self._client is None:
            await self.connect()
        assert self._client is not None
        return bool(await self._client.ping())

    async def put(self, session: SessionRecord) -> None:
        if self._client is None:
            await self.connect()
        assert self._client is not None
        payload = encode_session(session)
        await self._client.set(self._key(session.session_id), payload, ex=self._ttl_seconds)

    async def get(self, session_id: str) -> SessionRecord | None:
        if self._client is None:
            await self.connect()
        assert self._client is not None
        raw = await self._client.get(self._key(session_id))
        if raw is None:
            return None
        return decode_session(raw)

    async def delete(self, session_id: str) -> None:
        if self._client is None:
            await self.connect()
        assert self._client is not None
        await self._client.delete(self._key(session_id))


__all__ = ["RedisSessionStore"]
