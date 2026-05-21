from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from functools import lru_cache
from time import perf_counter
from typing import Protocol

from fastapi import HTTPException, status
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings
from app.models.chat import ChatMessageRole


class ChatContextMessage(Protocol):
    role: ChatMessageRole
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass
class LLMStreamChunk:
    """Yielded during streaming. `done=True` on the final chunk with full metadata."""

    content: str
    done: bool = False
    model: str = ""
    latency_ms: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


def ensure_llm_configured() -> None:
    if not settings.google_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not configured",
        )


async def generate_assistant_reply(
    history: list[ChatContextMessage],
    model: str | None = None,
) -> LLMResponse:
    ensure_llm_configured()
    model_name = _normalize_model_name(model)
    try:
        started_at = perf_counter()
        response = await _get_gemini_model(model_name).ainvoke(
            _to_langchain_messages(history)
        )
        latency_ms = int((perf_counter() - started_at) * 1000)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service failed",
        ) from exc

    content = _string_content(response.content)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service returned an empty response",
        )
    usage = _token_usage(response)
    return LLMResponse(
        content=content,
        model=model_name,
        latency_ms=latency_ms,
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        total_tokens=usage.get("total_tokens"),
    )


async def stream_assistant_reply(
    history: list[ChatContextMessage],
    model: str | None = None,
) -> AsyncIterator[LLMStreamChunk]:
    """Yield content chunks as they arrive, then a final done=True chunk with metadata."""
    ensure_llm_configured()
    model_name = _normalize_model_name(model)
    langchain_messages = _to_langchain_messages(history)
    collected: list[str] = []
    started_at = perf_counter()

    try:
        async for chunk in _get_gemini_model(model_name).astream(langchain_messages):
            text = _string_content(chunk.content)
            if text:
                collected.append(text)
                yield LLMStreamChunk(content=text)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service failed",
        ) from exc

    full_content = "".join(collected)
    if not full_content:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service returned an empty response",
        )

    latency_ms = int((perf_counter() - started_at) * 1000)
    yield LLMStreamChunk(
        content=full_content,
        done=True,
        model=model_name,
        latency_ms=latency_ms,
    )


@lru_cache
def _get_gemini_model(model_name: str) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=settings.gemini_temperature,
        api_key=settings.google_api_key,
    )


def _normalize_model_name(model: str | None) -> str:
    if model is None or not model.strip():
        model_name = settings.default_gemini_model
    else:
        model_name = model.strip()

    if model_name not in settings.gemini_allowed_models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gemini model is not allowed",
        )
    return model_name


def _to_langchain_messages(history: list[ChatContextMessage]) -> list[BaseMessage]:
    messages: list[BaseMessage] = [SystemMessage(content=settings.chat_system_prompt)]
    for message in history[-settings.chat_context_message_limit :]:
        if message.role == ChatMessageRole.USER:
            messages.append(HumanMessage(content=message.content))
        elif message.role == ChatMessageRole.ASSISTANT:
            messages.append(AIMessage(content=message.content))
        else:
            messages.append(SystemMessage(content=message.content))
    return messages


def _string_content(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts).strip()
    return str(content).strip()


def _token_usage(response: object) -> dict[str, int | None]:
    usage = getattr(response, "usage_metadata", None) or {}
    if not isinstance(usage, dict):
        return {}

    return {
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }
