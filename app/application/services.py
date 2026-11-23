"""Application Layer: use cases.

Оркеструють роботу: дістають дані через порти, викликають доменні об'єкти,
перевіряють права, фіксують транзакцію. Бізнес-правил тут немає — вони в домені.
"""
from datetime import date, datetime, time

from app.domain.entities import (
    Appointment,
    AppointmentStatus,
    Client,
    Role,
    Specialist,
    WorkingDay,
)
from app.domain.errors import (
    AppointmentNotFound,
    AuthenticationFailed,
    Conflict,
    InvariantViolation,
    PermissionDenied,
    SpecialistNotFound,
    WorkingDayNotFound,
)
from app.domain.factories import (
    AppointmentFactory,
    BookingPolicy,
    ClientFactory,
    SpecialistFactory,
)
from app.domain.ports import (
    AppointmentRepository,
    ClientRepository,
    Clock,
    PasswordHasher,
    SpecialistRepository,
    UnitOfWork,
)
from app.domain.value_objects import Email, TimeRange, WorkingHours


def require_admin(actor: Client) -> None:
    if not actor.is_admin:
        raise PermissionDenied("Доступ лише для адміністратора")


# ---------- UC-01, UC-02: автентифікація ----------

class AuthService:
    def __init__(self, clients: ClientRepository, hasher: PasswordHasher, uow: UnitOfWork):
        self._clients = clients
        self._hasher = hasher
        self._uow = uow
        self._factory = ClientFactory(clients, hasher)

    def register(self, name: str, email: str, phone: str, password: str) -> Client:
        client = self._factory.create(name, email, phone, password)
        client = self._clients.add(client)
        self._uow.commit()
        return client

    def authenticate(self, email: str, password: str) -> Client:
        try:
            client = self._clients.get_by_email(Email(email))
        except InvariantViolation:
            client = None
        if client is None or not self._hasher.verify(password, client.password_hash):
            raise AuthenticationFailed("Невірний email або пароль")
        return client

    def get_user(self, client_id: int) -> Client | None:
        return self._clients.get(client_id)

    def ensure_admin(self, email: str, password: str) -> None:
        """Створює адміністратора, якщо його ще немає (викликається під час старту)."""
        if self._clients.get_by_email(Email(email)) is not None:
            return
        admin = self._factory.create("Адміністратор", email, "+380000000000", password, role=Role.admin)
        self._clients.add(admin)
        self._uow.commit()


# ---------- UC-03 – UC-05: майстри та графік ----------

class SpecialistService:
    def __init__(
        self,
        specialists: SpecialistRepository,
        appointments: AppointmentRepository,
        uow: UnitOfWork,
        clock: Clock,
    ):
        self._specialists = specialists
        self._appointments = appointments
        self._uow = uow
        self._clock = clock

    def list(self, actor: Client, specialization: str | None = None) -> list[Specialist]:
        return self._specialists.list(only_active=not actor.is_admin, specialization=specialization)

    def get(self, actor: Client, specialist_id: int) -> Specialist:
        specialist = self._specialists.get(specialist_id)
        # Клієнт не бачить неактивних майстрів
        if specialist is None or (not specialist.is_active and not actor.is_admin):
            raise SpecialistNotFound()
        return specialist

    def create(self, actor: Client, name: str, specialization: str) -> Specialist:
        require_admin(actor)
        specialist = self._specialists.add(SpecialistFactory.create(name, specialization))
        self._uow.commit()
        return specialist

    def update(self, actor: Client, specialist_id: int, name: str, specialization: str) -> Specialist:
        require_admin(actor)
        specialist = self._get_or_404(specialist_id)
        specialist.update_profile(name, specialization)
        specialist = self._specialists.save(specialist)
        self._uow.commit()
        return specialist

    def deactivate(self, actor: Client, specialist_id: int) -> Specialist:
        require_admin(actor)
        specialist = self._get_or_404(specialist_id)
        specialist.deactivate()
        specialist = self._specialists.save(specialist)
        self._uow.commit()
        return specialist

    def delete(self, actor: Client, specialist_id: int) -> None:
        require_admin(actor)
        specialist = self._get_or_404(specialist_id)
        if self._appointments.has_future_active(specialist.id, self._clock.now()):  # I-13
            raise Conflict("У майстра є майбутні записи. Спершу деактивуйте його або скасуйте записи")
        self._specialists.delete(specialist)
        self._uow.commit()

    def add_working_day(
        self, actor: Client, specialist_id: int, weekday: int, start: time, end: time
    ) -> WorkingDay:
        require_admin(actor)
        specialist = self._get_or_404(specialist_id)
        specialist.add_working_day(weekday, WorkingHours(start, end))
        specialist = self._specialists.save(specialist)
        self._uow.commit()
        return next(d for d in specialist.working_days if d.weekday == weekday)

    def change_working_day(
        self, actor: Client, working_day_id: int, weekday: int, start: time, end: time
    ) -> tuple[int, WorkingDay]:
        """Повертає (id майстра, оновлений робочий день)."""
        require_admin(actor)
        specialist = self._get_by_day_or_404(working_day_id)
        specialist.change_working_day(working_day_id, weekday, WorkingHours(start, end))
        specialist = self._specialists.save(specialist)
        self._uow.commit()
        return specialist.id, next(d for d in specialist.working_days if d.id == working_day_id)

    def remove_working_day(self, actor: Client, working_day_id: int) -> None:
        require_admin(actor)
        specialist = self._get_by_day_or_404(working_day_id)
        specialist.remove_working_day(working_day_id)
        self._specialists.save(specialist)
        self._uow.commit()

    def _get_or_404(self, specialist_id: int) -> Specialist:
        specialist = self._specialists.get(specialist_id)
        if specialist is None:
            raise SpecialistNotFound()
        return specialist

    def _get_by_day_or_404(self, working_day_id: int) -> Specialist:
        specialist = self._specialists.get_by_working_day(working_day_id)
        if specialist is None:
            raise WorkingDayNotFound()
        return specialist


