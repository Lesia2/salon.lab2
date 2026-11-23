"""UC-06 – UC-10: записи до майстра."""
from datetime import date

from fastapi import APIRouter, Depends, Query, status

from app.application.services import AppointmentService
from app.domain.entities import AppointmentStatus, Client
from app.presentation.api.dependencies import get_appointment_service, get_current_user
from app.presentation.api.schemas import (
    ADMIN_ONLY,
    AUTH_REQUIRED,
    AppointmentCreateRequest,
    AppointmentResponse,
    AppointmentUpdateRequest,
    error_responses,
    to_local_naive,
)

router = APIRouter(tags=["appointments"], responses=AUTH_REQUIRED)

NOT_FOUND = error_responses(e404="Запис не знайдено (або він належить іншому клієнту)")
SLOT_ERRORS = error_responses(
    e400="Невалідні дані або час недоступний: у минулому, майстер неактивний, поза графіком",
    e404="Майстра не знайдено",
    e409="Цей час у майстра вже зайнятий",
)


@router.post(
    "/appointments",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    responses=SLOT_ERRORS,
)
def create_appointment(
    data: AppointmentCreateRequest,
    user: Client = Depends(get_current_user),
    service: AppointmentService = Depends(get_appointment_service),
):
    appointment = service.book(
        user,
        data.specialist_id,
        to_local_naive(data.start_at),
        to_local_naive(data.end_at),
        data.comment,
    )
    return AppointmentResponse.from_domain(appointment)


@router.get("/appointments", response_model=list[AppointmentResponse])
def list_appointments(
    status_filter: AppointmentStatus | None = Query(default=None, alias="status"),
    specialist_id: int | None = None,
    day: date | None = None,
    user: Client = Depends(get_current_user),
    service: AppointmentService = Depends(get_appointment_service),
):
    appointments = service.list(user, status=status_filter, specialist_id=specialist_id, day=day)
    return [AppointmentResponse.from_domain(a) for a in appointments]


@router.get("/appointments/{appointment_id}", response_model=AppointmentResponse, responses=NOT_FOUND)
def get_appointment(
    appointment_id: int,
    user: Client = Depends(get_current_user),
    service: AppointmentService = Depends(get_appointment_service),
):
    return AppointmentResponse.from_domain(service.get(user, appointment_id))


@router.patch(
    "/appointments/{appointment_id}",
    response_model=AppointmentResponse,
    responses={
        **SLOT_ERRORS,
        **NOT_FOUND,
        **error_responses(
            e409="Час зайнятий, запис не в статусі booked, або до початку менше 2 годин (для клієнта)"
        ),
    },
)
def update_appointment(
    appointment_id: int,
    data: AppointmentUpdateRequest,
    user: Client = Depends(get_current_user),
    service: AppointmentService = Depends(get_appointment_service),
):
    appointment = service.update(
        user,
        appointment_id,
        to_local_naive(data.start_at),
        to_local_naive(data.end_at),
        data.comment,
    )
    return AppointmentResponse.from_domain(appointment)


@router.post(
    "/appointments/{appointment_id}/cancel",
    response_model=AppointmentResponse,
    responses={
        **NOT_FOUND,
        **error_responses(e409="Запис не в статусі booked, або до початку менше 2 годин (для клієнта)"),
    },
)
def cancel_appointment(
    appointment_id: int,
    user: Client = Depends(get_current_user),
    service: AppointmentService = Depends(get_appointment_service),
):
    return AppointmentResponse.from_domain(service.cancel(user, appointment_id))


@router.post(
    "/appointments/{appointment_id}/complete",
    response_model=AppointmentResponse,
    responses={
        **ADMIN_ONLY,
        **NOT_FOUND,
        **error_responses(e409="Запис не в статусі booked або ще не почався"),
    },
)
def complete_appointment(
    appointment_id: int,
    user: Client = Depends(get_current_user),
    service: AppointmentService = Depends(get_appointment_service),
):
    return AppointmentResponse.from_domain(service.complete(user, appointment_id))
