"""ORM-моделі (таблиці БД). Це НЕ доменні моделі: вони описують лише, як дані зберігаються."""
from datetime import datetime, time

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.entities import AppointmentStatus, Role
from app.infrastructure.db.database import Base


class ClientORM(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.client)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SpecialistORM(Base):
    __tablename__ = "specialists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    specialization: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    schedules: Mapped[list["ScheduleORM"]] = relationship(
        cascade="all, delete-orphan", order_by="ScheduleORM.weekday", lazy="selectin"
    )


class ScheduleORM(Base):
    __tablename__ = "schedules"
    __table_args__ = (UniqueConstraint("specialist_id", "weekday", name="uq_schedule_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    specialist_id: Mapped[int] = mapped_column(ForeignKey("specialists.id", ondelete="CASCADE"))
    weekday: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)


class AppointmentORM(Base):
    __tablename__ = "appointments"
    __table_args__ = (Index("ix_appointments_slot", "specialist_id", "status", "start_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"))
    specialist_id: Mapped[int] = mapped_column(ForeignKey("specialists.id", ondelete="CASCADE"))
    start_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus), default=AppointmentStatus.booked
    )
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
