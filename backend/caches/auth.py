import uuid

from config.cache_config import get_redis

TOKEN_TTL = 7 * 24 * 60 * 60   # 7 days, in seconds


def _token_key(token: str) -> str:
    return f"token:{token}"


async def create_token(user_id: str) -> dict:
    """Issue a single 7-day token for a user and store it in Redis."""
    redis = get_redis()
    token = str(uuid.uuid4())
    await redis.set(_token_key(token), user_id, ex=TOKEN_TTL)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": TOKEN_TTL,
    }


async def get_user_id_by_token(token: str) -> str | None:
    """Resolve a token to a user_id, or None if missing/expired."""
    redis = get_redis()
    return await redis.get(_token_key(token))


async def revoke_token(token: str) -> None:
    """Delete a token so it can no longer authenticate (logout)."""
    redis = get_redis()
    await redis.delete(_token_key(token))
