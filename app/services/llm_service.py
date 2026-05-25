from collections.abc import AsyncIterator
from dataclasses import dataclass
from functools import lru_cache
from time import perf_counter
from typing import Protocol

from fastapi import HTTPException, status
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.core.config import settings
from app.models.chat import ChatMessageRole

# ---------------------------------------------------------------------------
# Supported providers
# ---------------------------------------------------------------------------

PROVIDER_GEMINI = "gemini"
PROVIDER_OPENAI = "openai"
PROVIDER_ANTHROPIC = "anthropic"

SUPPORTED_PROVIDERS = {PROVIDER_GEMINI, PROVIDER_OPENAI, PROVIDER_ANTHROPIC}


# ---------------------------------------------------------------------------
# Protocols / response types
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_assistant_reply(
    history: list[ChatContextMessage],
    model: str | None = None,
) -> LLMResponse:
    model_str = _resolve_and_validate(model)
    provider, model_name = _parse_model_str(model_str)
    llm = _get_llm_model(provider, model_name)

    try:
        started_at = perf_counter()
        response = await llm.ainvoke(_to_langchain_messages(history))
        latency_ms = int((perf_counter() - started_at) * 1000)
    except HTTPException:
        raise
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
        model=model_str,
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
    model_str = _resolve_and_validate(model)
    provider, model_name = _parse_model_str(model_str)
    llm = _get_llm_model(provider, model_name)
    langchain_messages = _to_langchain_messages(history)
    collected: list[str] = []
    started_at = perf_counter()

    try:
        async for chunk in llm.astream(langchain_messages):
            text = _string_content(chunk.content)
            if text:
                collected.append(text)
                yield LLMStreamChunk(content=text)
    except HTTPException:
        raise
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
        model=model_str,
        latency_ms=latency_ms,
    )


# ---------------------------------------------------------------------------
# Model factory
# ---------------------------------------------------------------------------

@lru_cache
def _get_llm_model(provider: str, model_name: str) -> BaseChatModel:
    if provider == PROVIDER_GEMINI:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=settings.llm_temperature,
            api_key=settings.google_api_key,
        )
    if provider == PROVIDER_OPENAI:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name,
            temperature=settings.llm_temperature,
            api_key=settings.openai_api_key,
        )
    if provider == PROVIDER_ANTHROPIC:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model_name,
            temperature=settings.llm_temperature,
            api_key=settings.anthropic_api_key,
        )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported LLM provider: '{provider}'. Supported: {sorted(SUPPORTED_PROVIDERS)}",
    )


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _resolve_and_validate(model: str | None) -> str:
    model_str = _resolve_model_str(model)
    if model_str not in settings.llm_allowed_models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model '{model_str}' is not in the allowed models list",
        )
    provider, _ = _parse_model_str(model_str)
    _check_api_key(provider)
    return model_str


def _resolve_model_str(model: str | None) -> str:
    """Return the model string to use, falling back to the configured default."""
    if model and model.strip():
        return model.strip()
    return settings.default_llm_model


def _parse_model_str(model_str: str) -> tuple[str, str]:
    """
    Parse 'provider/model-name' into (provider, model_name).
    Raises 400 if the format is wrong or the provider is unsupported.
    """
    if "/" not in model_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid model format '{model_str}'. "
                "Expected 'provider/model-name', e.g. 'gemini/gemini-2.5-flash'."
            ),
        )
    provider, model_name = model_str.split("/", 1)
    provider = provider.strip().lower()
    model_name = model_name.strip()
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider '{provider}'. Supported: {sorted(SUPPORTED_PROVIDERS)}",
        )
    return provider, model_name


def _check_api_key(provider: str) -> None:
    key_map = {
        PROVIDER_GEMINI: settings.google_api_key,
        PROVIDER_OPENAI: settings.openai_api_key,
        PROVIDER_ANTHROPIC: settings.anthropic_api_key,
    }
    if not key_map.get(provider):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"API key for provider '{provider}' is not configured",
        )


# ---------------------------------------------------------------------------
# LangChain message conversion
# ---------------------------------------------------------------------------

def _to_langchain_messages(history: list[ChatContextMessage]) -> list[BaseMessage]:
    messages: list[BaseMessage] = [SystemMessage(content=settings.chat_system_prompt)]
    for message in history[-settings.chat_context_message_limit:]:
        if message.role == ChatMessageRole.USER:
            messages.append(HumanMessage(content=message.content))
        elif message.role == ChatMessageRole.ASSISTANT:
            messages.append(AIMessage(content=message.content))
        else:
            messages.append(SystemMessage(content=message.content))
    return messages


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

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
    # LangChain exposes usage differently per provider — try both shapes
    usage = getattr(response, "usage_metadata", None) or {}
    if not isinstance(usage, dict):
        # OpenAI / Anthropic shape via response_metadata
        meta = getattr(response, "response_metadata", {}) or {}
        token_usage = meta.get("token_usage") or meta.get("usage") or {}
        return {
            "input_tokens": token_usage.get("prompt_tokens") or token_usage.get("input_tokens"),
            "output_tokens": token_usage.get("completion_tokens") or token_usage.get("output_tokens"),
            "total_tokens": token_usage.get("total_tokens"),
        }
    return {
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }
