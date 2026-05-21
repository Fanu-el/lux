from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.role import Role, RoleKey
from app.models.user import User, UserStatus

DEFAULT_ROLES = {
    RoleKey.SUPER_ADMIN: "Super Admin",
    RoleKey.USER: "User",
}


def seed_default_roles(db: Session) -> None:
    for key, name in DEFAULT_ROLES.items():
        role = db.query(Role).filter(Role.key == key).one_or_none()
        if role is None:
            db.add(Role(name=name, key=key))
    db.commit()


def seed_default_super_admin(db: Session) -> None:
    if not settings.super_admin_email or not settings.super_admin_password:
        return

    email = settings.super_admin_email.lower().strip()
    existing_user = db.query(User).filter(User.email == email).one_or_none()
    if existing_user is not None:
        return

    super_admin_role = get_role_by_key(db, RoleKey.SUPER_ADMIN)
    db.add(
        User(
            name=settings.super_admin_name or "Super Admin",
            email=email,
            hashed_password=hash_password(settings.super_admin_password),
            status=UserStatus.ACTIVE,
            role_id=super_admin_role.id,
        )
    )
    db.commit()


def get_role_by_key(db: Session, key: RoleKey) -> Role:
    role = db.query(Role).filter(Role.key == key, Role.deleted_at.is_(None)).one()
    return role
