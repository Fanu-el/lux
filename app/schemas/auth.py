from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserPublic


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class AuthMessageResponse(BaseModel):
    message: str
    user: UserPublic | None = None


class EmailVerificationRequest(BaseModel):
    email: EmailStr = Field(max_length=255)
    code: str = Field(min_length=4, max_length=12)


class EmailRequest(BaseModel):
    email: EmailStr = Field(max_length=255)


class ResetPasswordRequest(BaseModel):
    email: EmailStr = Field(max_length=255)
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(min_length=8, max_length=128)
