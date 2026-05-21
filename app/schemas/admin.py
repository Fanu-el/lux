from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.email import EmailStatus
from app.models.verification_code import VerificationCodePurpose


class EmailPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    to_email: str
    subject: str
    body: str
    status: EmailStatus
    provider: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class VerificationCodePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    email: str
    purpose: VerificationCodePurpose
    expires_at: datetime
    consumed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class AnalyticsResponse(BaseModel):
    total_chat_sessions: int
    total_messages: int
    active_users: int
    failed_ai_calls: int
