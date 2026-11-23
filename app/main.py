"""Точка входу і composition root. Запуск: uvicorn app.main:app --reload

Тут збираються всі шари: Presentation (роутери), Infrastructure (БД, безпека) і Application.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from sqlalchemy import text

from app.application.services import AuthService
from app.infrastructure.config import settings
from app.infrastructure.db import orm_models  # noqa: F401  — реєструє таблиці в Base
from app.infrastructure.db.database import Base, SessionLocal, engine
from app.infrastructure.db.repositories import (
    SqlAlchemyClientRepository,
    SqlAlchemyUnitOfWork,
)
from app.infrastructure.security import BcryptPasswordHasher
from app.presentation.api.errors import register_error_handlers
from app.presentation.api.routers import appointments, auth, specialists


def create_admin_if_missing() -> None:
    if not settings.admin_email or not settings.admin_password:
        return
    with SessionLocal() as session:
        service = AuthService(
            SqlAlchemyClientRepository(session), BcryptPasswordHasher(), SqlAlchemyUnitOfWork(session)
        )
        service.ensure_admin(settings.admin_email, settings.admin_password)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    create_admin_if_missing()
    yield


app = FastAPI(title="Salon API", version="2.0.0", lifespan=lifespan)
register_error_handlers(app)

app.include_router(auth.router)
app.include_router(specialists.router)
app.include_router(appointments.router)


@app.get("/health", tags=["service"])
def health():
    """Перевірка, що сервер працює і бачить базу даних."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


def custom_openapi():
    """У документації Swagger замінюємо 422 на 400, бо API насправді повертає 400."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    for path in schema["paths"].values():
        for operation in path.values():
            responses = operation.get("responses", {})
            if responses.pop("422", None) is not None:
                if "400" in responses:
                    responses["400"]["description"] = "Невалідні дані. " + responses["400"]["description"]
                else:
                    responses["400"] = {"description": "Невалідні дані"}
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi
