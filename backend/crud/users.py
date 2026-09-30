from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile

from caches.user import *
from models.users import User
from schemas.auth import AuthRegisterRequest

from utils.auth import hash_password
from caches.auth import get_user_id_by_token
from schemas.users import UserInfoResponse, UserUpdateRequest
from utils.s3 import read_image
from config.s3db_config import delete_s3_object_by_url, upload_bytes

async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    query = select(User).where(User.username == username)
    result = await session.execute(query)
    return result.scalar_one_or_none()

async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    query = select(User).where(User.email == email)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    query = select(User).where(User.id == user_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()

async def get_user_info_by_id(session: AsyncSession, user_id: UUID) -> UserInfoResponse | None:
    # check cache
    cached = await get_user_cache(user_id)
    if cached is not None:
        return cached
    # if not in cache, get from database
    user = await get_user_by_id(session, user_id)
    if user is None:
        return None
    user_info = UserInfoResponse.model_validate(user)
    # write to cache
    await set_user_cache(user_id, user_info)
    return user_info

async def get_user_by_token(session: AsyncSession, token: str) -> UserInfoResponse | None:
    user_id = await get_user_id_by_token(token)
    if not user_id:
        return None
    user_info = await get_user_info_by_id(session, user_id)
    if not user_info:
        return None
    return user_info

# only use by auth
async def get_raw_user_by_token(session: AsyncSession, token: str) -> User | None:
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
    query = update(User).where(User.email == email).values(
        **user_data.model_dump(
            exclude_unset=True,
            exclude_none=True,
            exclude={"id", "email", "avatar_url", "is_verified"},
        ),
        updated_at=update_at,
    )
    result = await session.execute(query)
    await session.commit()
    
    if result.rowcount == 0:
        return None

    await delete_user_cache(User.id)
    updated_user = await get_user_by_email(session, email)
    return UserInfoResponse.model_validate(updated_user)


async def soft_delete_user(session: AsyncSession, user_id: UUID) -> bool:
    deleted_user_data = {
        "username": "Deleted User",
        "university": None,
        "description": None,
        "avatar_url": None,
        "is_verified": False,
        "updated_at": datetime.now(timezone.utc),
    }
    query = update(User).where(User.id == user_id).values(**deleted_user_data)
    result = await session.execute(query)
    await session.commit()
    if result.rowcount == 0:
        return False
    await delete_user_cache(user_id)
    return True


async def upload_user_avatar(session: AsyncSession, user: User, file: UploadFile) -> User:
    body, content_type = await read_image(file)
    url = await upload_bytes(body, prefix=f"avatars/{user.id}", content_type=content_type)
    old_url = user.avatar_url
    try:
        query = (
            update(User)
            .where(User.id == user.id)
            .values(avatar_url=url, updated_at=func.now())
        )
        await session.execute(query)
        await session.commit()
    except Exception:
        await delete_s3_object_by_url(url)
        raise

    if old_url and old_url != url:
        await delete_s3_object_by_url(old_url)

    updated = await get_user_by_id(session, str(user.id))
    if not updated:
        raise RuntimeError("User not found after avatar upload")
    return updated
