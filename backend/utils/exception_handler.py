import traceback

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette import status
# Starlette's HTTPException is the parent of FastAPI's, so handling it also
# covers framework-raised errors such as unmatched routes and 405s.
from starlette.exceptions import HTTPException


DEBUG_MODE = True

async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle HTTP exceptions
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
        "code": exc.status_code,
        "message": exc.detail,
        "data": None,
    }

)

async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle request validation failures: bad path/query params, headers or body
    """
    # Build plain dicts rather than returning exc.errors() directly: each entry
    # can carry a "ctx" holding the original exception, which is not JSON serializable.
    errors = [
        {
            "source": error["loc"][0] if error["loc"] else None,
            "field": ".".join(str(part) for part in error["loc"][1:]),
            "message": error["msg"],
        }
        for error in exc.errors()
    ]

    return JSONResponse(
        status_code=400,
        content={
            "code": 400,
            "message": "Invalid request",
            "data": errors if DEBUG_MODE else None
        }
    )


async def integrity_error_handler(request: Request, exc: IntegrityError):
    """
    Handle database integrity constraint errors: when data violates a unique constraint
    """
    error_msg = str(exc.orig)

    if "username_UNIQUE" in error_msg or "Duplicate entry" in error_msg:
        detail = "Username already exists"
    elif "FOREIGN KEY" in error_msg:
        detail = "Associated data does not exist"
    else:
        detail = "Data constraint conflict, please check the input"

    error_data = None
    if DEBUG_MODE:
        error_data = {
            "error_type": "IntegrityError",
            "error_detail": error_msg,
            "path": str(request.url)
        }

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "code": 400,
            "message": detail,
            "data": error_data
        }
    )


async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    """
    Handle SQLAlchemy database errors
    """
    error_data = None
    if DEBUG_MODE:
        error_data = {
            "error_type": type(exc).__name__,
            "error_detail": str(exc),
            "traceback": traceback.format_exc(),
            "path": str(request.url)
        }

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": 500,
            "message": "Database operation failed, please try again later",
            "data": error_data
        }
    )


async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle all uncaught exceptions
    """
 
    error_data = None
    if DEBUG_MODE:
        error_data = {
            "error_type": type(exc).__name__,
            "error_detail": str(exc),

            "traceback": traceback.format_exc(),
            "path": str(request.url)
        }

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": 500,
            "message": "Internal Server Error",
            "data": error_data
        }
    )

