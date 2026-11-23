"""Доменні фабрики: прості інваріанти + складні через фейкові репозиторії. Без БД."""
from datetime import datetime, time, timedelta

import pytest

from app.domain.entities import Appointment, AppointmentStatus, Client, Role, Specialist
from app.domain.errors import (
    EmailAlreadyRegistered,
    InvariantViolation,
    SlotAlreadyTaken,
    SpecialistNotFound,
)
from app.domain.factories import (
    AppointmentFactory,
    BookingPolicy,
    ClientFactory,
    SpecialistFactory,
)
from app.domain.value_objects import Email, Phone, TimeRange, WorkingHours
from tests.fakes import (
    FakePasswordHasher,
    InMemoryAppointmentRepository,
    InMemoryClientRepository,
    InMemorySpecialistRepository,
)

NOW = datetime(2030, 1, 1, 12, 0)
MONDAY_10 = datetime(2030, 1, 7, 10, 0)  # у майбутньому відносно NOW


# ---------- ClientFactory ----------

@pytest.fixture
def clients():
    return InMemoryClientRepository()


@pytest.fixture
def client_factory(clients):
    return ClientFactory(clients, FakePasswordHasher())


def test_client_factory_creates_client_with_hashed_password(client_factory):
    client = client_factory.create("Леся", "Lesia@Example.com", "+380671234567", "secret123")

    assert client.email == Email("lesia@example.com")
    assert client.role == Role.client
    assert client.password_hash != "secret123"


@pytest.mark.parametrize(
    "field, value",
    [("email", "not-an-email"), ("phone", "123"), ("password", "short"), ("name", "  ")],
)
def test_client_factory_rejects_invalid_data(client_factory, field, value):
    data = {"name": "Леся", "email": "lesia@example.com", "phone": "+380671234567", "password": "secret123"}
    data[field] = value
    with pytest.raises(InvariantViolation):
        client_factory.create(**data)


def test_client_factory_rejects_taken_email(clients, client_factory):
    clients.add(client_factory.create("Леся", "lesia@example.com", "+380671234567", "secret123"))

    with pytest.raises(EmailAlreadyRegistered):  # I-2 — складний інваріант через репозиторій
        client_factory.create("Інша", "LESIA@example.com", "+380501112233", "secret123")


# ---------- SpecialistFactory ----------

def test_specialist_factory_creates_active_specialist():
    specialist = SpecialistFactory.create("Оксана", "перукар")
    assert specialist.is_active and specialist.working_days == []


# ---------- AppointmentFactory ----------

@pytest.fixture
def specialists():
    repo = InMemorySpecialistRepository()
    specialist = Specialist(id=None, name="Оксана", specialization="перукар")
    specialist.add_working_day(0, WorkingHours(time(9), time(18)))  # понеділок
    repo.add(specialist)
    return repo


@pytest.fixture
def appointments():
    return InMemoryAppointmentRepository()


@pytest.fixture
def factory(specialists, appointments):
    return AppointmentFactory(specialists, BookingPolicy(appointments))


CLIENT = Client(id=10, name="Леся", email=Email("l@example.com"), phone=Phone("+380671234567"), password_hash="x")


def book(factory, start=MONDAY_10, hours=1, specialist_id=1):
    return factory.create(CLIENT, specialist_id, start, start + timedelta(hours=hours), None, NOW)


def test_appointment_factory_creates_booked_appointment(factory):
    appointment = book(factory)
    assert appointment.status == AppointmentStatus.booked
    assert appointment.client_id == CLIENT.id


def test_appointment_in_past_rejected(factory):
    with pytest.raises(InvariantViolation, match="минулому"):  # I-7
        book(factory, start=NOW - timedelta(days=1))


def test_appointment_for_missing_specialist_rejected(factory):
    with pytest.raises(SpecialistNotFound):
        book(factory, specialist_id=999)


def test_appointment_outside_schedule_rejected(factory):
    tuesday = MONDAY_10 + timedelta(days=1)
    with pytest.raises(InvariantViolation, match="не працює"):  # I-8
        book(factory, start=tuesday)


def test_overlapping_appointment_rejected(factory, appointments):
    existing = Appointment(id=None, client_id=99, specialist_id=1, time=TimeRange(MONDAY_10, MONDAY_10 + timedelta(hours=1)))
    appointments.add(existing)

    with pytest.raises(SlotAlreadyTaken):  # I-9 — складний інваріант через репозиторій
        book(factory, start=MONDAY_10 + timedelta(minutes=30))


def test_cancelled_appointment_does_not_block_time(factory, appointments):
    cancelled = Appointment(
        id=None,
        client_id=99,
        specialist_id=1,
        time=TimeRange(MONDAY_10, MONDAY_10 + timedelta(hours=1)),
        status=AppointmentStatus.cancelled,
    )
    appointments.add(cancelled)

    assert book(factory).status == AppointmentStatus.booked
