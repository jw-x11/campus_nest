from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import connect as pg_connect, disconnect as pg_disconnect, get_db
import redis_client
import uvicorn

from api.chat import api_chat
from api.user import api_user
from api.listing import api_listing


@asynccontextmanager
async def lifespan(app: FastAPI):
    await pg_connect()
    await redis_client.connect()
    yield
    await pg_disconnect()
    await redis_client.disconnect()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_chat, prefix='/chat', tags=['chat'])
app.include_router(api_listing, prefix='/listing', tags=['listing'])
app.include_router(api_user, prefix='/user', tags=['user'])


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI!"}

@app.get("/api/user")
def user():
    return {"user": "user"}

@app.get("/api/status")
def health():
    return {"status": "ok"}

# TODO: Uninstall mongo and install postgres

if __name__ == '__main__':
    uvicorn.run('main:app', port=8000, reload=True)