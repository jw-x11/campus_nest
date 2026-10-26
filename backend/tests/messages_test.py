import asyncio
import uuid
from types import SimpleNamespace

import httpx
import pytest
from httpx_ws import WebSocketDisconnect, aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport

import crud.messages
from caches.auth import revoke_token
from caches.messages import user_channel
from config.cache_config import redis_client
from main import app
from schemas.messages import MAX_MESSAGE_LENGTH
from utils.message_hub import CLOSE_UNAUTHORIZED, hub

pytestmark = pytest.mark.usefixtures("services")

BASE = "/api/messages"


@pytest.fixture
async def parties(register, create_space):
    owner, renter, stranger = await register(), await register(), await register()
    space = await create_space(owner)
    return SimpleNamespace(owner=owner, renter=renter, stranger=stranger, space=space)


@pytest.fixture
def open_conversation(client):
    async def _open(user, space_id: int, booking_id: str | None = None) -> dict:
        body = {"space_id": space_id}
        if booking_id is not None:
            body["booking_id"] = booking_id
        resp = await client.post(f"{BASE}/conversations", json=body, headers=user.headers)
        assert resp.status_code == 200, resp.text
        return resp.json()["data"]

    return _open


@pytest.fixture
def send(client):
    async def _send(user, conversation_id: str, body: str = "Hi there", client_msg_id: str | None = None):
        return await client.post(
            f"{BASE}/conversations/{conversation_id}/messages",
            json={"body": body, "client_msg_id": client_msg_id or str(uuid.uuid4())},
            headers=user.headers,
        )

    return _send


@pytest.fixture
async def conversation(parties, open_conversation):
    return await open_conversation(parties.renter, parties.space["id"])


@pytest.fixture
def published(monkeypatch) -> list[tuple[str, dict]]:
    """Events crud.messages publishes, recorded instead of sent."""
    events: list[tuple[str, dict]] = []

    async def fake_publish(user_id, event):
        events.append((str(user_id), event))
        return 1

    monkeypatch.setattr(crud.messages, "publish_event", fake_publish)
    return events


async def unread(client, user) -> dict:
    resp = await client.get(f"{BASE}/unread", headers=user.headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


class TestOpenConversation:
    async def test_find_or_create_is_idempotent(self, parties, open_conversation):
        first = await open_conversation(parties.renter, parties.space["id"])
        second = await open_conversation(parties.renter, parties.space["id"])
        assert first["id"] == second["id"]
        assert first["renter_id"] == parties.renter.id
        assert first["owner_id"] == parties.owner.id
        assert first["role"] == "renter"
        assert first["other_user"]["id"] == parties.owner.id
        # the other user's private fields stay private
        assert "email" not in first["other_user"]

    async def test_cannot_message_own_space(self, client, parties):
        resp = await client.post(f"{BASE}/conversations", json={"space_id": parties.space["id"]},
                                 headers=parties.owner.headers)
        assert resp.status_code == 400

    async def test_unknown_space(self, client, parties):
        resp = await client.post(f"{BASE}/conversations", json={"space_id": 999}, headers=parties.renter.headers)
        assert resp.status_code == 404

    async def test_owner_opens_from_booking_and_joins_existing_thread(self, parties, open_conversation, make_booking):
        existing = await open_conversation(parties.renter, parties.space["id"])
        booking_id = await make_booking(parties.space, parties.renter, parties.owner)

        from_owner = await open_conversation(parties.owner, parties.space["id"], booking_id)
        assert from_owner["id"] == existing["id"]
        assert from_owner["booking_id"] == booking_id
        assert from_owner["role"] == "owner"

    async def test_stranger_cannot_use_booking(self, client, parties, make_booking):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner)
        resp = await client.post(f"{BASE}/conversations",
                                 json={"space_id": parties.space["id"], "booking_id": booking_id},
                                 headers=parties.stranger.headers)
        assert resp.status_code == 403

    async def test_requires_auth(self, client, parties):
        resp = await client.post(f"{BASE}/conversations", json={"space_id": parties.space["id"]})
        assert resp.status_code == 401


class TestStrangerIsBlocked:
    @pytest.mark.parametrize("method,suffix", [
        ("get", ""), ("get", "/messages"), ("post", "/read"),
    ])
    async def test_routes(self, client, parties, conversation, method, suffix):
        resp = await getattr(client, method)(f"{BASE}/conversations/{conversation['id']}{suffix}",
                                             headers=parties.stranger.headers)
        assert resp.status_code == 403

    async def test_send(self, parties, conversation, send):
        resp = await send(parties.stranger, conversation["id"])
        assert resp.status_code == 403

    async def test_unknown_conversation(self, client, parties):
        resp = await client.get(f"{BASE}/conversations/{uuid.uuid4()}", headers=parties.renter.headers)
        assert resp.status_code == 404


