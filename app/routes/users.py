from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import requires_auth, requires_super_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.response import ApiResponse, success_response
from app.schemas.user import UpdateProfileRequest, UserPublic
from app.services.user_service import (
    ban_user,
    list_users,
    unban_user,
    update_user_profile,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/update-profile", response_model=ApiResponse[UserPublic])
def update_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(requires_auth),
    db: Session = Depends(get_db),
):
    return success_response(update_user_profile(db, current_user, payload))


@router.get(
    "",
    response_model=ApiResponse[list[UserPublic]],
    dependencies=[Depends(requires_super_admin)],
)
def get_users(db: Session = Depends(get_db)):
    return success_response(list_users(db))


@router.patch(
    "/{user_id}/ban",
    response_model=ApiResponse[UserPublic],
    dependencies=[Depends(requires_super_admin)],
)
async def ban(user_id: str, db: Session = Depends(get_db)):
    return success_response(await ban_user(db, user_id))


@router.patch(
    "/{user_id}/unban",
    response_model=ApiResponse[UserPublic],
    dependencies=[Depends(requires_super_admin)],
)
async def unban(user_id: str, db: Session = Depends(get_db)):
    return success_response(await unban_user(db, user_id))
