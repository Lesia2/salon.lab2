"""Integration-тести: записи до майстра (UC-06 – UC-10)."""
from datetime import datetime, timedelta

from app.domain.entities import AppointmentStatus
from app.infrastructure.db.orm_models import AppointmentORM, ScheduleORM
from tests.integration.conftest import at


def book(api, headers, specialist_id, day, start, end, **extra):
    return api.post(
        "/appointments",
        json={"specialist_id": specialist_id, "start_at": at(day, start), "end_at": at(day, end), **extra},
        headers=headers,
    )


def insert_appointment(db, client_id, specialist_id, start: datetime, status=AppointmentStatus.booked):
    """Створює запис напряму в БД — для випадків, які не можна створити через API (час у минулому тощо).

    Тривалість до 1 години, але не далі кінця доби: запис має бути в межах одного дня (I-6),
    інакше тест залежав би від того, о котрій його запускають.
    """
    start = start.replace(microsecond=0)
    end_of_day = start.replace(hour=23, minute=59, second=59)
    appointment = AppointmentORM(
        client_id=client_id,
        specialist_id=specialist_id,
        start_at=start,
        end_at=min(start + timedelta(hours=1), end_of_day),
        status=status,
    )
    db.add(appointment)
    db.commit()
    return appointment


# ---------- UC-06: створення ----------

def test_client_books_appointment(api, client_headers, client_user, specialist, future_day):
    response = book(api, client_headers, specialist.id, future_day, "10:00", "11:00", comment="стрижка")

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "booked"
    assert body["client_id"] == client_user.id
    assert body["comment"] == "стрижка"


def test_overlapping_appointment_returns_409(api, client_headers, other_headers, specialist, future_day):
    book(api, client_headers, specialist.id, future_day, "10:00", "11:00")

    response = book(api, other_headers, specialist.id, future_day, "10:30", "11:30")

    assert response.status_code == 409  # I-9


def test_appointment_right_after_another_is_allowed(api, client_headers, other_headers, specialist, future_day):
    book(api, client_headers, specialist.id, future_day, "10:00", "11:00")

    response = book(api, other_headers, specialist.id, future_day, "11:00", "12:00")

    assert response.status_code == 201  # 11:00 — кінець першого і початок другого, перетину немає


def test_cancelled_appointment_does_not_block_time(api, db, client_user, other_headers, specialist, future_day):
    start = datetime.combine(future_day, datetime.min.time()).replace(hour=10)
    insert_appointment(db, client_user.id, specialist.id, start, status=AppointmentStatus.cancelled)

    response = book(api, other_headers, specialist.id, future_day, "10:00", "11:00")

    assert response.status_code == 201


def test_appointment_in_past_returns_400(api, client_headers, specialist):
    yesterday = datetime.now().date() - timedelta(days=1)
    response = book(api, client_headers, specialist.id, yesterday, "10:00", "11:00")
    assert response.status_code == 400  # I-7


def test_appointment_outside_working_hours_returns_400(api, client_headers, specialist, future_day):
    response = book(api, client_headers, specialist.id, future_day, "17:30", "18:30")
    assert response.status_code == 400  # I-8


def test_appointment_on_day_off_returns_400(api, db, client_headers, specialist, future_day):
    db.query(ScheduleORM).filter(ScheduleORM.weekday == future_day.weekday()).delete()
    db.commit()

    response = book(api, client_headers, specialist.id, future_day, "10:00", "11:00")

    assert response.status_code == 400  # I-8: майстер не працює в цей день


def test_appointment_with_inactive_specialist_returns_400(api, db, client_headers, specialist, future_day):
    specialist.is_active = False
    db.commit()

    response = book(api, client_headers, specialist.id, future_day, "10:00", "11:00")

    assert response.status_code == 400  # I-10


def test_appointment_with_missing_specialist_returns_404(api, client_headers, future_day):
    response = book(api, client_headers, 9999, future_day, "10:00", "11:00")
    assert response.status_code == 404


def test_appointment_with_end_before_start_returns_400(api, client_headers, specialist, future_day):
    response = book(api, client_headers, specialist.id, future_day, "12:00", "11:00")
    assert response.status_code == 400  # I-6


# ---------- UC-07: перегляд ----------

def test_client_sees_only_own_appointments(
    api, client_headers, other_headers, admin_headers, specialist, future_day
):
    book(api, client_headers, specialist.id, future_day, "10:00", "11:00")
    book(api, other_headers, specialist.id, future_day, "12:00", "13:00")

    assert len(api.get("/appointments", headers=client_headers).json()) == 1
    assert len(api.get("/appointments", headers=other_headers).json()) == 1
    assert len(api.get("/appointments", headers=admin_headers).json()) == 2


def test_filter_appointments_by_status_and_day(api, client_headers, specialist, future_day):
    first = book(api, client_headers, specialist.id, future_day, "10:00", "11:00").json()
    book(api, client_headers, specialist.id, future_day, "12:00", "13:00")
    api.post(f"/appointments/{first['id']}/cancel", headers=client_headers)

    booked = api.get("/appointments", params={"status": "booked"}, headers=client_headers).json()
    other_day = api.get(
        "/appointments", params={"day": (future_day + timedelta(days=1)).isoformat()}, headers=client_headers
    ).json()

    assert len(booked) == 1
    assert other_day == []


def test_foreign_appointment_returns_404(api, client_headers, other_headers, specialist, future_day):
    appointment = book(api, client_headers, specialist.id, future_day, "10:00", "11:00").json()

    response = api.get(f"/appointments/{appointment['id']}", headers=other_headers)

    assert response.status_code == 404  # чужий запис не розкриваємо


# ---------- UC-08: перенесення ----------

def test_reschedule_appointment(api, client_headers, specialist, future_day):
    appointment = book(api, client_headers, specialist.id, future_day, "10:00", "11:00").json()

    response = api.patch(
        f"/appointments/{appointment['id']}",
        json={"start_at": at(future_day, "14:00"), "end_at": at(future_day, "15:00")},
        headers=client_headers,
    )

    assert response.status_code == 200
    assert response.json()["start_at"] == at(future_day, "14:00")


def test_reschedule_overlapping_itself_is_allowed(api, client_headers, specialist, future_day):
    appointment = book(api, client_headers, specialist.id, future_day, "10:00", "11:00").json()

    response = api.patch(
        f"/appointments/{appointment['id']}",
        json={"start_at": at(future_day, "10:30"), "end_at": at(future_day, "11:30")},
        headers=client_headers,
    )

    assert response.status_code == 200  # запис не конфліктує сам із собою


def test_reschedule_to_taken_time_returns_409(api, client_headers, other_headers, specialist, future_day):
    mine = book(api, client_headers, specialist.id, future_day, "10:00", "11:00").json()
    book(api, other_headers, specialist.id, future_day, "14:00", "15:00")

    response = api.patch(
        f"/appointments/{mine['id']}",
        json={"start_at": at(future_day, "14:30"), "end_at": at(future_day, "15:30")},
        headers=client_headers,
    )

    assert response.status_code == 409


def test_other_client_cannot_reschedule(api, client_headers, other_headers, specialist, future_day):
    appointment = book(api, client_headers, specialist.id, future_day, "10:00", "11:00").json()

    response = api.patch(f"/appointments/{appointment['id']}", json={"comment": "x"}, headers=other_headers)

    assert response.status_code == 404


# ---------- UC-09: скасування ----------

def test_cancel_appointment(api, client_headers, specialist, future_day):
    appointment = book(api, client_headers, specialist.id, future_day, "10:00", "11:00").json()

    response = api.post(f"/appointments/{appointment['id']}/cancel", headers=client_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_cancel_twice_returns_409(api, client_headers, specialist, future_day):
    appointment = book(api, client_headers, specialist.id, future_day, "10:00", "11:00").json()
    api.post(f"/appointments/{appointment['id']}/cancel", headers=client_headers)

    response = api.post(f"/appointments/{appointment['id']}/cancel", headers=client_headers)

    assert response.status_code == 409  # I-11


def test_client_cannot_cancel_less_than_2_hours_before(api, db, client_user, client_headers, specialist):
    soon = insert_appointment(db, client_user.id, specialist.id, datetime.now() + timedelta(hours=1))

    response = api.post(f"/appointments/{soon.id}/cancel", headers=client_headers)

    assert response.status_code == 409  # I-12


def test_admin_can_cancel_less_than_2_hours_before(api, db, client_user, admin_headers, specialist):
    soon = insert_appointment(db, client_user.id, specialist.id, datetime.now() + timedelta(hours=1))

    response = api.post(f"/appointments/{soon.id}/cancel", headers=admin_headers)

    assert response.status_code == 200  # на адміністратора правило 2 годин не діє


# ---------- UC-10: завершення ----------

def test_admin_completes_started_appointment(api, db, client_user, admin_headers, specialist):
    started = insert_appointment(db, client_user.id, specialist.id, datetime.now() - timedelta(minutes=30))

    response = api.post(f"/appointments/{started.id}/complete", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_cannot_complete_future_appointment(api, client_headers, admin_headers, specialist, future_day):
    appointment = book(api, client_headers, specialist.id, future_day, "10:00", "11:00").json()

    response = api.post(f"/appointments/{appointment['id']}/complete", headers=admin_headers)

    assert response.status_code == 409


def test_client_cannot_complete_appointment(api, client_headers, specialist, future_day):
    appointment = book(api, client_headers, specialist.id, future_day, "10:00", "11:00").json()

    response = api.post(f"/appointments/{appointment['id']}/complete", headers=client_headers)

    assert response.status_code == 403
