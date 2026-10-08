from fastapi import Header, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from schemas.users import UserInfoResponse
from config.db_config import get_db
from crud.users import get_raw_user_by_token, get_user_by_token


def get_bearer_token(authorization: str | None) -> str:
    """Token from an "Authorization: Bearer <token>" header. Raises 401 when it is missing or malformed."""
    scheme, _, token = (authorization or "").partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return token


# Get current user from authorization header, use as dependency in routers
async def get_current_user( authorization: str | None = Header(None), db: AsyncSession = Depends(get_db)):
    token = get_bearer_token(authorization)
    user = await get_raw_user_by_token(db, token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user


async def get_current_user_info( authorization: str | None = Header(None), db: AsyncSession = Depends(get_db)) -> UserInfoResponse:
    token = get_bearer_token(authorization)
    user_info = await get_user_by_token(db, token)
    if not user_info:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user_info