class TestSend:
    @pytest.mark.parametrize("body", ["", "   ", "x" * (MAX_MESSAGE_LENGTH + 1)])
    async def test_rejects_bad_body(self, parties, conversation, send, body):
        resp = await send(parties.renter, conversation["id"], body)
        assert resp.status_code == 400

    async def test_body_is_trimmed(self, parties, conversation, send):
        resp = await send(parties.renter, conversation["id"], "  hello  ")
        assert resp.json()["data"]["body"] == "hello"

    async def test_retry_returns_same_message_and_publishes_once(self, parties, conversation, send, published):
        client_msg_id = str(uuid.uuid4())
        first = await send(parties.renter, conversation["id"], "once", client_msg_id)
        second = await send(parties.renter, conversation["id"], "once", client_msg_id)

        assert first.status_code == second.status_code == 200
        assert first.json()["data"]["id"] == second.json()["data"]["id"]
        assert second.json()["message"] == "Message already sent"
        # one event each to the recipient and the sender
        assert sorted(user_id for user_id, _ in published) == sorted([parties.owner.id, parties.renter.id])
        assert all(event["type"] == "message" for _, event in published)

    async def test_same_client_id_from_other_sender_is_a_new_message(self, parties, conversation, send):
        client_msg_id = str(uuid.uuid4())
        a = await send(parties.renter, conversation["id"], "a", client_msg_id)
        b = await send(parties.owner, conversation["id"], "b", client_msg_id)
        assert a.json()["data"]["id"] != b.json()["data"]["id"]

    async def test_inbox_orders_by_latest_message(self, client, parties, register, create_space,
                                                  open_conversation, send):
        other_owner = await register()
        other_space = await create_space(other_owner)
        first = await open_conversation(parties.renter, parties.space["id"])
        second = await open_conversation(parties.renter, other_space["id"])

        await send(parties.renter, second["id"], "older")
        await send(parties.renter, first["id"], "newer")

        resp = await client.get(f"{BASE}/conversations", headers=parties.renter.headers)
        data = resp.json()["data"]
        assert data["total_count"] == 2
        assert [c["id"] for c in data["conversations"]] == [first["id"], second["id"]]
        assert data["conversations"][0]["last_message"]["body"] == "newer"
        assert data["conversations"][0]["last_message_at"] is not None


class TestHistory:
    async def _send_many(self, send, user, conversation_id, count):
        ids = []
        for i in range(count):
            resp = await send(user, conversation_id, f"m{i}")
            ids.append(resp.json()["data"]["id"])
        return ids

    async def _page(self, client, user, conversation_id, **params):
        resp = await client.get(f"{BASE}/conversations/{conversation_id}/messages",
                                params=params, headers=user.headers)
        assert resp.status_code == 200, resp.text
        return resp.json()["data"]

    async def test_pages_back_without_gaps(self, client, parties, conversation, send):
        ids = await self._send_many(send, parties.renter, conversation["id"], 5)

        newest = await self._page(client, parties.renter, conversation["id"], limit=2)
        assert [m["id"] for m in newest["messages"]] == ids[3:]
        assert newest["has_more"] is True

        middle = await self._page(client, parties.renter, conversation["id"], limit=2, before=ids[3])
        assert [m["id"] for m in middle["messages"]] == ids[1:3]

        oldest = await self._page(client, parties.renter, conversation["id"], limit=2, before=ids[1])
        assert [m["id"] for m in oldest["messages"]] == ids[:1]
        assert oldest["has_more"] is False

    async def test_catch_up_after(self, client, parties, conversation, send):
        ids = await self._send_many(send, parties.renter, conversation["id"], 4)
        page = await self._page(client, parties.owner, conversation["id"], after=ids[1])
        assert [m["id"] for m in page["messages"]] == ids[2:]
        assert page["has_more"] is False

    async def test_cursor_from_another_conversation(self, client, parties, register, create_space,
                                                    conversation, open_conversation, send):
        other_space = await create_space(await register())
        other = await open_conversation(parties.renter, other_space["id"])
        foreign_id = (await send(parties.renter, other["id"])).json()["data"]["id"]
        resp = await client.get(f"{BASE}/conversations/{conversation['id']}/messages",
                                params={"before": foreign_id}, headers=parties.renter.headers)
        assert resp.status_code == 400

    async def test_before_and_after_together(self, client, parties, conversation):
        resp = await client.get(f"{BASE}/conversations/{conversation['id']}/messages",
                                params={"before": str(uuid.uuid4()), "after": str(uuid.uuid4())},
                                headers=parties.renter.headers)
        assert resp.status_code == 400


