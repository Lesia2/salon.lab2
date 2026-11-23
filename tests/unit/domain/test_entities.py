"""Поведінка доменних сутностей (Rich Domain Model). Без БД і фреймворку."""
from datetime import datetime, time, timedelta

import pytest

from app.domain.entities import Appointment, AppointmentStatus, Specialist
from app.domain.errors import (
    Conflict,
    InvariantViolation,
    WorkingDayAlreadyExists,
    WorkingDayNotFound,
)
from app.domain.value_objects import TimeRange, WorkingHours

NINE_TO_SIX = WorkingHours(time(9), time(18))
MONDAY_10 = datetime(2030, 1, 7, 10, 0)  # понеділок


def make_specialist(**overrides) -> Specialist:
    data = {"id": 1, "name": "Оксана", "specialization": "перукар", "is_active": True}
    return Specialist(**{**data, **overrides})


def make_appointment(start: datetime = MONDAY_10, **overrides) -> Appointment:
    data = {"id": 1, "client_id": 10, "specialist_id": 1, "time": TimeRange(start, start + timedelta(hours=1))}
    return Appointment(**{**data, **overrides})


# ---------- Specialist ----------

def test_specialist_requires_name():
    with pytest.raises(InvariantViolation):
        make_specialist(name="  ")


def test_add_working_day():
    specialist = make_specialist()
    specialist.add_working_day(0, NINE_TO_SIX)
    assert specialist.working_hours_on(0) == NINE_TO_SIX


def test_second_working_day_on_same_weekday_rejected():
    specialist = make_specialist()
    specialist.add_working_day(0, NINE_TO_SIX)
    with pytest.raises(WorkingDayAlreadyExists):  # I-5
        specialist.add_working_day(0, WorkingHours(time(10), time(12)))


@pytest.mark.parametrize("weekday", [-1, 7])
def test_invalid_weekday_rejected(weekday):
    with pytest.raises(InvariantViolation):
        make_specialist().add_working_day(weekday, NINE_TO_SIX)


def test_change_working_day_to_taken_weekday_rejected():
    specialist = make_specialist()
    specialist.add_working_day(0, NINE_TO_SIX).id = 1
    specialist.add_working_day(1, NINE_TO_SIX).id = 2
    with pytest.raises(WorkingDayAlreadyExists):
        specialist.change_working_day(2, 0, NINE_TO_SIX)


def test_remove_unknown_working_day_rejected():
    with pytest.raises(WorkingDayNotFound):
        make_specialist().remove_working_day(99)


def test_specialist_takes_client_within_working_hours():
    specialist = make_specialist()
    specialist.add_working_day(0, NINE_TO_SIX)
    specialist.ensure_can_take(TimeRange(MONDAY_10, MONDAY_10 + timedelta(hours=1)))  # без помилки


def test_specialist_rejects_day_off():
    specialist = make_specialist()
    with pytest.raises(InvariantViolation, match="не працює"):  # I-8
        specialist.ensure_can_take(TimeRange(MONDAY_10, MONDAY_10 + timedelta(hours=1)))


def test_specialist_rejects_time_outside_hours():
    specialist = make_specialist()
    specialist.add_working_day(0, NINE_TO_SIX)
    late = MONDAY_10.replace(hour=17, minute=30)
    with pytest.raises(InvariantViolation, match="робочі години"):  # I-8
        specialist.ensure_can_take(TimeRange(late, late + timedelta(hours=1)))


def test_inactive_specialist_rejects_clients():
    specialist = make_specialist()
    specialist.add_working_day(0, NINE_TO_SIX)
    specialist.deactivate()
    with pytest.raises(InvariantViolation, match="не приймає"):  # I-10
        specialist.ensure_can_take(TimeRange(MONDAY_10, MONDAY_10 + timedelta(hours=1)))


# ---------- Appointment: статуси і правило 2 годин ----------

def test_client_cancels_more_than_2_hours_before():
    appointment = make_appointment()
    appointment.cancel(by_admin=False, now=MONDAY_10 - timedelta(hours=3))
    assert appointment.status == AppointmentStatus.cancelled


def test_client_cannot_cancel_less_than_2_hours_before():
    appointment = make_appointment()
    with pytest.raises(Conflict, match="2 години"):  # I-12
        appointment.cancel(by_admin=False, now=MONDAY_10 - timedelta(hours=1))


def test_exactly_2_hours_before_is_allowed():
    appointment = make_appointment()
    appointment.cancel(by_admin=False, now=MONDAY_10 - timedelta(hours=2))
    assert appointment.status == AppointmentStatus.cancelled


def test_admin_cancels_any_time():
    appointment = make_appointment()
    appointment.cancel(by_admin=True, now=MONDAY_10 - timedelta(minutes=5))
    assert appointment.status == AppointmentStatus.cancelled


def test_cancelled_appointment_cannot_be_changed():
    appointment = make_appointment(status=AppointmentStatus.cancelled)
    with pytest.raises(Conflict):  # I-11
        appointment.cancel(by_admin=True, now=MONDAY_10 - timedelta(days=1))
    with pytest.raises(Conflict):
        appointment.reschedule(
            TimeRange(MONDAY_10, MONDAY_10 + timedelta(hours=1)), by_admin=True, now=MONDAY_10 - timedelta(days=1)
        )


def test_complete_started_appointment():
    appointment = make_appointment()
    appointment.complete(now=MONDAY_10 + timedelta(minutes=30))
    assert appointment.status == AppointmentStatus.completed


def test_cannot_complete_future_appointment():
    with pytest.raises(Conflict, match="не почався"):
        make_appointment().complete(now=MONDAY_10 - timedelta(hours=1))


def test_cannot_complete_cancelled_appointment():
    appointment = make_appointment(status=AppointmentStatus.cancelled)
    with pytest.raises(Conflict):
        appointment.complete(now=MONDAY_10 + timedelta(hours=1))


def test_comment_longer_than_500_rejected():
    with pytest.raises(InvariantViolation):
        make_appointment(comment="x" * 501)
