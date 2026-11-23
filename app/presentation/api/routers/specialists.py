"""UC-03 Перегляд майстрів, UC-04 Керування майстрами, UC-05 Графік.

Контролери лише перетворюють HTTP-запит у виклик use case і результат — у відповідь.
"""
from fastapi import APIRouter, Depends, Response, status

from app.application.services import SpecialistService
from app.domain.entities import Client
from app.presentation.api.dependencies import get_current_user, get_specialist_service
from app.presentation.api.schemas import (
    ADMIN_ONLY,
    AUTH_REQUIRED,
    ScheduleRequest,
    ScheduleResponse,
    SpecialistDetailResponse,
    SpecialistRequest,
    SpecialistResponse,
    error_responses,
)

router = APIRouter(responses=AUTH_REQUIRED)

NOT_FOUND_SPECIALIST = error_responses(e404="Майстра не знайдено")
NOT_FOUND_SCHEDULE = error_responses(e404="Запис графіка не знайдено")
DAY_TAKEN = error_responses(e409="На цей день графік уже існує")


# ---------- UC-03: перегляд ----------

@router.get("/specialists", tags=["specialists"], response_model=list[SpecialistResponse])
def list_specialists(
    specialization: str | None = None,
    user: Client = Depends(get_current_user),
    service: SpecialistService = Depends(get_specialist_service),
):
    return [SpecialistResponse.from_domain(s) for s in service.list(user, specialization)]


@router.get(
    "/specialists/{specialist_id}",
    tags=["specialists"],
    response_model=SpecialistDetailResponse,
    responses=NOT_FOUND_SPECIALIST,
)
def get_specialist(
    specialist_id: int,
    user: Client = Depends(get_current_user),
    service: SpecialistService = Depends(get_specialist_service),
):
    return SpecialistDetailResponse.from_domain(service.get(user, specialist_id))


# ---------- UC-04: керування майстрами ----------

@router.post(
    "/specialists",
    tags=["specialists"],
    response_model=SpecialistResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ADMIN_ONLY,
)
def create_specialist(
    data: SpecialistRequest,
    user: Client = Depends(get_current_user),
    service: SpecialistService = Depends(get_specialist_service),
):
    return SpecialistResponse.from_domain(service.create(user, data.name, data.specialization))


@router.put(
    "/specialists/{specialist_id}",
    tags=["specialists"],
    response_model=SpecialistResponse,
    responses={**ADMIN_ONLY, **NOT_FOUND_SPECIALIST},
)
def update_specialist(
    specialist_id: int,
    data: SpecialistRequest,
    user: Client = Depends(get_current_user),
    service: SpecialistService = Depends(get_specialist_service),
):
    specialist = service.update(user, specialist_id, data.name, data.specialization)
    return SpecialistResponse.from_domain(specialist)


@router.patch(
    "/specialists/{specialist_id}/deactivate",
    tags=["specialists"],
    response_model=SpecialistResponse,
    responses={**ADMIN_ONLY, **NOT_FOUND_SPECIALIST},
)
def deactivate_specialist(
    specialist_id: int,
    user: Client = Depends(get_current_user),
    service: SpecialistService = Depends(get_specialist_service),
):
    return SpecialistResponse.from_domain(service.deactivate(user, specialist_id))


@router.delete(
    "/specialists/{specialist_id}",
    tags=["specialists"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        **ADMIN_ONLY,
        **NOT_FOUND_SPECIALIST,
        **error_responses(e409="У майстра є майбутні активні записи"),
    },
)
def delete_specialist(
    specialist_id: int,
    user: Client = Depends(get_current_user),
    service: SpecialistService = Depends(get_specialist_service),
):
    service.delete(user, specialist_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- UC-05: графік ----------

@router.post(
    "/specialists/{specialist_id}/schedule",
    tags=["schedules"],
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    responses={**ADMIN_ONLY, **NOT_FOUND_SPECIALIST, **DAY_TAKEN},
)
def create_schedule(
    specialist_id: int,
    data: ScheduleRequest,
    user: Client = Depends(get_current_user),
    service: SpecialistService = Depends(get_specialist_service),
):
    day = service.add_working_day(user, specialist_id, data.weekday, data.start_time, data.end_time)
    return ScheduleResponse.from_domain(day, specialist_id)


@router.put(
    "/schedules/{schedule_id}",
    tags=["schedules"],
    response_model=ScheduleResponse,
    responses={**ADMIN_ONLY, **NOT_FOUND_SCHEDULE, **DAY_TAKEN},
)
def update_schedule(
    schedule_id: int,
    data: ScheduleRequest,
    user: Client = Depends(get_current_user),
    service: SpecialistService = Depends(get_specialist_service),
):
    specialist_id, day = service.change_working_day(
        user, schedule_id, data.weekday, data.start_time, data.end_time
    )
    return ScheduleResponse.from_domain(day, specialist_id)


@router.delete(
    "/schedules/{schedule_id}",
    tags=["schedules"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**ADMIN_ONLY, **NOT_FOUND_SCHEDULE},
)
def delete_schedule(
    schedule_id: int,
    user: Client = Depends(get_current_user),
    service: SpecialistService = Depends(get_specialist_service),
):
    service.remove_working_day(user, schedule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
