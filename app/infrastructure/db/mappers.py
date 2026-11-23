"""Мапери: ORM-модель ↔ доменна модель. Живуть в Infrastructure, домен про них не знає."""
from app.domain.entities import Appointment, Client, Specialist, WorkingDay
from app.domain.value_objects import Email, Phone, TimeRange, WorkingHours
from app.infrastructure.db.orm_models import (
    AppointmentORM,
    ClientORM,
    ScheduleORM,
    SpecialistORM,
)

# ---------- Client ----------

def client_to_domain(row: ClientORM) -> Client:
    return Client(
        id=row.id,
        name=row.name,
        email=Email(row.email),
        phone=Phone(row.phone),
        password_hash=row.password_hash,
        role=row.role,
        created_at=row.created_at,
    )


def client_to_orm(client: Client) -> ClientORM:
    return ClientORM(
        id=client.id,
        name=client.name,
        email=client.email.value,
        phone=client.phone.value,
        password_hash=client.password_hash,
        role=client.role,
    )


# ---------- Specialist + графік ----------

def specialist_to_domain(row: SpecialistORM) -> Specialist:
    return Specialist(
        id=row.id,
        name=row.name,
        specialization=row.specialization,
        is_active=row.is_active,
        working_days=[
            WorkingDay(id=s.id, weekday=s.weekday, hours=WorkingHours(s.start_time, s.end_time))
            for s in row.schedules
        ],
    )


def update_specialist_orm(row: SpecialistORM, specialist: Specialist) -> None:
    """Переносить стан агрегату в ORM: оновлює, додає й видаляє робочі дні."""
    row.name = specialist.name
    row.specialization = specialist.specialization
    row.is_active = specialist.is_active

    existing = {s.id: s for s in row.schedules}
    keep_ids = {d.id for d in specialist.working_days if d.id is not None}
    for schedule in list(row.schedules):
        if schedule.id not in keep_ids:
            row.schedules.remove(schedule)

    for day in specialist.working_days:
        if day.id is not None and day.id in existing:
            schedule = existing[day.id]
            schedule.weekday = day.weekday
            schedule.start_time = day.hours.start
            schedule.end_time = day.hours.end
        elif day.id is None:
            row.schedules.append(
                ScheduleORM(weekday=day.weekday, start_time=day.hours.start, end_time=day.hours.end)
            )


# ---------- Appointment ----------

def appointment_to_domain(row: AppointmentORM) -> Appointment:
    return Appointment(
        id=row.id,
        client_id=row.client_id,
        specialist_id=row.specialist_id,
        time=TimeRange(row.start_at, row.end_at),
        status=row.status,
        comment=row.comment,
        created_at=row.created_at,
    )


def update_appointment_orm(row: AppointmentORM, appointment: Appointment) -> None:
    row.client_id = appointment.client_id
    row.specialist_id = appointment.specialist_id
    row.start_at = appointment.time.start
    row.end_at = appointment.time.end
    row.status = appointment.status
    row.comment = appointment.comment
