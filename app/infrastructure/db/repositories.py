"""Реалізації репозиторіїв (адаптери) на SQLAlchemy + MySQL."""
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities import Appointment, AppointmentStatus, Client, Specialist
from app.domain.ports import (
    AppointmentRepository,
    ClientRepository,
    SpecialistRepository,
    UnitOfWork,
)
from app.domain.value_objects import Email, TimeRange
from app.infrastructure.db.mappers import (
    appointment_to_domain,
    client_to_domain,
    client_to_orm,
    specialist_to_domain,
    update_appointment_orm,
    update_specialist_orm,
)
from app.infrastructure.db.orm_models import (
    AppointmentORM,
    ClientORM,
    ScheduleORM,
    SpecialistORM,
)


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session: Session):
        self._session = session

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()


class SqlAlchemyClientRepository(ClientRepository):
    def __init__(self, session: Session):
        self._session = session

    def get(self, client_id: int) -> Client | None:
        row = self._session.get(ClientORM, client_id)
        return client_to_domain(row) if row else None

    def get_by_email(self, email: Email) -> Client | None:
        row = self._session.scalar(select(ClientORM).where(ClientORM.email == email.value))
        return client_to_domain(row) if row else None

    def add(self, client: Client) -> Client:
        row = client_to_orm(client)
        self._session.add(row)
        self._session.flush()  # щоб отримати id
        return client_to_domain(row)


class SqlAlchemySpecialistRepository(SpecialistRepository):
    def __init__(self, session: Session):
        self._session = session

    def get(self, specialist_id: int) -> Specialist | None:
        row = self._session.get(SpecialistORM, specialist_id)
        return specialist_to_domain(row) if row else None

    def get_for_booking(self, specialist_id: int) -> Specialist | None:
        # SELECT ... FOR UPDATE: два одночасні записи до одного майстра виконуються по черзі
        row = self._session.get(SpecialistORM, specialist_id, with_for_update=True)
        return specialist_to_domain(row) if row else None

    def get_by_working_day(self, working_day_id: int) -> Specialist | None:
        schedule = self._session.get(ScheduleORM, working_day_id)
        return self.get(schedule.specialist_id) if schedule else None

    def list(self, only_active: bool, specialization: str | None = None) -> list[Specialist]:
        query = select(SpecialistORM).order_by(SpecialistORM.id)
        if only_active:
            query = query.where(SpecialistORM.is_active.is_(True))
        if specialization:
            query = query.where(SpecialistORM.specialization == specialization)
        return [specialist_to_domain(row) for row in self._session.scalars(query)]

    def add(self, specialist: Specialist) -> Specialist:
        row = SpecialistORM()
        update_specialist_orm(row, specialist)
        self._session.add(row)
        self._session.flush()
        return specialist_to_domain(row)

    def save(self, specialist: Specialist) -> Specialist:
        row = self._session.get(SpecialistORM, specialist.id)
        update_specialist_orm(row, specialist)
        self._session.flush()
        self._session.refresh(row)
        return specialist_to_domain(row)

    def delete(self, specialist: Specialist) -> None:
        row = self._session.get(SpecialistORM, specialist.id)
        self._session.delete(row)
        self._session.flush()


class SqlAlchemyAppointmentRepository(AppointmentRepository):
    def __init__(self, session: Session):
        self._session = session

    def get(self, appointment_id: int) -> Appointment | None:
        row = self._session.get(AppointmentORM, appointment_id)
        return appointment_to_domain(row) if row else None

    def list(
        self,
        client_id: int | None = None,
        status: AppointmentStatus | None = None,
        specialist_id: int | None = None,
        day: date | None = None,
    ) -> list[Appointment]:
        query = select(AppointmentORM).order_by(AppointmentORM.start_at)
        if client_id is not None:
            query = query.where(AppointmentORM.client_id == client_id)
        if status is not None:
            query = query.where(AppointmentORM.status == status)
        if specialist_id is not None:
            query = query.where(AppointmentORM.specialist_id == specialist_id)
        if day is not None:
            start = datetime.combine(day, datetime.min.time())
            query = query.where(AppointmentORM.start_at >= start, AppointmentORM.start_at < start + timedelta(days=1))
        return [appointment_to_domain(row) for row in self._session.scalars(query)]

    def has_overlapping(self, specialist_id: int, period: TimeRange, exclude_id: int | None = None) -> bool:
        query = select(AppointmentORM.id).where(
            AppointmentORM.specialist_id == specialist_id,
            AppointmentORM.status == AppointmentStatus.booked,
            AppointmentORM.start_at < period.end,
            AppointmentORM.end_at > period.start,
        )
        if exclude_id is not None:
            query = query.where(AppointmentORM.id != exclude_id)
        return self._session.scalar(query.limit(1)) is not None

    def has_future_active(self, specialist_id: int, now: datetime) -> bool:
        query = select(AppointmentORM.id).where(
            AppointmentORM.specialist_id == specialist_id,
            AppointmentORM.status == AppointmentStatus.booked,
            AppointmentORM.start_at > now,
        )
        return self._session.scalar(query.limit(1)) is not None

    def add(self, appointment: Appointment) -> Appointment:
        row = AppointmentORM()
        update_appointment_orm(row, appointment)
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)  # підтягнути created_at, який ставить БД
        return appointment_to_domain(row)

    def save(self, appointment: Appointment) -> Appointment:
        row = self._session.get(AppointmentORM, appointment.id)
        update_appointment_orm(row, appointment)
        self._session.flush()
        return appointment_to_domain(row)
