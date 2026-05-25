from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.dependencies import requires_auth
from app.db.session import get_db
from app.models.user import User
from app.schemas.chat import (
    ChatExchangeResponse,
    ChatMessageCreateRequest,
    ChatMessagePublic,
    ChatSessionCreateRequest,
    ChatSessionPublic,
    ChatSessionUpdateRequest,
    ChatSessionWithMessages,
)
from app.schemas.response import ApiResponse, success_response
from app.services.chat_service import (
    create_chat_exchange,
    create_chat_session,
    get_user_chat_session,
    list_user_chat_messages,
    list_user_chat_sessions,
    soft_delete_chat_session,
    stream_chat_exchange,
    update_chat_session,
)

router = APIRouter(prefix="/chats", tags=["chats"])


@router.post("", response_model=ApiResponse[ChatSessionPublic], status_code=201)
def create_chat(
    payload: ChatSessionCreateRequest,
    current_user: User = Depends(requires_auth),
    db: Session = Depends(get_db),
):
    return success_response(create_chat_session(db, current_user, payload))


@router.get("", response_model=ApiResponse[list[ChatSessionPublic]])
def list_chats(
    current_user: User = Depends(requires_auth),
    db: Session = Depends(get_db),
):
    return success_response(list_user_chat_sessions(db, current_user))


@router.get("/{session_id}", response_model=ApiResponse[ChatSessionWithMessages])
def get_chat(
    session_id: str,
    current_user: User = Depends(requires_auth),
    db: Session = Depends(get_db),
):
    return success_response(get_user_chat_session(db, current_user, session_id))


@router.patch("/{session_id}", response_model=ApiResponse[ChatSessionPublic])
def update_chat(
    session_id: str,
    payload: ChatSessionUpdateRequest,
    current_user: User = Depends(requires_auth),
    db: Session = Depends(get_db),
):
    return success_response(update_chat_session(db, current_user, session_id, payload))


@router.delete("/{session_id}", response_model=ApiResponse[None])
async def delete_chat(
    session_id: str,
    current_user: User = Depends(requires_auth),
    db: Session = Depends(get_db),
):
    await soft_delete_chat_session(db, current_user, session_id)
    return success_response()


@router.get(
    "/{session_id}/messages",
    response_model=ApiResponse[list[ChatMessagePublic]],
)
def list_messages(
    session_id: str,
    current_user: User = Depends(requires_auth),
    db: Session = Depends(get_db),
):
    return success_response(list_user_chat_messages(db, current_user, session_id))


@router.post(
    "/{session_id}/messages",
    response_model=ApiResponse[ChatExchangeResponse],
    status_code=201,
)
async def create_message(
    session_id: str,
    payload: ChatMessageCreateRequest,
    llm_model: str | None = Header(default=None, alias="X-LLM-Model"),
    current_user: User = Depends(requires_auth),
    db: Session = Depends(get_db),
):
    return success_response(
        await create_chat_exchange(
            db,
            current_user,
            session_id,
            payload,
            model=llm_model,
        )
    )


@router.post(
    "/{session_id}/messages/stream",
    summary="Send a message and stream the assistant reply (SSE)",
)
async def stream_message(
    session_id: str,
    payload: ChatMessageCreateRequest,
    llm_model: str | None = Header(default=None, alias="X-LLM-Model"),
    current_user: User = Depends(requires_auth),
    db: Session = Depends(get_db),
):
    """
    Returns a Server-Sent Events stream.

    Each event is a JSON object on a `data:` line:
    - `{"type":"chunk","content":"..."}` — incremental text
    - `{"type":"done","user_message":{...},"assistant_message":{...}}` — final persisted messages
    - `{"type":"error","detail":"..."}` — on failure
    """
    return StreamingResponse(
        stream_chat_exchange(db, current_user, session_id, payload, model=llm_model),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
