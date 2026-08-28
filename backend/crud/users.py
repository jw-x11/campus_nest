from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from models.users import User
from schemas.auth import AuthRegisterRequest

from utils.auth import hash_password
from caches.auth import get_user_id_by_token
from schemas.users import UserInfoResponse, UserUpdateRequest

async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    query = select(User).where(User.username == username)
    result = await session.execute(query)
    return result.scalar_one_or_none()

async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    query = select(User).where(User.email == email)
    result = await session.execute(query)
    return result.scalar_one_or_none()

async def get_user_by_id(session: AsyncSession, user_id: str) -> User | None:
    query = select(User).where(User.id == user_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_user_by_token(session: AsyncSession, token: str) -> User | None:
    user_id = await get_user_id_by_token(token)
    if not user_id:
        return None
    user = await get_user_by_id(session, user_id)
    if not user:
        return None
    return user

async def create_user(session: AsyncSession, user_data: AuthRegisterRequest) -> User:
    hashed_password = hash_password(user_data.password)
    user = User(
        email=user_data.email,
        password=hashed_password,
        username=user_data.username,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_user(session: AsyncSession, email: str, user_data: UserUpdateRequest) -> User | None:
    # Pydantic convert to dict then convert into sqlalchemy orm
    update_at = datetime.now(timezone.utc)
    query = update(User).where(User.email == email).values(**user_data.model_dump(exclude_unset=True, exclude_none=True), updated_at=update_at)
    result = await session.execute(query)
    await session.commit()
    
    if result.rowcount == 0:
        return None

    updated_user = await get_user_by_email(session, email)
    return UserInfoResponse.model_validate(updated_user)


async def soft_delete_user(session: AsyncSession, user_id: UUID) -> bool:
    deleted_user_data = {
        "username": "Deleted User",
        "university": None,
        "avatar_url": None,
        "is_verified": False,
        "updated_at": datetime.now(timezone.utc),
    }
    query = update(User).where(User.id == user_id).values(**deleted_user_data)
    result = await session.execute(query)
    await session.commit()
    if result.rowcount == 0:
        return False
    return True
