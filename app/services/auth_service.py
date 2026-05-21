from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.role import RoleKey
from app.models.user import User, UserStatus
from app.models.verification_code import VerificationCodePurpose
from app.schemas.auth import (
    AuthMessageResponse,
    EmailRequest,
    EmailVerificationRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.services.email_service import (
    password_reset_email_body,
    send_email,
    verification_email_body,
)
from app.services.role_service import get_role_by_key
from app.services.verification_service import (
    consume_verification_code,
    create_verification_code,
)


async def register_user(db: Session, payload: RegisterRequest) -> AuthMessageResponse:
    return await _register_user_with_role(db, payload, RoleKey.USER)


async def register_super_admin(
    db: Session,
    payload: RegisterRequest,
) -> AuthMessageResponse:
    return await _register_user_with_role(db, payload, RoleKey.SUPER_ADMIN)


async def _register_user_with_role(
    db: Session,
    payload: RegisterRequest,
    role_key: RoleKey,
) -> AuthMessageResponse:
    email = payload.email.lower().strip()
    existing_user = db.query(User).filter(User.email == email).one_or_none()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        )

    user_role = get_role_by_key(db, role_key)
    user = User(
        name=payload.name.strip(),
        email=email,
        hashed_password=hash_password(payload.password),
        status=UserStatus.PENDING,
        role_id=user_role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    code = create_verification_code(
        db,
        user=user,
        purpose=VerificationCodePurpose.EMAIL_VERIFICATION,
    )
    await send_email(
        db,
        to_email=user.email,
        subject="Verify your Lux email",
        body=verification_email_body(code),
    )
    return AuthMessageResponse(
        message="Verification code sent. Please verify your email.",
        user=user,
    )


def authenticate_user(db: Session, payload: LoginRequest) -> TokenResponse:
    email = payload.email.lower().strip()
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if user.deleted_at is not None or user.status == UserStatus.DELETED:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is not available",
        )
    if user.status == UserStatus.BANNED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is banned",
        )
    if user.status == UserStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification is required",
        )
    return _token_response(user)


def verify_email(db: Session, payload: EmailVerificationRequest) -> TokenResponse:
    verification_code = consume_verification_code(
        db,
        email=payload.email,
        code=payload.code,
        purpose=VerificationCodePurpose.EMAIL_VERIFICATION,
    )
    user = verification_code.user
    if user.status == UserStatus.BANNED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is banned",
        )
    user.status = UserStatus.ACTIVE
    db.commit()
    db.refresh(user)
    return _token_response(user)


async def resend_verification_code(
    db: Session,
    payload: EmailRequest,
) -> AuthMessageResponse:
    user = _get_user_by_email(db, payload.email)
    if user.status == UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified",
        )
    if user.status in {UserStatus.BANNED, UserStatus.DELETED}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not available",
        )

    code = create_verification_code(
        db,
        user=user,
        purpose=VerificationCodePurpose.EMAIL_VERIFICATION,
    )
    await send_email(
        db,
        to_email=user.email,
        subject="Verify your Lux email",
        body=verification_email_body(code),
    )
    return AuthMessageResponse(message="Verification code sent.", user=user)


async def forgot_password(db: Session, payload: EmailRequest) -> AuthMessageResponse:
    email = payload.email.lower().strip()
    user = db.query(User).filter(User.email == email).one_or_none()
    generic_response = AuthMessageResponse(
        message="If the email exists, a password reset code has been sent."
    )
    if user is None or user.status != UserStatus.ACTIVE:
        return generic_response

    code = create_verification_code(
        db,
        user=user,
        purpose=VerificationCodePurpose.PASSWORD_RESET,
    )
    await send_email(
        db,
        to_email=user.email,
        subject="Reset your Lux password",
        body=password_reset_email_body(code),
    )
    return generic_response


def reset_password(db: Session, payload: ResetPasswordRequest) -> AuthMessageResponse:
    verification_code = consume_verification_code(
        db,
        email=payload.email,
        code=payload.code,
        purpose=VerificationCodePurpose.PASSWORD_RESET,
    )
    user = verification_code.user
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not available",
        )
    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return AuthMessageResponse(message="Password reset successfully.")


def soft_delete_user(db: Session, user: User) -> User:
    user.status = UserStatus.DELETED
    user.deleted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(subject=user.id),
        user=user,
    )


def _get_user_by_email(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email.lower().strip()).one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
