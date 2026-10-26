import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from caches.auth import get_user_id_by_token
from caches.messages import WS_TICKET_TTL, consume_ws_ticket, create_ws_ticket, publish_event
from config.db_config import SessionLocal, get_db
from crud.bookings import get_booking_by_id
from crud.messages import (
    conversation_exists,
    describe_conversations,
    get_or_create_conversation,
    get_participant_conversation,
    get_unread_counts,
    list_conversations,
    list_messages,
    mark_conversation_read,
    other_participant,
    send_message,
)
from crud.spaces import get_space_record
from models.messages import Conversation
from schemas.messages import (
    ConversationCreateRequest,
    ConversationResponseList,
    MessageResponse,
    MessageSendRequest,
    UnreadResponse,
    WsInbound,
    WsSend,
    WsTicketResponse,
    WsTyping,
)
from schemas.users import UserInfoResponse
from utils.deps import get_bearer_token, get_current_user_info
from utils.message_hub import CLOSE_UNAUTHORIZED, hub
from utils.rate_limit import check, rate_limit
from utils.response import success_response

# Router: /api/messages

api_messages = APIRouter()
# The WebSocket route lives apart: the router-wide rate limit dependency only works on HTTP requests.
api_messages_ws = APIRouter()

write_limit = [Depends(rate_limit("write"))]
send_limit = [Depends(rate_limit("write")), Depends(rate_limit("message"))]


async def require_conversation(db: AsyncSession, conversation_id: UUID, user_id: UUID) -> Conversation:
    """The conversation if the user is in it. 404 when it does not exist, 403 when it belongs to others."""
    conv = await get_participant_conversation(db, conversation_id, user_id)
    if conv is not None:
        return conv
    if await conversation_exists(db, conversation_id):
        raise HTTPException(status_code=403, detail="You are not part of this conversation")
    raise HTTPException(status_code=404, detail="Conversation not found")


# Open the thread about a space, or return the one that already exists.
@api_messages.post("/conversations", dependencies=write_limit)
async def open_conversation(
    body: ConversationCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
):
    if body.booking_id is not None:
        # either side of a booking can open its thread; the parties come from the booking
        booking = await get_booking_by_id(db, body.booking_id)
        if booking is None:
            raise HTTPException(status_code=404, detail="Booking not found")
        if user.id not in (booking.renter_id, booking.owner_id):
            raise HTTPException(status_code=403, detail="You are not part of this booking")
        if booking.space_id != body.space_id:
            raise HTTPException(status_code=400, detail="Booking is for a different space")
        conv = await get_or_create_conversation(
            db, booking.space_id, booking.renter_id, booking.owner_id, booking.id
        )
    else:
        # without a booking the caller is asking the owner about the listing
        space = await get_space_record(db, body.space_id)
        if space is None:
            raise HTTPException(status_code=404, detail="Space not found")
        if space.owner_id == user.id:
            raise HTTPException(status_code=400, detail="You cannot message yourself about your own space")
        if space.is_active is False:
            raise HTTPException(status_code=400, detail="Space is not active")
        conv = await get_or_create_conversation(db, space.id, user.id, space.owner_id)

    [item] = await describe_conversations(db, user.id, [conv])
    return success_response(message="Conversation ready", data=item)


# The caller's inbox.
@api_messages.get("/conversations")
async def get_my_conversations(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
):
    conversations, total_count = await list_conversations(db, user.id, page, page_size)
    items = await describe_conversations(db, user.id, conversations)
    data = ConversationResponseList(conversations=items, total_count=total_count, page=page, page_size=page_size)
    return success_response(message=f"{total_count} conversations found", data=data)


@api_messages.get("/conversations/{conversation_id}")
async def get_conversation_details(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
):
    conv = await require_conversation(db, conversation_id, user.id)
    [item] = await describe_conversations(db, user.id, [conv])
    return success_response(message="Conversation retrieved successfully", data=item)


# History. before pages back from a message; after catches up after a reconnect; neither is the newest page.
@api_messages.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
    before: Annotated[UUID | None, Query()] = None,
    after: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    if before is not None and after is not None:
        raise HTTPException(status_code=400, detail="Use before or after, not both")
    await require_conversation(db, conversation_id, user.id)
    page = await list_messages(db, conversation_id, limit, before_id=before, after_id=after)
    if page is None:
        raise HTTPException(status_code=400, detail="Cursor message is not in this conversation")
    return success_response(message=f"{len(page.messages)} messages found", data=page)


