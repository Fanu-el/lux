from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.chat import ChatMessageRole, ChatMessageStatus, ChatSessionStatus
from app.schemas.user import UserPublic


class ChatSessionCreateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)


class ChatSessionUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)


class ChatMessageCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class ChatMessagePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    role: ChatMessageRole
    content: str
    status: ChatMessageStatus
    model: str | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class ChatExchangeResponse(BaseModel):
    user_message: ChatMessagePublic
    assistant_message: ChatMessagePublic


class ChatSessionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    status: ChatSessionStatus
    created_at: datetime
    updated_at: datetime


class ChatSessionWithMessages(ChatSessionPublic):
    messages: list[ChatMessagePublic]


class AdminChatSessionPublic(ChatSessionPublic):
    user: UserPublic
