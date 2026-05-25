from enum import StrEnum

from sqlalchemy import Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, UUIDPrimaryKeyMixin


class EmailStatus(StrEnum):
    SENT = "SENT"
    FAILED = "FAILED"


class Email(UUIDPrimaryKeyMixin, AuditMixin, Base):
    __tablename__ = "emails"

    to_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[EmailStatus] = mapped_column(
        Enum(EmailStatus, name="email_status"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(80), default="fastapi-mail")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