# Send without a socket. Safe to retry with the same client_msg_id.
@api_messages.post("/conversations/{conversation_id}/messages", dependencies=send_limit)
async def post_message(
    conversation_id: UUID,
    body: MessageSendRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
):
    conv = await require_conversation(db, conversation_id, user.id)
    message, created = await send_message(db, user.id, conv, body.body, body.client_msg_id)
    return success_response(
        message="Message sent" if created else "Message already sent",
        data=MessageResponse.model_validate(message),
    )


@api_messages.post("/conversations/{conversation_id}/read", dependencies=write_limit)
async def read_conversation(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
):
    conv = await require_conversation(db, conversation_id, user.id)
    read_at = await mark_conversation_read(db, conv, user.id)
    return success_response(message="Conversation marked read", data={"read_at": read_at})


# Unread counts for the inbox badge.
@api_messages.get("/unread")
async def get_unread(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
):
    counts = await get_unread_counts(db, user.id)
    data = UnreadResponse(total=sum(counts.values()), conversations=counts)
    return success_response(message=f"{data.total} unread messages", data=data)


# A browser cannot set the Authorization header on a WebSocket, so it trades the token for a
# short single-use ticket and puts that on the socket URL instead.
@api_messages.post("/ws-ticket", dependencies=write_limit)
async def get_ws_ticket(
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
    authorization: Annotated[str, Header()],
):
    ticket = await create_ws_ticket(get_bearer_token(authorization))
    if ticket is None:
        raise HTTPException(status_code=503, detail="Live messaging is unavailable")
    return success_response(message="Ticket issued", data=WsTicketResponse(ticket=ticket, expires_in=WS_TICKET_TTL))


# ---- WebSocket

async def _send_error(websocket: WebSocket, code: str, detail: str, client_msg_id: UUID | None = None) -> None:
    frame = {"type": "error", "code": code, "detail": detail}
    if client_msg_id is not None:
        frame["client_msg_id"] = str(client_msg_id)
    await websocket.send_json(frame)


async def _handle_send(websocket: WebSocket, user_id: str, frame: WsSend) -> None:
    try:
        await check("message", f"user:{user_id}")
    except HTTPException as e:
        await _send_error(websocket, str(e.detail), "Too many messages", frame.client_msg_id)
        return
    async with SessionLocal() as db:
        conv = await get_participant_conversation(db, frame.conversation_id, UUID(user_id))
        if conv is None:
            await _send_error(websocket, "NOT_FOUND", "Conversation not found", frame.client_msg_id)
            return
        message, _ = await send_message(db, UUID(user_id), conv, frame.body, frame.client_msg_id)
    await websocket.send_json({
        "type": "ack",
        "client_msg_id": str(frame.client_msg_id),
        "message": MessageResponse.model_validate(message).model_dump(mode="json"),
    })


async def _handle_typing(user_id: str, frame: WsTyping) -> None:
    # never stored; only the other participant hears it
    async with SessionLocal() as db:
        conv = await get_participant_conversation(db, frame.conversation_id, UUID(user_id))
    if conv is None:
        return
    await publish_event(other_participant(conv, UUID(user_id)), {
        "type": "typing",
        "conversation_id": str(conv.id),
        "user_id": user_id,
    })


async def _handle_frame(websocket: WebSocket, user_id: str, raw: str) -> None:
    try:
        frame = WsInbound.model_validate({"frame": json.loads(raw)}).frame
    except (json.JSONDecodeError, ValidationError):
        await _send_error(websocket, "BAD_FRAME", "Expected a send, typing or pong frame")
        return
    if isinstance(frame, WsSend):
        await _handle_send(websocket, user_id, frame)
    elif isinstance(frame, WsTyping):
        await _handle_typing(user_id, frame)
    # pong only proves the client is alive; nothing to do


# Live events for the signed-in user: new messages, read receipts, typing. Sends are accepted here too.
@api_messages_ws.websocket("/ws")
async def message_socket(websocket: WebSocket, ticket: str = ""):
    await websocket.accept()
    token = await consume_ws_ticket(ticket) if ticket else None
    user_id = await get_user_id_by_token(token) if token else None
    if not user_id:
        await websocket.close(code=CLOSE_UNAUTHORIZED)
        return

    try:
        await hub.connect(user_id, websocket, token)
    except Exception as e:
        print(f"Error registering message socket: {e}")
        await websocket.close(code=1011)
        return

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                await _handle_frame(websocket, user_id, raw)
            except WebSocketDisconnect:
                raise
            except Exception as e:
                # one failed frame should not drop the connection
                print(f"Error handling message socket frame: {e}")
                await _send_error(websocket, "INTERNAL", "Could not handle this frame")
    except (WebSocketDisconnect, RuntimeError):
        # RuntimeError: the heartbeat already closed this socket
        pass
    finally:
        await hub.disconnect(user_id, websocket)
