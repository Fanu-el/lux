from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiError(BaseModel):
    message: str
    details: object | None = None


class ApiResponse(BaseModel, Generic[T]):
    data: T | None
    error: ApiError | None
    is_error: bool


def success_response(data: T | None = None) -> dict[str, object]:
    return {
        "data": data,
        "error": None,
        "is_error": False,
    }


def error_response(message: str, details: object | None = None) -> dict[str, object]:
    return {
        "data": None,
        "error": {
            "message": message,
            "details": details,
        },
        "is_error": True,
    }

