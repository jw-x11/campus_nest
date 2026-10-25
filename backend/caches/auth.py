import uuid

from config.cache_config import (
    get_cache, set_cache, delete_cache, update_ttl, get_ttl, DAY,
    add_set_cache, remove_set_cache, get_set_cache,
)

TOKEN_TTL = 7 * 24 * 60 * 60   # 7 days, in seconds

# format for the token key
def _token_key(token: str) -> str:
    return f"token:{token}"


# format for the key of the set that holds every active token of one user
def _sessions_key(user_id: str) -> str:
    return f"user_sessions:{user_id}"


async def create_token(user_id: str) -> dict:
    """Issue a single 7-day token for a user and store it in Redis, and in the user's session set."""
    token = str(uuid.uuid4())
    await set_cache(_token_key(token), str(user_id), ttl=TOKEN_TTL)
    await add_set_cache(_sessions_key(user_id), token, ttl=TOKEN_TTL)

    return token


async def get_user_id_by_token(token: str) -> str | None:
    """Resolve a token to a user_id, or None if missing/expired."""
    return await get_cache(_token_key(token))


async def revoke_token(token: str) -> None:
    """Delete a token so it can no longer authenticate (logout)."""
    user_id = await get_user_id_by_token(token)
    await delete_cache(_token_key(token))
    if user_id is not None:
        await remove_set_cache(_sessions_key(user_id), token)


async def revoke_all_tokens(user_id: str) -> int:
    """Delete every token of a user (logout of all devices). Returns how many tokens were in the session set."""
    key = _sessions_key(user_id)
    tokens = await get_set_cache(key) or set()
    for token in tokens:
        await delete_cache(_token_key(token))
    await delete_cache(key)
    return len(tokens)


async def refresh_token(token: str) -> None:
    key = _token_key(token)
    remaining = await get_ttl(key)
    if 0 < remaining < 1 * DAY:
        await update_ttl(key, TOKEN_TTL)
        user_id = await get_user_id_by_token(token)
        if user_id is not None:
            await update_ttl(_sessions_key(user_id), TOKEN_TTL)
