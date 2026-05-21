import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.models.verification_code import (
    VerificationCode,
    VerificationCodePurpose,
)


def create_verification_code(
    db: Session,
    user: User,
    purpose: VerificationCodePurpose,
) -> str:
    _enforce_resend_cooldown(db, user=user, purpose=purpose)
    _expire_existing_codes(db, user=user, purpose=purpose)
    code = _generate_numeric_code(settings.verification_code_length)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=_expiry_minutes_for(purpose)
    )
    db.add(
        VerificationCode(
            user_id=user.id,
            email=user.email,
            code_hash=hash_password(code),
            purpose=purpose,
            expires_at=expires_at,
        )
    )
    db.commit()
    return code


def consume_verification_code(
    db: Session,
    email: str,
    code: str,
    purpose: VerificationCodePurpose,
) -> VerificationCode:
    normalized_email = email.lower().strip()
    now = datetime.now(timezone.utc)
    verification_codes = (
        db.query(VerificationCode)
        .filter(
            VerificationCode.email == normalized_email,
            VerificationCode.purpose == purpose,
            VerificationCode.consumed_at.is_(None),
            VerificationCode.deleted_at.is_(None),
        )
        .order_by(VerificationCode.created_at.desc())
        .all()
    )

    for verification_code in verification_codes:
        expires_at = _ensure_aware_datetime(verification_code.expires_at)
        if expires_at < now:
            continue
        if verify_password(code, verification_code.code_hash):
            verification_code.consumed_at = now
            db.commit()
            db.refresh(verification_code)
            return verification_code

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired verification code",
    )


def _expire_existing_codes(
    db: Session,
    user: User,
    purpose: VerificationCodePurpose,
) -> None:
    db.query(VerificationCode).filter(
        VerificationCode.user_id == user.id,
        VerificationCode.purpose == purpose,
        VerificationCode.consumed_at.is_(None),
    ).update({VerificationCode.consumed_at: datetime.now(timezone.utc)})
    db.commit()


def _enforce_resend_cooldown(
    db: Session,
    user: User,
    purpose: VerificationCodePurpose,
) -> None:
    latest_code = (
        db.query(VerificationCode)
        .filter(
            VerificationCode.user_id == user.id,
            VerificationCode.purpose == purpose,
            VerificationCode.consumed_at.is_(None),
            VerificationCode.deleted_at.is_(None),
        )
        .order_by(VerificationCode.created_at.desc())
        .first()
    )
    if latest_code is None:
        return

    cooldown_seconds = settings.verification_code_resend_cooldown_seconds
    if cooldown_seconds <= 0:
        return

    now = datetime.now(timezone.utc)
    created_at = _ensure_aware_datetime(latest_code.created_at)
    can_resend_at = created_at + timedelta(seconds=cooldown_seconds)
    if can_resend_at <= now:
        return

    retry_after_seconds = max(1, int((can_resend_at - now).total_seconds()))
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Please wait {retry_after_seconds} seconds before requesting a new code",
        headers={"Retry-After": str(retry_after_seconds)},
    )


def _generate_numeric_code(length: int) -> str:
    start = 10 ** (length - 1)
    end = (10**length) - 1
    return str(secrets.randbelow(end - start + 1) + start)


def _expiry_minutes_for(purpose: VerificationCodePurpose) -> int:
    if purpose == VerificationCodePurpose.PASSWORD_RESET:
        return settings.password_reset_code_expires_in_minute
    return settings.verification_code_expires_in_minute


def _ensure_aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
