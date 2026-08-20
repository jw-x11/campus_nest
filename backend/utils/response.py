from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import Any

def success_response(message: str = "Success Response", data: Any = None) -> dict:
    content = {
        "code": 200,
        "message": message,
        "data": data
    }
    # Convert any content to a JSON-encodable format (ORM object, pydantic model, etc.)
    return JSONResponse(status_code=200, content=jsonable_encoder(content))
