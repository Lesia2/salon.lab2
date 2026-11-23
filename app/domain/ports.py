"""Порти — інтерфейси, які визначає домен, а реалізує Infrastructure (DIP).

Домен не знає, чи дані лежать у MySQL, у пам'яті чи деінде.
"""
from abc import ABC, abstractmethod
from datetime import date, datetime

from app.domain.entities import Appointment, AppointmentStatus, Client, Specialist
from app.domain.value_objects import Email, TimeRange


class ClientRepository(ABC):
    @abstractmethod
    def get(self, client_id: int) -> Client | None: ...

    @abstractmethod
    def get_by_email(self, email: Email) -> Client | None: ...

    @abstractmethod
    def add(self, client: Client) -> Client: ...


class SpecialistRepository(ABC):
    @abstractmethod
    def get(self, specialist_id: int) -> Specialist | None: ...

    @abstractmethod
    def get_for_booking(self, specialist_id: int) -> Specialist | None:
        """Як get, але блокує майстра до кінця транзакції — щоб два записи не зайняли один час."""

    @abstractmethod
    def get_by_working_day(self, working_day_id: int) -> Specialist | None: ...

    @abstractmethod
    def list(self, only_active: bool, specialization: str | None = None) -> list[Specialist]: ...

    @abstractmethod
    def add(self, specialist: Specialist) -> Specialist: ...

    @abstractmethod
    def save(self, specialist: Specialist) -> Specialist: ...

    @abstractmethod
    def delete(self, specialist: Specialist) -> None: ...


class AppointmentRepository(ABC):
    @abstractmethod
    def get(self, appointment_id: int) -> Appointment | None: ...

    @abstractmethod
    def list(
        self,
        client_id: int | None = None,
        status: AppointmentStatus | None = None,
        specialist_id: int | None = None,
        day: date | None = None,
    ) -> list[Appointment]: ...

    @abstractmethod
    def has_overlapping(
        self, specialist_id: int, period: TimeRange, exclude_id: int | None = None
    ) -> bool:
        """Чи є в майстра активний запис, що перетинається з period."""

    @abstractmethod
    def has_future_active(self, specialist_id: int, now: datetime) -> bool: ...

    @abstractmethod
    def add(self, appointment: Appointment) -> Appointment: ...

    @abstractmethod
    def save(self, appointment: Appointment) -> Appointment: ...


class PasswordHasher(ABC):
    @abstractmethod
    def hash(self, password: str) -> str: ...

    @abstractmethod
    def verify(self, password: str, password_hash: str) -> bool: ...


class Clock(ABC):
    """Поточний час. Окремий порт, щоб у тестах можна було «зупинити» час."""

    @abstractmethod
    def now(self) -> datetime: ...


class UnitOfWork(ABC):
    """Межі транзакції: зміни зберігаються лише після commit."""

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...
