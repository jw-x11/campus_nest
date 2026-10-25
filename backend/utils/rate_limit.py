import ipaddress
import math
import time
from typing import Literal

from fastapi import HTTPException, Request, status
from limits import parse_many
from limits.aio.storage import RedisStorage
from limits.aio.strategies import MovingWindowRateLimiter, SlidingWindowCounterRateLimiter

import config.rate_limit_config as rate_limit_config
from caches.auth import get_user_id_by_token
from config.cache_config import REDIS_URI
from utils.deps import get_bearer_token

# Buckets live in the app's Redis as rl:<strategy keys>, apart from the cache keys.
storage = RedisStorage(f"async+{REDIS_URI}", implementation="redispy", key_prefix="rl", socket_timeout=5)
limiters = {
    "moving": MovingWindowRateLimiter(storage),
    "sliding": SlidingWindowCounterRateLimiter(storage),
}
# Parsed once: scope -> the limits that must all hold.
_tier_limits = {scope: parse_many(tier.limits) for scope, tier in rate_limit_config.TIERS.items()}


def client_ip(request: Request) -> str:
    """Address of the client. X-Real-IP is used only when the request came through a trusted proxy (nginx)."""
    peer = request.client.host if request.client else ""
    try:
        trusted = any(ipaddress.ip_address(peer) in network for network in rate_limit_config.TRUSTED_PROXIES)
    except ValueError:
        trusted = False
    if trusted:
        forwarded = request.headers.get("x-real-ip", "").strip()
        if forwarded:
            return forwarded
    return peer or "unknown"


async def _identity(request: Request) -> str:
    """user:<id> for a valid bearer token, otherwise ip:<address>. Never raises: the route's own auth answers 401."""
    try:
        token = get_bearer_token(request.headers.get("authorization"))
        user_id = await get_user_id_by_token(token)
    except HTTPException:
        user_id = None
    if user_id:
        return f"user:{user_id}"
    return f"ip:{client_ip(request)}"


async def check(scope: str, identity: str) -> None:
    """Count one request against every limit of this scope. Raises 429 when one is used up."""
    if not rate_limit_config.RATE_LIMIT_ENABLED:
        return
    tier = rate_limit_config.TIERS[scope]
    limiter = limiters[tier.strategy]
    try:
        for item in _tier_limits[scope]:
            if not await limiter.hit(item, scope, identity):
                stats = await limiter.get_window_stats(item, scope, identity)
                retry_after = max(1, math.ceil(stats.reset_time - time.time()))
                break
        else:
            return
    except Exception as e:
        print(f"Error checking rate limit {scope}: {e}")
        if tier.fail_open:
            return
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="RATE_LIMITER_UNAVAILABLE")

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="RATE_LIMITED",
        headers={
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": str(item.amount),
            "X-RateLimit-Remaining": "0",
        },
    )


def rate_limit(scope: str, by: Literal["auto", "ip"] = "auto"):
    """
    Dependency that limits a route or router under one scope from config.rate_limit_config.TIERS.\n
    'by' picks the identity: "auto" is the signed-in user, else the client address; "ip" is always the address.\n
    Use as dependencies=[Depends(rate_limit("map"))].
    """
    if scope not in rate_limit_config.TIERS:
        raise ValueError(f"Unknown rate limit scope: {scope}")

    async def dependency(request: Request) -> None:
        identity = f"ip:{client_ip(request)}" if by == "ip" else await _identity(request)
        await check(scope, identity)

    return dependency