# ---------- UC-06 – UC-10: записи ----------

class AppointmentService:
    def __init__(
        self,
        appointments: AppointmentRepository,
        specialists: SpecialistRepository,
        uow: UnitOfWork,
        clock: Clock,
    ):
        self._appointments = appointments
        self._specialists = specialists
        self._uow = uow
        self._clock = clock
        self._policy = BookingPolicy(appointments)
        self._factory = AppointmentFactory(specialists, self._policy)

    def book(
        self, actor: Client, specialist_id: int, start: datetime, end: datetime, comment: str | None
    ) -> Appointment:
        appointment = self._factory.create(actor, specialist_id, start, end, comment, self._clock.now())
        appointment = self._appointments.add(appointment)
        self._uow.commit()
        return appointment

    def list(
        self,
        actor: Client,
        status: AppointmentStatus | None = None,
        specialist_id: int | None = None,
        day: date | None = None,
    ) -> list[Appointment]:
        client_id = None if actor.is_admin else actor.id  # клієнт бачить лише свої
        return self._appointments.list(client_id=client_id, status=status, specialist_id=specialist_id, day=day)

    def get(self, actor: Client, appointment_id: int) -> Appointment:
        appointment = self._appointments.get(appointment_id)
        # Чужий запис для клієнта — теж «не знайдено», щоб не розкривати, що він існує
        if appointment is None or (not actor.is_admin and not appointment.is_owned_by(actor)):
            raise AppointmentNotFound()
        return appointment

    def update(
        self,
        actor: Client,
        appointment_id: int,
        start: datetime | None,
        end: datetime | None,
        comment: str | None,
    ) -> Appointment:
        if (start is None) != (end is None):
            raise InvariantViolation("Для перенесення потрібно вказати і start_at, і end_at")
        if start is None and comment is None:
            raise InvariantViolation("Немає що змінювати: вкажіть новий час або коментар")

        appointment = self.get(actor, appointment_id)
        now = self._clock.now()

        if start is not None and end is not None:
            new_time = TimeRange(start, end)
            appointment.ensure_changeable(actor.is_admin, now)
            specialist = self._specialists.get_for_booking(appointment.specialist_id)
            self._policy.ensure_available(specialist, new_time, now, exclude_appointment_id=appointment.id)
            appointment.reschedule(new_time, actor.is_admin, now)
        if comment is not None:
            appointment.change_comment(comment, actor.is_admin, now)

        appointment = self._appointments.save(appointment)
        self._uow.commit()
        return appointment

    def cancel(self, actor: Client, appointment_id: int) -> Appointment:
        appointment = self.get(actor, appointment_id)
        appointment.cancel(actor.is_admin, self._clock.now())
        appointment = self._appointments.save(appointment)
        self._uow.commit()
        return appointment

    def complete(self, actor: Client, appointment_id: int) -> Appointment:
        require_admin(actor)
        appointment = self.get(actor, appointment_id)
        appointment.complete(self._clock.now())
        appointment = self._appointments.save(appointment)
        self._uow.commit()
        return appointment