class TestUnread:
    async def test_counts_and_clears(self, client, parties, conversation, send):
        assert (await unread(client, parties.owner))["total"] == 0

        await send(parties.renter, conversation["id"], "one")
        await send(parties.renter, conversation["id"], "two")
        owner_unread = await unread(client, parties.owner)
        assert owner_unread["total"] == 2
        assert owner_unread["conversations"] == {conversation["id"]: 2}
        # the sender's own messages are never unread for them
        assert (await unread(client, parties.renter))["total"] == 0

        resp = await client.post(f"{BASE}/conversations/{conversation['id']}/read", headers=parties.owner.headers)
        assert resp.status_code == 200
        assert (await unread(client, parties.owner))["total"] == 0

        await send(parties.renter, conversation["id"], "three")
        assert (await unread(client, parties.owner))["total"] == 1

    async def test_rebuilds_after_cache_loss(self, client, parties, conversation, send):
        await unread(client, parties.owner)  # warm the cache
        await send(parties.renter, conversation["id"])
        await redis_client.delete(f"msg:unread:{parties.owner.id}")
        await send(parties.renter, conversation["id"])

        # the missing key is not recreated from one increment; the read recounts both
        assert (await unread(client, parties.owner))["total"] == 2

    async def test_inbox_shows_unread(self, client, parties, conversation, send):
        await send(parties.renter, conversation["id"])
        resp = await client.get(f"{BASE}/conversations", headers=parties.owner.headers)
        assert resp.json()["data"]["conversations"][0]["unread_count"] == 1

    async def test_read_tells_the_other_side(self, client, parties, conversation, published):
        await client.post(f"{BASE}/conversations/{conversation['id']}/read", headers=parties.owner.headers)
        assert [(user_id, event["type"]) for user_id, event in published] == [(parties.renter.id, "read")]


# --------------------------------------------------------------------------- live delivery


@pytest.fixture
async def running_hub():
    """The hub's Redis listener and its sockets, as main.py's lifespan runs them."""
    task = asyncio.create_task(hub.run())
    yield hub
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await hub.close()
    hub.sockets.clear()
    hub.tokens.clear()


def live_client() -> httpx.AsyncClient:
    """Client that speaks WebSocket to the app. Open it inside the test: its transport holds an anyio
    cancel scope that must close in the task that opened it, which fixture teardown is not."""
    return httpx.AsyncClient(transport=ASGIWebSocketTransport(app=app), base_url="http://test")


