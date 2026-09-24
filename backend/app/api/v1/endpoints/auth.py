from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import AppSettings, CurrentUserDep, DbSession, client_ip
from app.schemas.common import ErrorResponse
from app.schemas.users import CurrentUser, TokenResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth")


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse, "description": "Credenciais inválidas"}},
    summary="Autentica o usuário e emite um token JWT",
    description="Formulário OAuth2 (`username`, `password`). Sucessos e falhas são auditados.",
)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    session: DbSession,
    settings: AppSettings,
) -> TokenResponse:
    result = AuthService(session, settings).login(
        form.username, form.password, ip_address=client_ip(request)
    )
    return TokenResponse(
        access_token=result.access_token,
        expires_at=result.expires_at,
        user=CurrentUser.from_user(result.user),
    )


@router.get("/me", response_model=CurrentUser, summary="Usuário autenticado e suas permissões")
def me(user: CurrentUserDep) -> CurrentUser:
    return CurrentUser.from_user(user)
