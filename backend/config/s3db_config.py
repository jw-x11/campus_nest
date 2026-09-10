import os
import uuid
from contextlib import asynccontextmanager

import aioboto3
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

S3_ENDPOINT = os.getenv("S3_ENDPOINT") or os.getenv(
    "SEAWEEDFS_S3_ENDPOINT", "http://localhost:8333"
)
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_PUBLIC_URL = os.getenv("S3_PUBLIC_URL", S3_ENDPOINT).rstrip("/")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")
S3_REGION = os.getenv("S3_REGION", "us-east-1")

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
EXT_BY_TYPE = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}
MAX_BYTES = 10 * 1024 * 1024

_session = aioboto3.Session()
_client_kwargs = {
    "service_name": "s3",
    "endpoint_url": S3_ENDPOINT,
    "aws_access_key_id": S3_ACCESS_KEY,
    "aws_secret_access_key": S3_SECRET_KEY,
    "region_name": S3_REGION,
    "config": Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
    ),
}


@asynccontextmanager
async def s3_client():
    async with _session.client(**_client_kwargs) as client:
        yield client


def public_url(key: str) -> str:
    return f"{S3_PUBLIC_URL}/{S3_BUCKET}/{key}"


def key_from_url(url: str) -> str | None:
    prefix = f"{S3_PUBLIC_URL}/{S3_BUCKET}/"
    if url.startswith(prefix):
        return url[len(prefix) :]
    return None


async def connect() -> None:
    """Create the image bucket if it is missing. Fails fast when S3 is down."""
    async with s3_client() as s3:
        try:
            await s3.head_bucket(Bucket=S3_BUCKET)
            return
        except ClientError:
            pass
        await s3.create_bucket(Bucket=S3_BUCKET)


async def disconnect() -> None:
    return


async def upload_bytes(body: bytes, *, prefix: str, content_type: str) -> str:
    ext = EXT_BY_TYPE.get(content_type, "bin")
    key = f"{prefix.rstrip('/')}/{uuid.uuid4()}.{ext}"
    async with s3_client() as s3:
        await s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=body,
            ContentType=content_type,
        )
    return public_url(key)


async def delete_object(url: str) -> None:
    key = key_from_url(url)
    if not key:
        return
    async with s3_client() as s3:
        await s3.delete_object(Bucket=S3_BUCKET, Key=key)
