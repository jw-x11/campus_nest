from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.users import User
from schemas.auth import AuthRegisterRequest

from utils.auth import hash_password


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    query = select(User).where(User.email == email)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, user_data: AuthRegisterRequest):
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


async def update_user_password(session: AsyncSession, user_id: str, password: str):
    pass