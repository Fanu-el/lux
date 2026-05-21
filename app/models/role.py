from enum import StrEnum

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, UUIDPrimaryKeyMixin


class RoleKey(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    USER = "USER"


class Role(UUIDPrimaryKeyMixin, AuditMixin, Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    key: Mapped[RoleKey] = mapped_column(
        Enum(RoleKey, name="role_key"),
        unique=True,
        nullable=False,
        index=True,
    )

    users = relationship("User", back_populates="role")

