import uuid

from config.cache_config import get_cache, set_cache, delete_cache

TOKEN_TTL = 7 * 24 * 60 * 60   # 7 days, in seconds

# format for the token key
def _token_key(token: str) -> str:
    return f"token:{token}"


async def create_token(user_id: str) -> dict:
    """Issue a single 7-day token for a user and store it in Redis."""
    token = str(uuid.uuid4())
    await set_cache(_token_key(token), str(user_id), ttl=TOKEN_TTL)

    return token


async def get_user_id_by_token(token: str) -> str | None:
    """Resolve a token to a user_id, or None if missing/expired."""
    return await get_cache(_token_key(token))


async def revoke_token(token: str) -> None:
    """Delete a token so it can no longer authenticate (logout)."""
    await delete_cache(_token_key(token))
