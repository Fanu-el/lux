from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import requires_auth
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    AuthMessageResponse,
    EmailRequest,
    EmailVerificationRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.schemas.response import ApiResponse, success_response
from app.schemas.user import UserPublic
from app.services.auth_service import (
    authenticate_user,
    forgot_password,
    register_super_admin,
    register_user,
    resend_verification_code,
    reset_password,
    verify_email,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=ApiResponse[AuthMessageResponse],
    status_code=201,
)
async def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    return success_response(await register_user(db, payload))


@router.post(
    "/register-super-admin",
    response_model=ApiResponse[AuthMessageResponse],
    status_code=201,
)
async def register_admin(payload: RegisterRequest, db: Session = Depends(get_db)):
    return success_response(await register_super_admin(db, payload))


@router.post("/login", response_model=ApiResponse[TokenResponse])
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return success_response(authenticate_user(db, payload))


@router.post("/verify-email", response_model=ApiResponse[TokenResponse])
def verify_email_address(
    payload: EmailVerificationRequest,
    db: Session = Depends(get_db),
):
    return success_response(verify_email(db, payload))


@router.post(
    "/resend-verification-code",
    response_model=ApiResponse[AuthMessageResponse],
)
async def resend_code(payload: EmailRequest, db: Session = Depends(get_db)):
    return success_response(await resend_verification_code(db, payload))


@router.post("/forgot-password", response_model=ApiResponse[AuthMessageResponse])
async def forgot(payload: EmailRequest, db: Session = Depends(get_db)):
    return success_response(await forgot_password(db, payload))


@router.post("/reset-password", response_model=ApiResponse[AuthMessageResponse])
def reset(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    return success_response(reset_password(db, payload))


@router.get("/me", response_model=ApiResponse[UserPublic])
def me(current_user: User = Depends(requires_auth)):
    return success_response(current_user)
