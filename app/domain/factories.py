"""Доменні фабрики та сервіси: створення об'єктів з перевіркою інваріантів.

Прості інваріанти перевіряються без БД (value objects, сутності).
Складні — через інтерфейси репозиторіїв, які фабрика отримує ззовні (DIP).
"""
from datetime import datetime

from app.domain.entities import Appointment, AppointmentStatus, Client, Role, Specialist
from app.domain.errors import (
    EmailAlreadyRegistered,
    InvariantViolation,
    SlotAlreadyTaken,
    SpecialistNotFound,
)
from app.domain.ports import (
    AppointmentRepository,
    ClientRepository,
    PasswordHasher,
    SpecialistRepository,
)
from app.domain.value_objects import Email, Phone, TimeRange, require_text

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 72  # обмеження bcrypt


class ClientFactory:
    def __init__(self, clients: ClientRepository, hasher: PasswordHasher):
        self._clients = clients
        self._hasher = hasher

    def create(self, name: str, email: str, phone: str, password: str, role: Role = Role.client) -> Client:
        # Прості інваріанти
        valid_name = require_text(name, "ім'я", 100)
        valid_email = Email(email)  # I-1
        valid_phone = Phone(phone)
        if not MIN_PASSWORD_LENGTH <= len(password or "") <= MAX_PASSWORD_LENGTH:  # I-3
            raise InvariantViolation(
                f"Пароль має містити від {MIN_PASSWORD_LENGTH} до {MAX_PASSWORD_LENGTH} символів"
            )

        # Складний інваріант — потребує даних з БД (I-2)
        if self._clients.get_by_email(valid_email) is not None:
            raise EmailAlreadyRegistered()

        return Client(
            id=None,
            name=valid_name,
            email=valid_email,
            phone=valid_phone,
            password_hash=self._hasher.hash(password),
            role=role,
        )


class SpecialistFactory:
    @staticmethod
    def create(name: str, specialization: str) -> Specialist:
        return Specialist(id=None, name=name, specialization=specialization, is_active=True)


class BookingPolicy:
    """Доменний сервіс: чи можна зайняти час у майстра. Використовується при створенні і перенесенні."""

    def __init__(self, appointments: AppointmentRepository):
        self._appointments = appointments

    def ensure_available(
        self,
        specialist: Specialist,
        period: TimeRange,
        now: datetime,
        exclude_appointment_id: int | None = None,
    ) -> None:
        if period.start <= now:  # I-7
            raise InvariantViolation("Не можна записатися на час у минулому")
        specialist.ensure_can_take(period)  # I-8, I-10
        if self._appointments.has_overlapping(specialist.id, period, exclude_appointment_id):  # I-9
            raise SlotAlreadyTaken()


class AppointmentFactory:
    def __init__(self, specialists: SpecialistRepository, policy: BookingPolicy):
        self._specialists = specialists
        self._policy = policy

    def create(
        self,
        client: Client,
        specialist_id: int,
        start: datetime,
        end: datetime,
        comment: str | None,
        now: datetime,
    ) -> Appointment:
        period = TimeRange(start, end)  # I-6

        specialist = self._specialists.get_for_booking(specialist_id)
        if specialist is None:
            raise SpecialistNotFound()
        self._policy.ensure_available(specialist, period, now)

        return Appointment(
            id=None,
            client_id=client.id,
            specialist_id=specialist.id,
            time=period,
            status=AppointmentStatus.booked,
            comment=comment,
        )
