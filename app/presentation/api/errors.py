"""Перетворення доменних помилок і помилок валідації у HTTP-відповіді.

Це єдине місце, де доменні помилки «зустрічаються» з HTTP-статусами.
"""
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.errors import (
    AuthenticationFailed,
    Conflict,
    DomainError,
    InvariantViolation,
    NotFound,
    PermissionDenied,
)

STATUS_BY_ERROR: list[tuple[type[DomainError], int]] = [
    (InvariantViolation, status.HTTP_400_BAD_REQUEST),
    (AuthenticationFailed, status.HTTP_401_UNAUTHORIZED),
    (PermissionDenied, status.HTTP_403_FORBIDDEN),
    (NotFound, status.HTTP_404_NOT_FOUND),
    (Conflict, status.HTTP_409_CONFLICT),
]


def status_for(error: DomainError) -> int:
    for error_type, code in STATUS_BY_ERROR:
        if isinstance(error, error_type):
            return code
    return status.HTTP_400_BAD_REQUEST


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError):
        code = status_for(exc)
        headers = {"WWW-Authenticate": "Bearer"} if code == status.HTTP_401_UNAUTHORIZED else None
        return JSONResponse(status_code=code, content={"detail": exc.message}, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        """Неправильна структура запиту (не той тип, немає поля) → 400 замість стандартного 422."""
        errors = [
            {"field": ".".join(str(p) for p in err["loc"][1:]) or None, "message": err["msg"]}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Невалідні дані", "errors": errors},
        )
