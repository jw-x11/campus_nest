from fastapi import HTTPException, UploadFile

from config.s3db_config import ALLOWED_TYPES, MAX_BYTES

async def read_image(file: UploadFile) -> tuple[bytes, str]:
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="UNSUPPORTED_MEDIA_TYPE")
    body = await file.read()
    if len(body) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="FILE_TOO_LARGE")
    if not body:
        raise HTTPException(status_code=400, detail="EMPTY_FILE")
    return body, content_type