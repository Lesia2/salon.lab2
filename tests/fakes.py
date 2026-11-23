"""Фейкові in-memory реалізації доменних портів для unit-тестів.

Реалізують ті самі інтерфейси, що й SQLAlchemy-репозиторії, але зберігають дані у словниках.
Завдяки DIP домен і use cases не помічають різниці.
"""
import copy
from datetime import date, datetime
from itertools import count

from app.domain.entities import Appointment, AppointmentStatus, Client, Specialist
from app.domain.ports import (
    AppointmentRepository,
    ClientRepository,
    Clock,
    PasswordHasher,
    SpecialistRepository,
    UnitOfWork,
)
from app.domain.value_objects import Email, TimeRange


class InMemoryClientRepository(ClientRepository):
    def __init__(self):
        self.items: dict[int, Client] = {}
        self._ids = count(1)

    def get(self, client_id: int) -> Client | None:
        return copy.deepcopy(self.items.get(client_id))

    def get_by_email(self, email: Email) -> Client | None:
        return next((copy.deepcopy(c) for c in self.items.values() if c.email == email), None)

    def add(self, client: Client) -> Client:
        client = copy.deepcopy(client)
        client.id = next(self._ids)
        self.items[client.id] = client
        return copy.deepcopy(client)


class InMemorySpecialistRepository(SpecialistRepository):
    def __init__(self):
        self.items: dict[int, Specialist] = {}
        self._ids = count(1)
        self._day_ids = count(1)

    def get(self, specialist_id: int) -> Specialist | None:
        return copy.deepcopy(self.items.get(specialist_id))

    def get_for_booking(self, specialist_id: int) -> Specialist | None:
        return self.get(specialist_id)

    def get_by_working_day(self, working_day_id: int) -> Specialist | None:
        for specialist in self.items.values():
            if specialist.has_working_day(working_day_id):
                return copy.deepcopy(specialist)
        return None

    def list(self, only_active: bool, specialization: str | None = None) -> list[Specialist]:
        return [
            copy.deepcopy(s)
            for s in self.items.values()
            if (not only_active or s.is_active) and (specialization is None or s.specialization == specialization)
        ]

    def add(self, specialist: Specialist) -> Specialist:
        specialist = copy.deepcopy(specialist)
        specialist.id = next(self._ids)
        return self.save(specialist)

    def save(self, specialist: Specialist) -> Specialist:
        specialist = copy.deepcopy(specialist)
        for day in specialist.working_days:
            if day.id is None:
                day.id = next(self._day_ids)
        self.items[specialist.id] = specialist
        return copy.deepcopy(specialist)

    def delete(self, specialist: Specialist) -> None:
        del self.items[specialist.id]


class InMemoryAppointmentRepository(AppointmentRepository):
    def __init__(self):
        self.items: dict[int, Appointment] = {}
        self._ids = count(1)

    def get(self, appointment_id: int) -> Appointment | None:
        return copy.deepcopy(self.items.get(appointment_id))

    def list(
        self,
        client_id: int | None = None,
        status: AppointmentStatus | None = None,
        specialist_id: int | None = None,
        day: date | None = None,
    ) -> list[Appointment]:
        result = [
            a
            for a in self.items.values()
            if (client_id is None or a.client_id == client_id)
            and (status is None or a.status == status)
            and (specialist_id is None or a.specialist_id == specialist_id)
            and (day is None or a.time.start.date() == day)
        ]
        return [copy.deepcopy(a) for a in sorted(result, key=lambda a: a.time.start)]

    def has_overlapping(self, specialist_id: int, period: TimeRange, exclude_id: int | None = None) -> bool:
        return any(
            a.specialist_id == specialist_id and a.is_active and a.id != exclude_id and a.time.overlaps(period)
            for a in self.items.values()
        )

    def has_future_active(self, specialist_id: int, now: datetime) -> bool:
        return any(
            a.specialist_id == specialist_id and a.is_active and a.time.start > now for a in self.items.values()
        )

    def add(self, appointment: Appointment) -> Appointment:
        appointment = copy.deepcopy(appointment)
        appointment.id = next(self._ids)
        return self.save(appointment)

    def save(self, appointment: Appointment) -> Appointment:
        self.items[appointment.id] = copy.deepcopy(appointment)
        return copy.deepcopy(appointment)


class FakePasswordHasher(PasswordHasher):
    """Не хешує по-справжньому — у unit-тестах bcrypt лише сповільнював би запуск."""

    def hash(self, password: str) -> str:
        return f"hashed::{password}"

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == f"hashed::{password}"


class FixedClock(Clock):
    """Годинник, який показує заданий час. Дозволяє тестувати правило «за 2 години» без очікування."""

    def __init__(self, now: datetime):
        self.current = now

    def now(self) -> datetime:
        return self.current


class FakeUnitOfWork(UnitOfWork):
    def __init__(self):
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        pass
