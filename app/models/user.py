from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, UUIDPrimaryKeyMixin


class UserStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    BANNED = "BANNED"
    DELETED = "DELETED"


class User(UUIDPrimaryKeyMixin, AuditMixin, Base):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"),
        default=UserStatus.PENDING,
        nullable=False,
        index=True,
    )
    role_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("roles.id"),
        nullable=False,
    )

    role = relationship("Role", back_populates="users")
    verification_codes = relationship("VerificationCode", back_populates="user")
