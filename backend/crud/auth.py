from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from models.users import User
from utils.auth import hash_password


async def change_password(session: AsyncSession, user: User, new_password: str) -> bool:

    user.password = hash_password(new_password)

    session.add(user)
    await session.commit()
    await session.refresh(user)
    return True

