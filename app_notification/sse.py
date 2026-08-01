"""
SSE (Server-Sent Events) pour notifications temps réel.

Pub/sub Redis en parallèle du WebSocket Channels.
Générateur async compatible ASGI (Uvicorn).
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, Optional

import redis
import redis.asyncio as aioredis
from decouple import config

logger = logging.getLogger(__name__)

REDIS_URL = config("REDIS_URL", default="redis://localhost:6379")
# Ping fréquent : certains émulateurs (BlueStacks) coupent les HTTP idle trop tôt
SSE_KEEPALIVE_SECONDS = 12.0


def sse_user_channel(user_id: int) -> str:
    return f"sse:notifications:{user_id}"


def publish_notification_sse(user_id: int, payload: Dict[str, Any]) -> None:
    """Diffuse un événement aux abonnés SSE de l'utilisateur (sync, depuis Django)."""
    try:
        client = redis.from_url(REDIS_URL, decode_responses=True)
        client.publish(sse_user_channel(user_id), json.dumps(payload, default=str))
        client.close()
    except Exception as exc:
        logger.warning("Publication SSE ignorée (%s)", exc)


async def sse_event_generator(user_id: int) -> AsyncIterator[str]:
    """Générateur SSE async : heartbeat + messages Redis pub/sub."""
    client = aioredis.from_url(REDIS_URL, decode_responses=True)
    pubsub = client.pubsub()
    channel = sse_user_channel(user_id)
    await pubsub.subscribe(channel)

    yield ": connected\n\n"

    try:
        while True:
            message: Optional[dict] = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=SSE_KEEPALIVE_SECONDS,
            )
            if message is None:
                yield ": ping\n\n"
                continue
            if message.get("type") != "message":
                continue
            data = message.get("data")
            if not data:
                continue
            yield f"event: message\ndata: {data}\n\n"
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except Exception:
            pass
        try:
            await client.aclose()
        except Exception:
            pass
