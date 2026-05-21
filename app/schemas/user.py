from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.role import RoleKey
from app.models.user import UserStatus


class RolePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    key: RoleKey


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    status: UserStatus
    role: RolePublic
    created_at: datetime
    updated_at: datetime


class UpdateProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
