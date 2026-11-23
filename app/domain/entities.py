"""Доменні сутності та агрегати (Rich Domain Model).

Сутності не залежать від БД і фреймворків: це звичайні Python-класи,
які зберігають дані й самі захищають свої інваріанти.
"""
import enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.domain.errors import (
    Conflict,
    InvariantViolation,
    WorkingDayAlreadyExists,
    WorkingDayNotFound,
)
from app.domain.value_objects import Email, Phone, TimeRange, WorkingHours, require_text

MAX_COMMENT_LENGTH = 500


class Role(str, enum.Enum):
    client = "client"
    admin = "admin"


class AppointmentStatus(str, enum.Enum):
    booked = "booked"
    cancelled = "cancelled"
    completed = "completed"


# ---------- Client ----------

@dataclass
class Client:
    id: int | None
    name: str
    email: Email
    phone: Phone
    password_hash: str
    role: Role = Role.client
    created_at: datetime | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == Role.admin


# ---------- Specialist (агрегат разом із робочими днями) ----------

@dataclass
class WorkingDay:
    """Робочий день майстра: день тижня (0 = пн … 6 = нд) і години."""

    id: int | None
    weekday: int
    hours: WorkingHours

    def __post_init__(self):
        if not 0 <= self.weekday <= 6:
            raise InvariantViolation("День тижня має бути від 0 (понеділок) до 6 (неділя)")


@dataclass
class Specialist:
    """Агрегат: майстер керує своїм графіком і вирішує, чи може прийняти клієнта в певний час."""

    id: int | None
    name: str
    specialization: str
    is_active: bool = True
    working_days: list[WorkingDay] = field(default_factory=list)

    def __post_init__(self):
        self.name = require_text(self.name, "ім'я", 100)
        self.specialization = require_text(self.specialization, "спеціалізація", 100)

    # --- профіль ---

    def update_profile(self, name: str, specialization: str) -> None:
        self.name = require_text(name, "ім'я", 100)
        self.specialization = require_text(specialization, "спеціалізація", 100)

    def deactivate(self) -> None:
        self.is_active = False

    # --- графік ---

    def add_working_day(self, weekday: int, hours: WorkingHours) -> WorkingDay:
        """I-5: не більше одного запису графіка на день тижня."""
        if self.working_hours_on(weekday) is not None:
            raise WorkingDayAlreadyExists()
        day = WorkingDay(id=None, weekday=weekday, hours=hours)
        self.working_days.append(day)
        return day

    def change_working_day(self, day_id: int, weekday: int, hours: WorkingHours) -> WorkingDay:
        day = self._find_day(day_id)
        if any(d.weekday == weekday and d.id != day_id for d in self.working_days):
            raise WorkingDayAlreadyExists()
        new_day = WorkingDay(id=day.id, weekday=weekday, hours=hours)  # перевірка weekday
        day.weekday, day.hours = new_day.weekday, new_day.hours
        return day

    def remove_working_day(self, day_id: int) -> None:
        self.working_days.remove(self._find_day(day_id))

    def has_working_day(self, day_id: int) -> bool:
        return any(d.id == day_id for d in self.working_days)

    def working_hours_on(self, weekday: int) -> WorkingHours | None:
        return next((d.hours for d in self.working_days if d.weekday == weekday), None)

    # --- запис клієнтів ---

    def ensure_can_take(self, period: TimeRange) -> None:
        """I-10: майстер активний; I-8: час у межах робочих годин."""
        if not self.is_active:
            raise InvariantViolation("Майстер зараз не приймає записи")
        hours = self.working_hours_on(period.weekday)
        if hours is None:
            raise InvariantViolation("Майстер не працює в цей день")
        if not hours.contains(period):
            raise InvariantViolation(f"Час виходить за робочі години майстра ({hours})")

    def _find_day(self, day_id: int) -> WorkingDay:
        for day in self.working_days:
            if day.id == day_id:
                return day
        raise WorkingDayNotFound()


# ---------- Appointment ----------

@dataclass
class Appointment:
    """Запис клієнта до майстра. Сам контролює, які зміни статусу дозволені."""

    CHANGE_DEADLINE = timedelta(hours=2)  # I-12

    id: int | None
    client_id: int
    specialist_id: int
    time: TimeRange
    status: AppointmentStatus = AppointmentStatus.booked
    comment: str | None = None
    created_at: datetime | None = None

    def __post_init__(self):
        self.comment = self._validate_comment(self.comment)

    def is_owned_by(self, client: Client) -> bool:
        return self.client_id == client.id

    @property
    def is_active(self) -> bool:
        return self.status == AppointmentStatus.booked

    def ensure_changeable(self, by_admin: bool, now: datetime) -> None:
        """I-11: лише статус booked; I-12: клієнт — не пізніше ніж за 2 години до початку."""
        if not self.is_active:
            raise Conflict(f"Запис у статусі «{self.status.value}» змінити не можна")
        if not by_admin and self.time.time_until_start(now) < self.CHANGE_DEADLINE:
            raise Conflict("Змінити або скасувати запис можна не пізніше ніж за 2 години до початку")

    def reschedule(self, new_time: TimeRange, by_admin: bool, now: datetime) -> None:
        """Доступність нового часу (графік, перетини) перевіряє BookingPolicy до виклику."""
        self.ensure_changeable(by_admin, now)
        self.time = new_time

    def change_comment(self, comment: str | None, by_admin: bool, now: datetime) -> None:
        self.ensure_changeable(by_admin, now)
        self.comment = self._validate_comment(comment)

    def cancel(self, by_admin: bool, now: datetime) -> None:
        self.ensure_changeable(by_admin, now)
        self.status = AppointmentStatus.cancelled

    def complete(self, now: datetime) -> None:
        if not self.is_active:
            raise Conflict(f"Запис у статусі «{self.status.value}» завершити не можна")
        if self.time.start > now:
            raise Conflict("Запис ще не почався")
        self.status = AppointmentStatus.completed

    @staticmethod
    def _validate_comment(comment: str | None) -> str | None:
        if comment is not None and len(comment) > MAX_COMMENT_LENGTH:
            raise InvariantViolation(f"Коментар не може бути довшим за {MAX_COMMENT_LENGTH} символів")
        return comment
