"""Repositório base: operações comuns, paginação e ordenação seguras."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.database.base import Base

MAX_PAGE_SIZE = 100

T = TypeVar("T")
ModelT = TypeVar("ModelT", bound=Base)


@dataclass(frozen=True)
class PageRequest:
    page: int = 1
    size: int = 20
    sort: str | None = None  # "campo" (asc) ou "-campo" (desc)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


@dataclass(frozen=True)
class PageResult(Generic[T]):
    items: Sequence[T]
    total: int
    page: int
    size: int


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]
    # Campos ordenáveis expostos na API → colunas. Ordenação fora da lista é recusada,
    # impedindo que o cliente ordene por colunas internas ou inexistentes.
    sortable: Mapping[str, ColumnElement] = {}
    default_sort: Sequence[ColumnElement] = ()

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, entity_id: int) -> ModelT | None:
        return self.session.get(self.model, entity_id)

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        self.session.flush()
        return entity

    def paginate(self, statement: Select, request: PageRequest) -> PageResult:
        total = self.session.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        )
        ordered = statement.order_by(*self._order_by(request.sort))
        items = self.session.scalars(ordered.offset(request.offset).limit(request.size)).unique()
        return PageResult(items=items.all(), total=total or 0, page=request.page, size=request.size)

    def _order_by(self, sort: str | None) -> list[ColumnElement]:
        if not sort:
            return [*self.default_sort, self.model.id]  # type: ignore[attr-defined]
        field = sort.removeprefix("-")
        column = self.sortable.get(field)
        if column is None:
            raise BusinessRuleError(
                f"Ordenação por '{field}' não é permitida.",
                code="INVALID_SORT_FIELD",
                details={"allowed": sorted(self.sortable)},
            )
        return [column.desc() if sort.startswith("-") else column.asc(), self.model.id]  # type: ignore[attr-defined]
