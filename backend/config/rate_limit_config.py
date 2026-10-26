import ipaddress
import os
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

# Switch every limit off, for example in tests. Any value other than false/0/no keeps them on.
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").strip().lower() not in ("false", "0", "no")

# Comma-separated networks whose X-Real-IP header is trusted as the client address. nginx sets
# that header; it reaches the backend from localhost or, through host.docker.internal, from the
# Docker bridge. A request from anywhere else is limited by its own address, so a client cannot
# pick a fresh bucket by sending the header itself.
TRUSTED_PROXIES = [
    ipaddress.ip_network(network.strip())
    for network in os.getenv("TRUSTED_PROXIES", "127.0.0.1/32,::1/128,172.16.0.0/12").split(",")
    if network.strip()
]


@dataclass(frozen=True)
class Tier:
    # One or more limits that must all hold, in the `limits` notation, e.g. "5/minute;20/hour".
    limits: str
    # "moving" counts every request in the last window exactly; "sliding" estimates it from two counters.
    strategy: Literal["moving", "sliding"]
    # When Redis is unreachable: True lets the request through, False answers 503.
    fail_open: bool


# Keyed by scope, the first part of each bucket's key.
TIERS: dict[str, Tier] = {
    # Auth uses the exact moving window and refuses requests when it cannot count them.
    "auth:login": Tier("5/minute;20/hour", "moving", fail_open=False),
    # Per email, so one account is not guessed at from many addresses.
    "auth:login-email": Tier("10/hour", "moving", fail_open=False),
    "auth:register": Tier("5/minute;20/hour", "moving", fail_open=False),
    "auth:reset-password": Tier("5/minute;20/hour", "moving", fail_open=False),
    # Each map request may call the paid or throttled geocoder.
    "map": Tier("30/minute", "sliding", fail_open=True),
    # Creating and changing listings, bookings and profiles, including uploads.
    "write": Tier("20/minute", "sliding", fail_open=True),
    # Chat sends, over REST and the WebSocket alike, on top of "write" for the REST route.
    "message": Tier("30/minute;500/hour", "sliding", fail_open=True),
    # Every /api route.
    "default": Tier("120/minute", "sliding", fail_open=True),
}
