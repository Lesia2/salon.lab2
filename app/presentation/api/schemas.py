"""DTO для HTTP: формат запитів і відповідей.

Тут лише структура і типи даних. Бізнес-правила (валідність email, часові діапазони тощо)
перевіряє домен, а не ці схеми.
"""
from datetime import datetime, time

from pydantic import BaseModel, Field

from app.domain.entities import (
    Appointment,
    AppointmentStatus,
    Client,
    Role,
    Specialist,
    WorkingDay,
)

# ---------- Помилки (для документації Swagger) ----------

class ErrorResponse(BaseModel):
    detail: str


def error_responses(**codes: str) -> dict:
    """Опис кодів помилок для Swagger: error_responses(e404="Не знайдено") → {404: {...}}."""
    return {
        int(code[1:]): {"model": ErrorResponse, "description": description}
        for code, description in codes.items()
    }


AUTH_REQUIRED = error_responses(e401="Немає токена, або він невалідний чи прострочений")
ADMIN_ONLY = error_responses(e403="Дія доступна лише адміністратору")


# ---------- Автентифікація ----------

class RegisterRequest(BaseModel):
    name: str
    email: str
    phone: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ClientResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    role: Role

    @classmethod
    def from_domain(cls, client: Client) -> "ClientResponse":
        return cls(
            id=client.id,
            name=client.name,
            email=client.email.value,
            phone=client.phone.value,
            role=client.role,
        )


# ---------- Майстри та графік ----------

class SpecialistRequest(BaseModel):
    name: str
    specialization: str


class ScheduleRequest(BaseModel):
    weekday: int = Field(description="0 = понеділок … 6 = неділя")
    start_time: time = Field(examples=["09:00"])
    end_time: time = Field(examples=["18:00"])


class ScheduleResponse(BaseModel):
    id: int
    specialist_id: int
    weekday: int
    start_time: time
    end_time: time

    @classmethod
    def from_domain(cls, day: WorkingDay, specialist_id: int) -> "ScheduleResponse":
        return cls(
            id=day.id,
            specialist_id=specialist_id,
            weekday=day.weekday,
            start_time=day.hours.start,
            end_time=day.hours.end,
        )


class SpecialistResponse(BaseModel):
    id: int
    name: str
    specialization: str
    is_active: bool

    @classmethod
    def from_domain(cls, specialist: Specialist) -> "SpecialistResponse":
        return cls(
            id=specialist.id,
            name=specialist.name,
            specialization=specialist.specialization,
            is_active=specialist.is_active,
        )


class SpecialistDetailResponse(SpecialistResponse):
    schedules: list[ScheduleResponse]

    @classmethod
    def from_domain(cls, specialist: Specialist) -> "SpecialistDetailResponse":
        return cls(
            **SpecialistResponse.from_domain(specialist).model_dump(),
            schedules=[
                ScheduleResponse.from_domain(day, specialist.id)
                for day in sorted(specialist.working_days, key=lambda d: d.weekday)
            ],
        )


# ---------- Записи ----------

class AppointmentCreateRequest(BaseModel):
    specialist_id: int
    start_at: datetime = Field(examples=["2026-12-01T10:00:00"])
    end_at: datetime = Field(examples=["2026-12-01T11:00:00"])
    comment: str | None = None


class AppointmentUpdateRequest(BaseModel):
    """Перенесення: новий час (обидва поля разом) та/або новий коментар."""

    start_at: datetime | None = Field(default=None, examples=["2026-12-01T12:00:00"])
    end_at: datetime | None = Field(default=None, examples=["2026-12-01T13:00:00"])
    comment: str | None = None


class AppointmentResponse(BaseModel):
    id: int
    client_id: int
    specialist_id: int
    start_at: datetime
    end_at: datetime
    status: AppointmentStatus
    comment: str | None
    created_at: datetime | None

    @classmethod
    def from_domain(cls, appointment: Appointment) -> "AppointmentResponse":
        return cls(
            id=appointment.id,
            client_id=appointment.client_id,
            specialist_id=appointment.specialist_id,
            start_at=appointment.time.start,
            end_at=appointment.time.end,
            status=appointment.status,
            comment=appointment.comment,
            created_at=appointment.created_at,
        )


def to_local_naive(value: datetime | None) -> datetime | None:
    """Час із часовим поясом переводимо в локальний без поясу — так його зберігає домен."""
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone().replace(tzinfo=None)
    return value.replace(microsecond=0)

