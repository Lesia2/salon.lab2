"""UC-01 Реєстрація, UC-02 Вхід, профіль поточного користувача."""
from fastapi import APIRouter, Depends, status

from app.application.services import AuthService
from app.domain.entities import Client
from app.presentation.api.dependencies import (
    get_auth_service,
    get_current_user,
    token_service,
)
from app.presentation.api.schemas import (
    AUTH_REQUIRED,
    ClientResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    error_responses,
)

router = APIRouter(tags=["auth"])


@router.post(
    "/auth/register",
    response_model=ClientResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(e409="Email вже зареєстрований"),
)
def register(data: RegisterRequest, auth: AuthService = Depends(get_auth_service)):
    client = auth.register(data.name, data.email, data.phone, data.password)
    return ClientResponse.from_domain(client)


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    responses=error_responses(e401="Невірний email або пароль"),
)
def login(data: LoginRequest, auth: AuthService = Depends(get_auth_service)):
    client = auth.authenticate(data.email, data.password)
    return TokenResponse(access_token=token_service.create(client.id))


@router.get("/clients/me", response_model=ClientResponse, responses=AUTH_REQUIRED)
def me(current_user: Client = Depends(get_current_user)):
    return ClientResponse.from_domain(current_user)
