from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import connect as mongo_connect, disconnect as mongo_disconnect, get_db
import redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mongo_connect()
    await redis_client.connect()
    yield
    await mongo_disconnect()
    await redis_client.disconnect()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI!"}

@app.get("/api/user")
def user():
    return {"user": "user"}

@app.get("/api/status")
def health():
    return {"status": "ok"}
