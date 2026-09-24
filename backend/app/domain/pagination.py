"""Tipos de paginação compartilhados entre API, serviços e repositórios."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

MAX_PAGE_SIZE = 100

T = TypeVar("T")


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
