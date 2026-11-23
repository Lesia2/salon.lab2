"""Integration-тести: майстри та графік (UC-03, UC-04, UC-05)."""
from datetime import datetime, timedelta

from app.domain.entities import AppointmentStatus
from app.infrastructure.db.orm_models import AppointmentORM, SpecialistORM

SPEC = {"name": "Оксана", "specialization": "перукар"}
MONDAY = {"weekday": 0, "start_time": "09:00", "end_time": "18:00"}


def create_specialist(api, admin_headers, **overrides) -> dict:
    response = api.post("/specialists", json={**SPEC, **overrides}, headers=admin_headers)
    assert response.status_code == 201
    return response.json()


# ---------- UC-04: керування майстрами ----------

def test_admin_creates_specialist(api, admin_headers):
    body = create_specialist(api, admin_headers)
    assert body["name"] == "Оксана"
    assert body["is_active"] is True


def test_client_cannot_create_specialist(api, client_headers):
    response = api.post("/specialists", json=SPEC, headers=client_headers)
    assert response.status_code == 403


def test_create_specialist_with_blank_name_returns_400(api, admin_headers):
    response = api.post("/specialists", json={**SPEC, "name": "  "}, headers=admin_headers)
    assert response.status_code == 400


def test_admin_updates_specialist(api, admin_headers):
    spec = create_specialist(api, admin_headers)
    response = api.put(
        f"/specialists/{spec['id']}",
        json={"name": "Оксана К.", "specialization": "колорист"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["specialization"] == "колорист"


def test_update_missing_specialist_returns_404(api, admin_headers):
    response = api.put("/specialists/9999", json=SPEC, headers=admin_headers)
    assert response.status_code == 404


def test_delete_specialist_without_future_appointments(api, admin_headers):
    spec = create_specialist(api, admin_headers)

    assert api.delete(f"/specialists/{spec['id']}", headers=admin_headers).status_code == 204
    assert api.get(f"/specialists/{spec['id']}", headers=admin_headers).status_code == 404


def test_delete_specialist_with_future_appointment_returns_409(api, db, admin_headers, client_user, specialist):
    start = datetime.now().replace(microsecond=0) + timedelta(days=3)
    db.add(
        AppointmentORM(
            client_id=client_user.id,
            specialist_id=specialist.id,
            start_at=start,
            end_at=start + timedelta(hours=1),
            status=AppointmentStatus.booked,
        )
    )
    db.commit()

    response = api.delete(f"/specialists/{specialist.id}", headers=admin_headers)

    assert response.status_code == 409  # I-13


# ---------- UC-03: перегляд ----------

def test_client_sees_only_active_specialists(api, db, admin_headers, client_headers):
    active = create_specialist(api, admin_headers, name="Активна")
    inactive = create_specialist(api, admin_headers, name="Неактивна")
    api.patch(f"/specialists/{inactive['id']}/deactivate", headers=admin_headers)

    client_list = api.get("/specialists", headers=client_headers).json()
    admin_list = api.get("/specialists", headers=admin_headers).json()

    assert [s["id"] for s in client_list] == [active["id"]]
    assert len(admin_list) == 2
    assert api.get(f"/specialists/{inactive['id']}", headers=client_headers).status_code == 404


def test_filter_specialists_by_specialization(api, admin_headers, client_headers):
    create_specialist(api, admin_headers, specialization="перукар")
    create_specialist(api, admin_headers, specialization="манікюр")

    response = api.get("/specialists", params={"specialization": "манікюр"}, headers=client_headers)

    assert [s["specialization"] for s in response.json()] == ["манікюр"]


def test_specialist_details_include_schedule(api, admin_headers, client_headers):
    spec = create_specialist(api, admin_headers)
    api.post(f"/specialists/{spec['id']}/schedule", json=MONDAY, headers=admin_headers)

    response = api.get(f"/specialists/{spec['id']}", headers=client_headers)

    assert response.status_code == 200
    assert response.json()["schedules"][0]["start_time"] == "09:00:00"


# ---------- UC-05: графік ----------

def test_admin_adds_schedule(api, admin_headers):
    spec = create_specialist(api, admin_headers)
    response = api.post(f"/specialists/{spec['id']}/schedule", json=MONDAY, headers=admin_headers)
    assert response.status_code == 201


def test_duplicate_weekday_returns_409(api, admin_headers):
    spec = create_specialist(api, admin_headers)
    api.post(f"/specialists/{spec['id']}/schedule", json=MONDAY, headers=admin_headers)

    response = api.post(f"/specialists/{spec['id']}/schedule", json=MONDAY, headers=admin_headers)

    assert response.status_code == 409  # I-5


def test_schedule_with_end_before_start_returns_400(api, admin_headers):
    spec = create_specialist(api, admin_headers)
    response = api.post(
        f"/specialists/{spec['id']}/schedule",
        json={"weekday": 0, "start_time": "18:00", "end_time": "09:00"},
        headers=admin_headers,
    )
    assert response.status_code == 400  # I-4


def test_schedule_for_missing_specialist_returns_404(api, admin_headers):
    response = api.post("/specialists/9999/schedule", json=MONDAY, headers=admin_headers)
    assert response.status_code == 404


def test_update_schedule_to_taken_weekday_returns_409(api, admin_headers):
    spec = create_specialist(api, admin_headers)
    api.post(f"/specialists/{spec['id']}/schedule", json=MONDAY, headers=admin_headers)
    tuesday = api.post(
        f"/specialists/{spec['id']}/schedule", json={**MONDAY, "weekday": 1}, headers=admin_headers
    ).json()

    response = api.put(f"/schedules/{tuesday['id']}", json=MONDAY, headers=admin_headers)

    assert response.status_code == 409


def test_delete_schedule(api, admin_headers):
    spec = create_specialist(api, admin_headers)
    schedule = api.post(f"/specialists/{spec['id']}/schedule", json=MONDAY, headers=admin_headers).json()

    assert api.delete(f"/schedules/{schedule['id']}", headers=admin_headers).status_code == 204
    assert api.delete(f"/schedules/{schedule['id']}", headers=admin_headers).status_code == 404


def test_client_cannot_manage_schedule(api, db, client_headers):
    spec = SpecialistORM(name="Оксана", specialization="перукар", is_active=True)
    db.add(spec)
    db.commit()

    response = api.post(f"/specialists/{spec.id}/schedule", json=MONDAY, headers=client_headers)

    assert response.status_code == 403
