"""Value Objects — незмінні об'єкти без ідентичності, які самі перевіряють свою валідність."""
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from app.domain.errors import InvariantViolation

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[0-9]{10,15}$")


@dataclass(frozen=True)
class Email:
    """I-1: email має бути валідним. Зберігається в нижньому регістрі."""

    value: str

    def __post_init__(self):
        normalized = (self.value or "").strip().lower()
        if not _EMAIL_RE.match(normalized):
            raise InvariantViolation("Невалідний email")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Phone:
    """Телефон: 10–15 цифр, можна з + на початку. Пробіли й дефіси прибираються."""

    value: str

    def __post_init__(self):
        normalized = (self.value or "").replace(" ", "").replace("-", "")
        if not _PHONE_RE.match(normalized):
            raise InvariantViolation("Телефон має містити 10–15 цифр, можна з + на початку")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class TimeRange:
    """Часовий проміжок запису. I-6: початок раніше за кінець, в межах одного дня."""

    start: datetime
    end: datetime

    def __post_init__(self):
        if self.start >= self.end:
            raise InvariantViolation("Початок запису має бути раніше за кінець")
        if self.start.date() != self.end.date():
            raise InvariantViolation("Запис має починатися і закінчуватися в один день")

    @property
    def weekday(self) -> int:
        return self.start.weekday()

    def overlaps(self, other: "TimeRange") -> bool:
        """Перетин проміжків. Суміжні (10:00–11:00 і 11:00–12:00) не перетинаються."""
        return self.start < other.end and other.start < self.end

    def time_until_start(self, now: datetime) -> timedelta:
        return self.start - now


@dataclass(frozen=True)
class WorkingHours:
    """Робочі години в межах дня. I-4: початок раніше за кінець."""

    start: time
    end: time

    def __post_init__(self):
        if self.start >= self.end:
            raise InvariantViolation("Початок роботи має бути раніше за кінець")

    def contains(self, period: TimeRange) -> bool:
        return self.start <= period.start.time() and period.end.time() <= self.end

    def __str__(self) -> str:
        return f"{self.start:%H:%M}–{self.end:%H:%M}"


def require_text(value: str | None, field: str, max_length: int) -> str:
    """Непорожній текст обмеженої довжини (ім'я, спеціалізація)."""
    text = (value or "").strip()
    if not text:
        raise InvariantViolation(f"Поле «{field}» не може бути порожнім")
    if len(text) > max_length:
        raise InvariantViolation(f"Поле «{field}» не може бути довшим за {max_length} символів")
    return text
