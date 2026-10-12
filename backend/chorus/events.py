"""Job events from the workers to the browser, through a Redis channel the SSE endpoint reads."""

import json
from collections.abc import AsyncIterator
from functools import lru_cache

import redis
import redis.asyncio as aioredis

from chorus.config import get_settings

CHANNEL = "chorus:events"


@lru_cache
def _client() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url)


def publish(event: str, data: dict) -> None:
    _client().publish(CHANNEL, json.dumps({"event": event, "data": data}))


async def subscribe() -> AsyncIterator[dict]:
    """Yield every event published from now on, until the caller stops iterating."""
    client = aioredis.Redis.from_url(get_settings().redis_url)
    pubsub = client.pubsub()
    await pubsub.subscribe(CHANNEL)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                yield json.loads(message["data"])
    finally:
        await pubsub.aclose()
        await client.aclose()
