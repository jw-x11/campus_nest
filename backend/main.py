import asyncio
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI, APIRouter, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import db_config, s3db_config
from config.exception_handlers import register_exception_handlers
from routers.auth import api_auth
from routers.users import api_users
from routers.spaces import api_spaces
from routers.bookings import api_bookings
from routers.view_history import api_view_history
from routers.saved_space import api_saved_space
from routers.map import api_map
from routers.messages import api_messages, api_messages_ws
from jobs.booking_status import run_booking_status_job
from jobs.view_count_flush import flush_view_counts_now, run_view_count_flusher
from utils.message_hub import hub
from utils.rate_limit import rate_limit

# TODO: Reviews and comments section
# TODO: Add logging and analytics
# TODO: Tests: Integration, e2e
# TODO: Stripe payment integration


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_config.connect()
    await s3db_config.connect()
    view_flusher = asyncio.create_task(run_view_count_flusher())
    booking_status_job = asyncio.create_task(run_booking_status_job())
    message_hub = asyncio.create_task(hub.run())
    message_heartbeat = asyncio.create_task(hub.run_heartbeat())
    yield
    for job in (view_flusher, booking_status_job, message_hub, message_heartbeat):
        job.cancel()
        with suppress(asyncio.CancelledError):
            await job
    await hub.close()
    # Write views from the last interval before the database pool closes.
    await flush_view_counts_now()
    await db_config.disconnect()
    await s3db_config.disconnect()


app = FastAPI(lifespan=lifespan)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app_router = APIRouter()
app.include_router(app_router, prefix="/api")

# Every /api route counts against the default limit; routers and routes add stricter ones.
default_limit = [Depends(rate_limit("default"))]

app_router.include_router(api_auth, prefix="/auth", tags=["auth"], dependencies=default_limit)
app_router.include_router(api_users, prefix="/users", tags=["users"], dependencies=default_limit)
app_router.include_router(api_spaces, prefix="/spaces", tags=["spaces"], dependencies=default_limit)
app_router.include_router(api_bookings, prefix="/bookings", tags=["bookings"], dependencies=default_limit)
app_router.include_router(api_view_history, prefix="/history", tags=["view-history"], dependencies=default_limit)
app_router.include_router(api_saved_space, prefix="/saved", tags=["saved-space"], dependencies=default_limit)
app_router.include_router(api_map, prefix="/map", tags=["map"], dependencies=default_limit)
app_router.include_router(api_messages, prefix="/messages", tags=["messages"], dependencies=default_limit)
# No default_limit: the limit dependency reads an HTTP request, which a WebSocket is not. Sends are limited inside.
app_router.include_router(api_messages_ws, prefix="/messages", tags=["messages"])

@app.get("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", port=5001, reload=True)
