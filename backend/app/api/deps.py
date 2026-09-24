"""Dependências compartilhadas pelas rotas."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.domain.permissions import Permission, has_permission
from app.models import User
from app.services.auth_service import AuthService


def get_db(request: Request) -> Iterator[Session]:
    """Uma sessão por requisição.

    O commit é responsabilidade do serviço (fim do caso de uso). Aqui garantimos
    apenas que nada fique pendente: em caso de erro, desfaz; no fim, fecha.
    """
    session: Session = request.app.state.session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


DbSession = Annotated[Session, Depends(get_db)]


# --- Autenticação e autorização -------------------------------------------------


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

AppSettings = Annotated[Settings, Depends(get_settings)]


def get_current_user(
    session: DbSession,
    settings: AppSettings,
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> User:
    if not token:
        raise AuthenticationError("Autenticação necessária.")
    return AuthService(session, settings).authenticate(token)


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_permission(permission: Permission):  # type: ignore[no-untyped-def]
    """Dependência de rota: exige que o usuário autenticado tenha a permissão."""

    def dependency(user: CurrentUserDep) -> User:
        if not has_permission(user.role.code, permission):
            raise PermissionDeniedError(
                "Seu perfil não tem permissão para esta operação.",
                details={"required_permission": permission, "role": user.role.code},
            )
        return user

    return dependency


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
