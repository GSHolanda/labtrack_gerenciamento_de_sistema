"""Parâmetros e respostas reutilizados pelas rotas."""

from typing import Annotated, Any

from fastapi import Depends, Query

from app.api.deps import require_permission
from app.domain.pagination import MAX_PAGE_SIZE, PageRequest
from app.domain.permissions import Permission
from app.models import User
from app.schemas.common import ErrorResponse


def page_request(
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
    sort: Annotated[
        str | None, Query(max_length=40, description="Campo; prefixo '-' para decrescente")
    ] = None,
) -> PageRequest:
    return PageRequest(page=page, size=size, sort=sort)


Paging = Annotated[PageRequest, Depends(page_request)]


def requires(permission: Permission) -> Any:
    """Atalho: ``actor: requires(Permission.X)`` injeta o usuário já autorizado."""
    return Annotated[User, Depends(require_permission(permission))]


def errors(*codes: int) -> dict[int | str, dict[str, Any]]:
    descriptions = {
        401: "Não autenticado",
        403: "Sem permissão",
        404: "Não encontrado",
        409: "Conflito com o estado atual",
        422: "Dados inválidos ou regra de negócio violada",
    }
    return {code: {"model": ErrorResponse, "description": descriptions[code]} for code in codes}
