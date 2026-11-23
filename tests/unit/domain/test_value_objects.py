"""Value Objects: перевіряють себе самі під час створення. Без БД і фреймворку."""
from datetime import datetime, time

import pytest

from app.domain.errors import InvariantViolation
from app.domain.value_objects import Email, Phone, TimeRange, WorkingHours, require_text

# ---------- Email (I-1) ----------

def test_email_is_normalized_to_lowercase():
    assert Email("  Lesia@Example.COM ").value == "lesia@example.com"


@pytest.mark.parametrize("value", ["nope", "a@", "@example.com", "lesia example.com", "", "a@b"])
def test_invalid_email_rejected(value):
    with pytest.raises(InvariantViolation):
        Email(value)


def test_emails_with_same_value_are_equal():
    assert Email("a@example.com") == Email("A@EXAMPLE.com")


# ---------- Phone ----------

def test_phone_spaces_and_dashes_are_removed():
    assert Phone("+380 67 123-45-67").value == "+380671234567"


@pytest.mark.parametrize("value", ["12345", "phone12345", "+38(067)1234567", "1" * 16])
def test_invalid_phone_rejected(value):
    with pytest.raises(InvariantViolation):
        Phone(value)


# ---------- TimeRange (I-6) ----------

def dt(hhmm: str, day: int = 7) -> datetime:
    hours, minutes = map(int, hhmm.split(":"))
    return datetime(2030, 1, day, hours, minutes)


def test_valid_time_range():
    period = TimeRange(dt("10:00"), dt("11:00"))
    assert period.weekday == 0  # 7 січня 2030 — понеділок


@pytest.mark.parametrize(
    "start, end",
    [
        (dt("11:00"), dt("10:00")),  # кінець раніше за початок
        (dt("10:00"), dt("10:00")),  # нульова тривалість
        (dt("23:00"), dt("01:00", day=8)),  # через північ
    ],
)
def test_invalid_time_range_rejected(start, end):
    with pytest.raises(InvariantViolation):
        TimeRange(start, end)


@pytest.mark.parametrize(
    "other, expected",
    [
        (("10:30", "11:30"), True),  # частковий перетин
        (("09:00", "12:00"), True),  # повністю охоплює
        (("10:15", "10:45"), True),  # всередині
        (("11:00", "12:00"), False),  # суміжний після
        (("09:00", "10:00"), False),  # суміжний до
        (("13:00", "14:00"), False),  # окремо
    ],
)
def test_time_range_overlap(other, expected):
    booked = TimeRange(dt("10:00"), dt("11:00"))
    assert booked.overlaps(TimeRange(dt(other[0]), dt(other[1]))) is expected


# ---------- WorkingHours (I-4) ----------

@pytest.mark.parametrize("start, end", [(time(18), time(9)), (time(10), time(10))])
def test_working_hours_start_must_be_before_end(start, end):
    with pytest.raises(InvariantViolation):
        WorkingHours(start, end)


def test_working_hours_contains_period():
    hours = WorkingHours(time(9), time(18))
    assert hours.contains(TimeRange(dt("09:00"), dt("18:00")))
    assert not hours.contains(TimeRange(dt("17:30"), dt("18:30")))
    assert not hours.contains(TimeRange(dt("08:30"), dt("09:30")))


# ---------- Текстові поля ----------

def test_blank_text_rejected():
    with pytest.raises(InvariantViolation):
        require_text("   ", "ім'я", 100)


def test_too_long_text_rejected():
    with pytest.raises(InvariantViolation):
        require_text("x" * 101, "ім'я", 100)
