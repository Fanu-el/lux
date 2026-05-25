from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.role import RoleKey
from app.models.user import User, UserStatus
from app.schemas.user import UpdateProfileRequest
from app.services.email_service import (
    account_banned_email_body,
    account_reactivated_email_body,
    send_email,
)


def list_users(db: Session) -> list[User]:
    return db.query(User).filter(User.deleted_at.is_(None)).order_by(User.created_at).all()


def get_user_or_404(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None or user.status == UserStatus.DELETED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def update_user_profile(
    db: Session,
    user: User,
    payload: UpdateProfileRequest,
) -> User:
    user.name = payload.name.strip()
    db.commit()
    db.refresh(user)
    return user


async def ban_user(db: Session, user_id: str) -> User:
    user = get_user_or_404(db, user_id)
    if user.role and user.role.key == RoleKey.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin users cannot be banned",
        )

    was_banned = user.status == UserStatus.BANNED
    user.status = UserStatus.BANNED
    db.commit()
    db.refresh(user)
    if not was_banned:
        await send_email(
            db,
            to_email=user.email,
            subject="Your Lux account has been banned",
            body=account_banned_email_body(),
        )
    return user


async def unban_user(db: Session, user_id: str) -> User:
    user = get_user_or_404(db, user_id)
    was_banned = user.status == UserStatus.BANNED
    user.status = UserStatus.ACTIVE
    db.commit()
    db.refresh(user)
    if was_banned:
        await send_email(
            db,
            to_email=user.email,
            subject="Your Lux account has been reactivated",
            body=account_reactivated_email_body(),
        )
    return user
