"""HTTP routes for user account management."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.schemas.user import UserCreate, UserResponse
from src.services.user_service import UserAlreadyExistsError, UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Create a user unless its email address is already registered."""

    try:
        user = await UserService(session).create_user(payload)
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return UserResponse.model_validate(user)


@router.get("", response_model=list[UserResponse])
async def list_users(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[UserResponse]:
    """List all user accounts without exposing password hashes."""

    users = await UserService(session).list_users()
    return [UserResponse.model_validate(user) for user in users]
