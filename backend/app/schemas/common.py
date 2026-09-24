"""Contratos comuns a toda a API: envelope de erro e paginação."""

from math import ceil
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


class UserReference(BaseModel):
    id: int
    full_name: str


class ErrorBody(BaseModel):
    code: str = Field(examples=["SAMPLE_NOT_FOUND"])
    message: str = Field(examples=["Amostra SMP-2026-0099 não encontrada."])
    details: Any | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int

    @classmethod
    def build(cls, items: list[T], total: int, page: int, size: int) -> "Page[T]":
        return cls(items=items, total=total, page=page, size=size, pages=ceil(total / size))
