"""Збирання залежностей для контролерів (Dependency Injection).

Тут конкретні реалізації з Infrastructure підставляються в Application-сервіси.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.application.services import AppointmentService, AuthService, SpecialistService
from app.domain.entities import Client
from app.infrastructure.db.database import get_session
from app.infrastructure.db.repositories import (
    SqlAlchemyAppointmentRepository,
    SqlAlchemyClientRepository,
    SqlAlchemySpecialistRepository,
    SqlAlchemyUnitOfWork,
)
from app.infrastructure.security import (
    BcryptPasswordHasher,
    InvalidToken,
    JwtTokenService,
    SystemClock,
)

bearer_scheme = HTTPBearer(auto_error=False)
token_service = JwtTokenService()
clock = SystemClock()
hasher = BcryptPasswordHasher()


def get_auth_service(session: Session = Depends(get_session)) -> AuthService:
    return AuthService(SqlAlchemyClientRepository(session), hasher, SqlAlchemyUnitOfWork(session))


def get_specialist_service(session: Session = Depends(get_session)) -> SpecialistService:
    return SpecialistService(
        SqlAlchemySpecialistRepository(session),
        SqlAlchemyAppointmentRepository(session),
        SqlAlchemyUnitOfWork(session),
        clock,
    )


def get_appointment_service(session: Session = Depends(get_session)) -> AppointmentService:
    return AppointmentService(
        SqlAlchemyAppointmentRepository(session),
        SqlAlchemySpecialistRepository(session),
        SqlAlchemyUnitOfWork(session),
        clock,
    )


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth: AuthService = Depends(get_auth_service),
) -> Client:
    """Поточний користувач з JWT або 401."""
    if credentials is None:
        raise _unauthorized("Потрібна автентифікація")
    try:
        client_id = token_service.read_client_id(credentials.credentials)
    except InvalidToken as error:
        raise _unauthorized(str(error))

    user = auth.get_user(client_id)
    if user is None:
        raise _unauthorized("Користувача не знайдено")
    return user
