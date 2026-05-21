from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.schemas.response import error_response


async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    details = None if isinstance(exc.detail, str) else exc.detail
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(message=message, details=details),
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_response(
            message="Validation failed",
            details=_safe_validation_errors(exc.errors()),
        ),
    )


async def integrity_error_handler(
    request: Request,
    exc: IntegrityError,
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content=error_response(message="Request conflicts with existing data"),
    )


async def sqlalchemy_error_handler(
    request: Request,
    exc: SQLAlchemyError,
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=error_response(message="Database error"),
    )


async def unexpected_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=error_response(message="Internal server error"),
    )


def _safe_validation_errors(errors: list[dict]) -> list[dict]:
    safe_errors = []
    for error in errors:
        safe_error = {
            key: value
            for key, value in error.items()
            if key not in {"input", "url", "ctx"}
        }
        safe_errors.append(safe_error)
    return safe_errors
