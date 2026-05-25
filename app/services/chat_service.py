import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatMessageRole, ChatMessageStatus, ChatSession
from app.models.user import User
from app.schemas.chat import (
    ChatMessageCreateRequest,
    ChatExchangeResponse,
    ChatSessionCreateRequest,
    ChatSessionUpdateRequest,
)
from app.services.chat_memory_service import (
    append_chat_memory,
    clear_chat_memory,
    get_chat_memory,
    hydrate_chat_memory,
)
from app.services.llm_service import generate_assistant_reply, stream_assistant_reply


def list_user_chat_sessions(db: Session, user: User) -> list[ChatSession]:
    return (
        db.query(ChatSession)
        .filter(
            ChatSession.user_id == user.id,
            ChatSession.deleted_at.is_(None),
        )
        .order_by(ChatSession.updated_at.desc())
        .all()
    )


def list_all_chat_sessions(db: Session) -> list[ChatSession]:
    return (
        db.query(ChatSession)
        .filter(ChatSession.deleted_at.is_(None))
        .order_by(ChatSession.updated_at.desc())
        .all()
    )


def create_chat_session(
    db: Session,
    user: User,
    payload: ChatSessionCreateRequest,
) -> ChatSession:
    title = payload.title.strip() if payload.title else "New chat"
    session = ChatSession(user_id=user.id, title=title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_user_chat_session(db: Session, user: User, session_id: str) -> ChatSession:
    session = db.get(ChatSession, session_id)
    if (
        session is None
        or session.deleted_at is not None
        or session.user_id != user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    return session


def list_user_chat_messages(
    db: Session,
    user: User,
    session_id: str,
) -> list[ChatMessage]:
    session = get_user_chat_session(db, user, session_id)
    return _list_session_messages(db, session.id)


def _list_session_messages(db: Session, session_id: str) -> list[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(
            ChatMessage.session_id == session_id,
            ChatMessage.deleted_at.is_(None),
        )
        .order_by(ChatMessage.created_at)
        .all()
    )


def get_chat_session_or_404(db: Session, session_id: str) -> ChatSession:
    session = db.get(ChatSession, session_id)
    if session is None or session.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    return session


def update_chat_session(
    db: Session,
    user: User,
    session_id: str,
    payload: ChatSessionUpdateRequest,
) -> ChatSession:
    session = get_user_chat_session(db, user, session_id)
    session.title = payload.title.strip()
    db.commit()
    db.refresh(session)
    return session


async def soft_delete_chat_session(db: Session, user: User, session_id: str) -> None:
    session = get_user_chat_session(db, user, session_id)
    now = datetime.now(timezone.utc)
    session.deleted_at = now
    for message in session.messages:
        message.deleted_at = now
    db.commit()
    await clear_chat_memory(session.id)


async def create_chat_exchange(
    db: Session,
    user: User,
    session_id: str,
    payload: ChatMessageCreateRequest,
    model: str | None = None,
) -> ChatExchangeResponse:
    # Validate model and API key before touching the DB
    from app.services.llm_service import _resolve_and_validate
    _resolve_and_validate(model)

    session = get_user_chat_session(db, user, session_id)
    existing_history = _list_session_messages(db, session.id)
    await hydrate_chat_memory(session.id, existing_history)

    user_message = ChatMessage(
        session_id=session.id,
        role=ChatMessageRole.USER,
        content=payload.content.strip(),
    )
    db.add(user_message)
    if not existing_history and session.title == "New chat":
        session.title = _title_from_message(user_message.content)
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user_message)

    await append_chat_memory(session.id, user_message)
    history = await get_chat_memory(session.id)
    if not history:
        history = [*existing_history, user_message]

    try:
        llm_response = await generate_assistant_reply(history, model=model)
    except HTTPException as exc:
        # Only save a failed message for actual LLM errors (502), not config errors (400/503)
        if exc.status_code == status.HTTP_502_BAD_GATEWAY:
            _save_failed_assistant_message(db, session, exc.detail)
        raise

    assistant_message = ChatMessage(
        session_id=session.id,
        role=ChatMessageRole.ASSISTANT,
        content=llm_response.content,
        model=llm_response.model,
        latency_ms=llm_response.latency_ms,
        input_tokens=llm_response.input_tokens,
        output_tokens=llm_response.output_tokens,
        total_tokens=llm_response.total_tokens,
    )
    db.add(assistant_message)
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(assistant_message)
    await append_chat_memory(session.id, assistant_message)
    return ChatExchangeResponse(
        user_message=user_message,
        assistant_message=assistant_message,
    )


def _save_failed_assistant_message(
    db: Session,
    session: ChatSession,
    error_detail: object,
) -> None:
    assistant_message = ChatMessage(
        session_id=session.id,
        role=ChatMessageRole.ASSISTANT,
        content="The AI service could not respond. Please try again.",
        status=ChatMessageStatus.FAILED,
        error_message=str(error_detail),
    )
    db.add(assistant_message)
    session.updated_at = datetime.now(timezone.utc)
    db.commit()


def _title_from_message(content: str) -> str:
    title = " ".join(content.split())
    if len(title) <= 60:
        return title or "New chat"
    return f"{title[:57].rstrip()}..."


async def stream_chat_exchange(
    db: Session,
    user: User,
    session_id: str,
    payload: ChatMessageCreateRequest,
    model: str | None = None,
) -> AsyncIterator[str]:
    """
    Yields SSE-formatted lines. Each content chunk is:
        data: {"type":"chunk","content":"..."}

    The final event is:
        data: {"type":"done","user_message":{...},"assistant_message":{...}}

    On error:
        data: {"type":"error","detail":"..."}
    """
    # Validate model and API key before touching the DB
    from app.services.llm_service import _resolve_and_validate
    try:
        _resolve_and_validate(model)
    except Exception as exc:
        detail = exc.detail if hasattr(exc, "detail") else "Configuration error"
        yield f"data: {json.dumps({'type': 'error', 'detail': str(detail)})}\n\n"
        return

    session = get_user_chat_session(db, user, session_id)
    existing_history = _list_session_messages(db, session.id)
    await hydrate_chat_memory(session.id, existing_history)

    user_message = ChatMessage(
        session_id=session.id,
        role=ChatMessageRole.USER,
        content=payload.content.strip(),
    )
    db.add(user_message)
    if not existing_history and session.title == "New chat":
        session.title = _title_from_message(user_message.content)
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user_message)

    await append_chat_memory(session.id, user_message)
    history = await get_chat_memory(session.id)
    if not history:
        history = [*existing_history, user_message]

    try:
        full_content = ""
        final_chunk = None
        async for chunk in stream_assistant_reply(history, model=model):
            if chunk.done:
                final_chunk = chunk
            else:
                full_content += chunk.content
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk.content})}\n\n"

        assistant_message = ChatMessage(
            session_id=session.id,
            role=ChatMessageRole.ASSISTANT,
            content=final_chunk.content if final_chunk else full_content,
            model=final_chunk.model if final_chunk else model,
            latency_ms=final_chunk.latency_ms if final_chunk else None,
        )
        db.add(assistant_message)
        session.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(assistant_message)
        await append_chat_memory(session.id, assistant_message)

        from app.schemas.chat import ChatMessagePublic
        yield (
            f"data: {json.dumps({'type': 'done', 'user_message': ChatMessagePublic.model_validate(user_message).model_dump(mode='json'), 'assistant_message': ChatMessagePublic.model_validate(assistant_message).model_dump(mode='json')})}\n\n"
        )

    except Exception as exc:
        detail = exc.detail if hasattr(exc, "detail") else "Streaming failed"
        _save_failed_assistant_message(db, session, detail)
        yield f"data: {json.dumps({'type': 'error', 'detail': str(detail)})}\n\n"
