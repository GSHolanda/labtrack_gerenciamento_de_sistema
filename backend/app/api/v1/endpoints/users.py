from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUserDep, DbSession, require_permission
from app.domain.enums import RoleCode
from app.domain.pagination import MAX_PAGE_SIZE, PageRequest
from app.domain.permissions import Permission
from app.models import User
from app.schemas.common import ErrorResponse, Page
from app.schemas.users import RoleRead, UserCreate, UserFilter, UserRead, UserUpdate
from app.services.user_service import UserService

router = APIRouter()

UserManager = Annotated[User, Depends(require_permission(Permission.USER_MANAGE))]
ERRORS = {
    401: {"model": ErrorResponse, "description": "Não autenticado"},
    403: {"model": ErrorResponse, "description": "Sem permissão"},
}


@router.get("/users", response_model=Page[UserRead], responses=ERRORS, summary="Lista usuários")
def list_users(
    session: DbSession,
    _: UserManager,
    role: RoleCode | None = None,
    is_active: bool | None = None,
    q: Annotated[
        str | None, Query(max_length=100, description="Busca em nome, login e e-mail")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
    sort: Annotated[str | None, Query(examples=["full_name", "-last_login_at"])] = None,
) -> Page[UserRead]:
    result = UserService(session).search(
        UserFilter(role=role, is_active=is_active, q=q), PageRequest(page, size, sort)
    )
    return Page.build([UserRead.from_user(u) for u in result.items], result.total, page, size)


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    responses={**ERRORS, 409: {"model": ErrorResponse, "description": "Login ou e-mail já existe"}},
    summary="Cria usuário",
)
def create_user(data: UserCreate, session: DbSession, actor: UserManager) -> UserRead:
    return UserRead.from_user(UserService(session).create(data, actor))


@router.get(
    "/users/{user_id}",
    response_model=UserRead,
    responses={**ERRORS, 404: {"model": ErrorResponse}},
    summary="Detalhe do usuário",
)
def get_user(user_id: int, session: DbSession, _: UserManager) -> UserRead:
    return UserRead.from_user(UserService(session).get(user_id))


@router.patch(
    "/users/{user_id}",
    response_model=UserRead,
    responses={**ERRORS, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    summary="Altera, redefine senha ou desativa usuário",
    description="Usuários nunca são excluídos: use `is_active=false` para desativar.",
)
def update_user(user_id: int, data: UserUpdate, session: DbSession, actor: UserManager) -> UserRead:
    return UserRead.from_user(UserService(session).update(user_id, data, actor))


@router.get("/roles", response_model=list[RoleRead], summary="Perfis e suas permissões")
def list_roles(session: DbSession, _: CurrentUserDep) -> list[RoleRead]:
    return [RoleRead.from_role(role) for role in UserService(session).list_roles()]
