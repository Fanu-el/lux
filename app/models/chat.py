from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, UUIDPrimaryKeyMixin


class ChatSessionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class ChatMessageRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class ChatMessageStatus(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ChatSession(UUIDPrimaryKeyMixin, AuditMixin, Base):
    __tablename__ = "chat_sessions"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(160), default="New chat", nullable=False)
    status: Mapped[ChatSessionStatus] = mapped_column(
        Enum(ChatSessionStatus, name="chat_session_status"),
        default=ChatSessionStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    user = relationship("User", back_populates="chat_sessions")
    messages = relationship(
        "ChatMessage",
        back_populates="session",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(UUIDPrimaryKeyMixin, AuditMixin, Base):
    __tablename__ = "chat_messages"

    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chat_sessions.id"),
        nullable=False,
        index=True,
    )
    role: Mapped[ChatMessageRole] = mapped_column(
        Enum(ChatMessageRole, name="chat_message_role"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ChatMessageStatus] = mapped_column(
        Enum(ChatMessageStatus, name="chat_message_status"),
        default=ChatMessageStatus.COMPLETED,
        nullable=False,
        index=True,
    )
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    session = relationship("ChatSession", back_populates="messages")