async def ticket_for(client, user) -> str:
    resp = await client.post(f"{BASE}/ws-ticket", headers=user.headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["ticket"]


async def receive_type(ws, event_type: str, timeout: float = 3.0) -> dict:
    """Next frame of this type, skipping heartbeats and other events."""
    async def _wait():
        while True:
            frame = await ws.receive_json()
            if frame["type"] == event_type:
                return frame

    return await asyncio.wait_for(_wait(), timeout)


async def wait_until(predicate, timeout: float = 3.0) -> None:
    async def _wait():
        while not await predicate():
            await asyncio.sleep(0.02)

    await asyncio.wait_for(_wait(), timeout)


async def subscribers(user_id: str) -> int:
    [(_, count)] = await redis_client.pubsub_numsub(user_channel(user_id))
    return count


class TestLiveDelivery:
    async def test_rest_send_reaches_recipient_and_sender_tabs(self, running_hub, parties,
                                                               conversation, send):
        async with live_client() as ws_client:
            owner_ticket = await ticket_for(ws_client, parties.owner)
            renter_ticket = await ticket_for(ws_client, parties.renter)
            async with aconnect_ws(f"{BASE}/ws?ticket={owner_ticket}", ws_client) as owner_ws, \
                    aconnect_ws(f"{BASE}/ws?ticket={renter_ticket}", ws_client) as renter_other_tab:
                await wait_until(lambda: _both_subscribed(parties))

                resp = await send(parties.renter, conversation["id"], "live hello")
                message_id = resp.json()["data"]["id"]

                to_owner = await receive_type(owner_ws, "message")
                to_renter = await receive_type(renter_other_tab, "message")
                assert to_owner["message"]["id"] == to_renter["message"]["id"] == message_id
                assert to_owner["conversation_id"] == conversation["id"]

    async def test_socket_send_acks_and_delivers(self, running_hub, parties, conversation):
        async with live_client() as ws_client:
            owner_ticket = await ticket_for(ws_client, parties.owner)
            renter_ticket = await ticket_for(ws_client, parties.renter)
            async with aconnect_ws(f"{BASE}/ws?ticket={owner_ticket}", ws_client) as owner_ws, \
                    aconnect_ws(f"{BASE}/ws?ticket={renter_ticket}", ws_client) as renter_ws:
                await wait_until(lambda: _both_subscribed(parties))
                client_msg_id = str(uuid.uuid4())
                await renter_ws.send_json({"type": "send", "conversation_id": conversation["id"],
                                           "body": "over the socket", "client_msg_id": client_msg_id})

                ack = await receive_type(renter_ws, "ack")
                assert ack["client_msg_id"] == client_msg_id
                delivered = await receive_type(owner_ws, "message")
                assert delivered["message"]["body"] == "over the socket"

    async def test_typing_reaches_only_the_other_side(self, running_hub, parties, conversation):
        async with live_client() as ws_client:
            owner_ticket = await ticket_for(ws_client, parties.owner)
            renter_ticket = await ticket_for(ws_client, parties.renter)
            async with aconnect_ws(f"{BASE}/ws?ticket={owner_ticket}", ws_client) as owner_ws, \
                    aconnect_ws(f"{BASE}/ws?ticket={renter_ticket}", ws_client) as renter_ws:
                await wait_until(lambda: _both_subscribed(parties))
                await renter_ws.send_json({"type": "typing", "conversation_id": conversation["id"]})
                typing = await receive_type(owner_ws, "typing")
                assert typing["user_id"] == parties.renter.id

    async def test_bad_frame_gets_an_error(self, running_hub, parties):
        async with live_client() as ws_client:
            ticket = await ticket_for(ws_client, parties.renter)
            async with aconnect_ws(f"{BASE}/ws?ticket={ticket}", ws_client) as ws:
                await ws.send_text("not json")
                error = await receive_type(ws, "error")
                assert error["code"] == "BAD_FRAME"

    async def test_stranger_socket_cannot_send(self, running_hub, parties, conversation):
        async with live_client() as ws_client:
            ticket = await ticket_for(ws_client, parties.stranger)
            async with aconnect_ws(f"{BASE}/ws?ticket={ticket}", ws_client) as ws:
                await ws.send_json({"type": "send", "conversation_id": conversation["id"],
                                    "body": "let me in", "client_msg_id": str(uuid.uuid4())})
                error = await receive_type(ws, "error")
                assert error["code"] == "NOT_FOUND"

    async def test_unsubscribes_after_last_socket(self, running_hub, parties):
        async with live_client() as ws_client:
            ticket = await ticket_for(ws_client, parties.renter)
            async with aconnect_ws(f"{BASE}/ws?ticket={ticket}", ws_client):
                await wait_until(lambda: _subscribed(parties.renter.id, 1))
            await wait_until(lambda: _subscribed(parties.renter.id, 0))
            assert parties.renter.id not in hub.sockets


async def _subscribed(user_id: str, count: int) -> bool:
    return await subscribers(user_id) == count


async def _both_subscribed(parties) -> bool:
    return await subscribers(parties.owner.id) == 1 and await subscribers(parties.renter.id) == 1


class TestSocketAuth:
    @pytest.mark.parametrize("query", ["", "?ticket=nope"])
    async def test_missing_or_unknown_ticket(self, running_hub, query):
        async with live_client() as ws_client:
            async with aconnect_ws(f"{BASE}/ws{query}", ws_client) as ws:
                with pytest.raises(WebSocketDisconnect) as closed:
                    await ws.receive_text()
            assert closed.value.code == CLOSE_UNAUTHORIZED

    async def test_ticket_works_once(self, running_hub, parties):
        async with live_client() as ws_client:
            ticket = await ticket_for(ws_client, parties.renter)
            async with aconnect_ws(f"{BASE}/ws?ticket={ticket}", ws_client):
                pass
            async with aconnect_ws(f"{BASE}/ws?ticket={ticket}", ws_client) as ws:
                with pytest.raises(WebSocketDisconnect) as closed:
                    await ws.receive_text()
            assert closed.value.code == CLOSE_UNAUTHORIZED

    async def test_logout_closes_socket_on_heartbeat(self, running_hub, parties):
        async with live_client() as ws_client:
            ticket = await ticket_for(ws_client, parties.renter)
            async with aconnect_ws(f"{BASE}/ws?ticket={ticket}", ws_client) as ws:
                await wait_until(lambda: _subscribed(parties.renter.id, 1))
                await revoke_token(parties.renter.token)
                await hub.heartbeat_once()
                with pytest.raises(WebSocketDisconnect) as closed:
                    await asyncio.wait_for(ws.receive_text(), 3)
            assert closed.value.code == CLOSE_UNAUTHORIZED
            assert parties.renter.id not in hub.sockets

    async def test_heartbeat_pings_live_sockets(self, running_hub, parties):
        async with live_client() as ws_client:
            ticket = await ticket_for(ws_client, parties.renter)
            async with aconnect_ws(f"{BASE}/ws?ticket={ticket}", ws_client) as ws:
                await wait_until(lambda: _subscribed(parties.renter.id, 1))
                await hub.heartbeat_once()
                assert (await receive_type(ws, "ping"))["type"] == "ping"
