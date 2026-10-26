import asyncio
from contextlib import suppress

import redis.asyncio as redis
from fastapi import WebSocket

from caches.auth import get_user_id_by_token
from caches.messages import user_channel
from config.cache_config import REDIS_URI

HEARTBEAT_INTERVAL = 30
RECONNECT_DELAY = 1
# Close code for a socket whose session is gone; the client should sign in again rather than reconnect.
CLOSE_UNAUTHORIZED = 4401
CHANNEL_PREFIX = user_channel("")


class MessageHub:
    """The sockets open on this process, and the one Redis subscription that feeds them.

    Each user with at least one socket here is subscribed to their own channel, user:{id}.
    Events published to that channel from any process are forwarded to all of the user's sockets.
    """

    def __init__(self, redis_uri: str = REDIS_URI):
        self.redis_uri = redis_uri
        self.sockets: dict[str, set[WebSocket]] = {}
        # Session token behind each socket, re-checked on every heartbeat.
        self.tokens: dict[WebSocket, str] = {}
        self._lock = asyncio.Lock()
        self._redis: redis.Redis | None = None
        self._pubsub = None

    async def _connect_redis(self) -> None:
        # Its own client: a subscribed connection can do nothing else, and it sits idle between
        # messages, so it must not inherit the shared pool's 5-second read timeout.
        self._redis = redis.Redis.from_url(
            self.redis_uri, decode_responses=True, socket_timeout=None, health_check_interval=30
        )
        self._pubsub = self._redis.pubsub()

    async def _ensure_redis(self) -> None:
        if self._pubsub is None:
            await self._connect_redis()

    async def connect(self, user_id: str, websocket: WebSocket, token: str) -> None:
        """Track a socket that has already been accepted and authenticated. Subscribes on the user's first socket."""
        async with self._lock:
            await self._ensure_redis()
            first = user_id not in self.sockets
            self.sockets.setdefault(user_id, set()).add(websocket)
            self.tokens[websocket] = token
            if first:
                await self._pubsub.subscribe(user_channel(user_id))

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        """Forget a socket. Unsubscribes when it was the user's last one here."""
        async with self._lock:
            self.tokens.pop(websocket, None)
            user_sockets = self.sockets.get(user_id)
            if user_sockets is None:
                return
            user_sockets.discard(websocket)
            if not user_sockets:
                del self.sockets[user_id]
                if self._pubsub is not None:
                    with suppress(Exception):
                        await self._pubsub.unsubscribe(user_channel(user_id))

    async def deliver(self, user_id: str, data: str) -> None:
        """Send one event to every socket of this user on this process. A socket that fails is dropped."""
        for websocket in list(self.sockets.get(user_id, ())):
            try:
                await websocket.send_text(data)
            except Exception:
                await self.disconnect(user_id, websocket)

    async def _resubscribe_all(self) -> None:
        async with self._lock:
            if self._redis is not None:
                with suppress(Exception):
                    await self._redis.aclose()
            await self._connect_redis()
            channels = [user_channel(user_id) for user_id in self.sockets]
            if channels:
                await self._pubsub.subscribe(*channels)

    async def _listen_once(self) -> None:
        await self._ensure_redis()
        while True:
            # listen() returns at once while nothing is subscribed, so wait for the first subscription.
            if not self._pubsub.subscribed:
                await asyncio.sleep(0.05)
                continue
            message = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None or message["type"] != "message":
                continue
            user_id = message["channel"].removeprefix(CHANNEL_PREFIX)
            await self.deliver(user_id, message["data"])

    async def run(self) -> None:
        """Forward published events to sockets until cancelled. Reconnects and resubscribes after a Redis error."""
        while True:
            try:
                await self._listen_once()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"Message hub lost Redis, reconnecting: {e}")
                await asyncio.sleep(RECONNECT_DELAY)
                with suppress(Exception):
                    await self._resubscribe_all()

    async def heartbeat_once(self) -> None:
        """Ping every socket, and close the ones whose session was logged out or expired."""
        for user_id, user_sockets in list(self.sockets.items()):
            for websocket in list(user_sockets):
                token = self.tokens.get(websocket)
                if token is None or await get_user_id_by_token(token) != user_id:
                    with suppress(Exception):
                        await websocket.close(code=CLOSE_UNAUTHORIZED)
                    await self.disconnect(user_id, websocket)
                    continue
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    await self.disconnect(user_id, websocket)

    async def run_heartbeat(self, interval: int = HEARTBEAT_INTERVAL) -> None:
        """heartbeat_once every interval seconds until cancelled."""
        while True:
            await asyncio.sleep(interval)
            try:
                await self.heartbeat_once()
            except Exception as e:
                print(f"Error in message hub heartbeat: {e}")

    async def close(self) -> None:
        """Drop the Redis subscription. Called on shutdown after the tasks are cancelled."""
        if self._pubsub is not None:
            with suppress(Exception):
                await self._pubsub.aclose()
        if self._redis is not None:
            with suppress(Exception):
                await self._redis.aclose()
        self._pubsub = None
        self._redis = None


hub = MessageHub()
