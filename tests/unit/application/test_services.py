"""Unit-тести use cases: репозиторії — in-memory фейки, час — фіксований. Без БД і HTTP."""
from datetime import datetime, time, timedelta

import pytest

from app.application.services import AppointmentService, AuthService, SpecialistService
from app.domain.entities import AppointmentStatus, Client, Role
from app.domain.errors import (
    AppointmentNotFound,
    AuthenticationFailed,
    Conflict,
    InvariantViolation,
    PermissionDenied,
    SlotAlreadyTaken,
    SpecialistNotFound,
)
from app.domain.value_objects import Email, Phone
from tests.fakes import (
    FakePasswordHasher,
    FakeUnitOfWork,
    FixedClock,
    InMemoryAppointmentRepository,
    InMemoryClientRepository,
    InMemorySpecialistRepository,
)

NOW = datetime(2030, 1, 1, 12, 0)
MONDAY = datetime(2030, 1, 7)  # понеділок, у майбутньому


def at(hour: int, minute: int = 0, base: datetime = MONDAY) -> datetime:
    return base.replace(hour=hour, minute=minute)


def make_user(user_id: int, role: Role = Role.client) -> Client:
    return Client(
        id=user_id,
        name="Тест",
        email=Email(f"user{user_id}@example.com"),
        phone=Phone("+380671234567"),
        password_hash="x",
        role=role,
    )


ADMIN = make_user(1, Role.admin)
CLIENT = make_user(2)
OTHER = make_user(3)


@pytest.fixture
def repos():
    return {
        "clients": InMemoryClientRepository(),
        "specialists": InMemorySpecialistRepository(),
        "appointments": InMemoryAppointmentRepository(),
        "uow": FakeUnitOfWork(),
        "clock": FixedClock(NOW),
    }


@pytest.fixture
def specialist_service(repos):
    return SpecialistService(repos["specialists"], repos["appointments"], repos["uow"], repos["clock"])


@pytest.fixture
def appointment_service(repos):
    return AppointmentService(repos["appointments"], repos["specialists"], repos["uow"], repos["clock"])


@pytest.fixture
def specialist(specialist_service):
    """Майстер, що працює в понеділок 09:00–18:00."""
    created = specialist_service.create(ADMIN, "Оксана", "перукар")
    specialist_service.add_working_day(ADMIN, created.id, 0, time(9), time(18))
    return created


# ---------- AuthService ----------

def test_register_and_authenticate(repos):
    auth = AuthService(repos["clients"], FakePasswordHasher(), repos["uow"])

    registered = auth.register("Леся", "lesia@example.com", "+380671234567", "secret123")

    assert auth.authenticate("LESIA@example.com", "secret123").id == registered.id
    assert repos["uow"].commits == 1


@pytest.mark.parametrize("email, password", [("lesia@example.com", "wrong-pass"), ("nobody@example.com", "x"), ("bad", "x")])
def test_authenticate_with_wrong_credentials_fails(repos, email, password):
    auth = AuthService(repos["clients"], FakePasswordHasher(), repos["uow"])
    auth.register("Леся", "lesia@example.com", "+380671234567", "secret123")

    with pytest.raises(AuthenticationFailed):
        auth.authenticate(email, password)


# ---------- SpecialistService ----------

def test_client_cannot_create_specialist(specialist_service):
    with pytest.raises(PermissionDenied):
        specialist_service.create(CLIENT, "Оксана", "перукар")


def test_client_does_not_see_inactive_specialist(specialist_service, specialist):
    specialist_service.deactivate(ADMIN, specialist.id)

    assert specialist_service.list(CLIENT) == []
    assert len(specialist_service.list(ADMIN)) == 1
    with pytest.raises(SpecialistNotFound):
        specialist_service.get(CLIENT, specialist.id)


def test_cannot_delete_specialist_with_future_appointments(specialist_service, appointment_service, specialist):
    appointment_service.book(CLIENT, specialist.id, at(10), at(11), None)

    with pytest.raises(Conflict):  # I-13
        specialist_service.delete(ADMIN, specialist.id)


def test_delete_specialist_without_appointments(specialist_service, specialist):
    specialist_service.delete(ADMIN, specialist.id)
    with pytest.raises(SpecialistNotFound):
        specialist_service.get(ADMIN, specialist.id)


# ---------- AppointmentService ----------

def test_book_appointment(appointment_service, specialist, repos):
    appointment = appointment_service.book(CLIENT, specialist.id, at(10), at(11), "стрижка")

    assert appointment.id is not None
    assert appointment.status == AppointmentStatus.booked
    assert repos["uow"].commits >= 1


def test_double_booking_rejected(appointment_service, specialist):
    appointment_service.book(CLIENT, specialist.id, at(10), at(11), None)
    with pytest.raises(SlotAlreadyTaken):
        appointment_service.book(OTHER, specialist.id, at(10, 30), at(11, 30), None)


def test_client_sees_only_own_appointments(appointment_service, specialist):
    appointment_service.book(CLIENT, specialist.id, at(10), at(11), None)
    appointment_service.book(OTHER, specialist.id, at(12), at(13), None)

    assert len(appointment_service.list(CLIENT)) == 1
    assert len(appointment_service.list(ADMIN)) == 2


def test_foreign_appointment_is_not_found(appointment_service, specialist):
    appointment = appointment_service.book(CLIENT, specialist.id, at(10), at(11), None)
    with pytest.raises(AppointmentNotFound):
        appointment_service.get(OTHER, appointment.id)


def test_reschedule_over_itself_is_allowed(appointment_service, specialist):
    appointment = appointment_service.book(CLIENT, specialist.id, at(10), at(11), None)

    moved = appointment_service.update(CLIENT, appointment.id, at(10, 30), at(11, 30), None)

    assert moved.time.start == at(10, 30)


def test_reschedule_requires_both_start_and_end(appointment_service, specialist):
    appointment = appointment_service.book(CLIENT, specialist.id, at(10), at(11), None)
    with pytest.raises(InvariantViolation):
        appointment_service.update(CLIENT, appointment.id, at(12), None, None)


def test_client_cannot_cancel_2_hours_before_but_admin_can(appointment_service, specialist, repos):
    appointment = appointment_service.book(CLIENT, specialist.id, at(10), at(11), None)
    repos["clock"].current = at(9)  # «перемотуємо» час: до початку 1 година

    with pytest.raises(Conflict):  # I-12
        appointment_service.cancel(CLIENT, appointment.id)
    assert appointment_service.cancel(ADMIN, appointment.id).status == AppointmentStatus.cancelled


def test_complete_after_start(appointment_service, specialist, repos):
    appointment = appointment_service.book(CLIENT, specialist.id, at(10), at(11), None)

    with pytest.raises(Conflict):
        appointment_service.complete(ADMIN, appointment.id)  # ще не почався

    repos["clock"].current = at(10, 30)
    assert appointment_service.complete(ADMIN, appointment.id).status == AppointmentStatus.completed


def test_client_cannot_complete(appointment_service, specialist, repos):
    appointment = appointment_service.book(CLIENT, specialist.id, at(10), at(11), None)
    repos["clock"].current = at(10, 30)
    with pytest.raises(PermissionDenied):
        appointment_service.complete(CLIENT, appointment.id)


def test_booking_does_not_depend_on_real_time(appointment_service, specialist, repos):
    """Завдяки порту Clock «зараз» задається в тесті: запис на 2030 рік — уже минуле."""
    repos["clock"].current = MONDAY + timedelta(days=1)
    with pytest.raises(InvariantViolation, match="минулому"):
        appointment_service.book(CLIENT, specialist.id, at(10), at(11), None)
