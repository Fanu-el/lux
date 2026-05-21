import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.core.config import settings
from app.models.chat import ChatMessage, ChatMessageRole


@dataclass
class ChatMemoryMessage:
    role: ChatMessageRole
    content: str


async def hydrate_chat_memory(
    session_id: str,
    messages: list[ChatMessage],
) -> None:
    client = _get_redis_client()
    if client is None:
        return

    try:
        key = _chat_memory_key(session_id)
        if await client.llen(key) > 0:
            await client.expire(key, settings.chat_memory_ttl_seconds)
            return

        encoded_messages = [
            _encode_message(message)
            for message in messages[-settings.chat_context_message_limit :]
        ]
        if encoded_messages:
            await client.rpush(key, *encoded_messages)
        await client.expire(key, settings.chat_memory_ttl_seconds)
    except Exception:
        return


async def append_chat_memory(session_id: str, message: ChatMessage) -> None:
    client = _get_redis_client()
    if client is None:
        return

    try:
        key = _chat_memory_key(session_id)
        await client.rpush(key, _encode_message(message))
        await client.ltrim(key, -settings.chat_context_message_limit, -1)
        await client.expire(key, settings.chat_memory_ttl_seconds)
    except Exception:
        return


async def get_chat_memory(session_id: str) -> list[ChatMemoryMessage]:
    client = _get_redis_client()
    if client is None:
        return []

    try:
        key = _chat_memory_key(session_id)
        raw_messages = await client.lrange(
            key,
            -settings.chat_context_message_limit,
            -1,
        )
        await client.expire(key, settings.chat_memory_ttl_seconds)
    except Exception:
        return []

    messages = []
    for raw_message in raw_messages:
        message = _decode_message(raw_message)
        if message is not None:
            messages.append(message)
    return messages


async def clear_chat_memory(session_id: str) -> None:
    client = _get_redis_client()
    if client is None:
        return

    try:
        await client.delete(_chat_memory_key(session_id))
    except Exception:
        return


@lru_cache
def _get_redis_client() -> Any | None:
    if not settings.redis_url:
        return None

    try:
        from redis.asyncio import Redis
    except ImportError:
        return None

    return Redis.from_url(settings.redis_url, decode_responses=True)


def _chat_memory_key(session_id: str) -> str:
    return f"lux:chat:{session_id}:memory"


def _encode_message(message: ChatMessage) -> str:
    return json.dumps(
        {
            "role": message.role.value,
            "content": message.content,
        },
        separators=(",", ":"),
    )


def _decode_message(raw_message: str) -> ChatMemoryMessage | None:
    try:
        payload = json.loads(raw_message)
        role = ChatMessageRole(payload["role"])
        content = payload["content"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None

    if not isinstance(content, str):
        return None
    return ChatMemoryMessage(role=role, content=content)
