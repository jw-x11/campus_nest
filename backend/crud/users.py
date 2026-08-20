from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.users import User
from schemas.auth import AuthRegisterRequest

from utils.auth import hash_password

async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    pass 

async def create_user(session: AsyncSession, user_data: AuthRegisterRequest) :
    print(user_data.password)
    hashed_password = hash_password(user_data.password)
    user = User(
        email=user_data.email,
        password=hashed_password,
        full_name=user_data.full_name,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
