from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field, StringConstraints

from app.domain.enums import RoleCode
from app.domain.permissions import Permission, permissions_for

Username = Annotated[
    str,
    # Normaliza antes de validar: "Carlos.Silva" e "carlos.silva" são o mesmo login.
    BeforeValidator(lambda value: value.strip().lower() if isinstance(value, str) else value),
    StringConstraints(pattern=r"^[a-z0-9._-]{3,50}$"),
]
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=150)]
Password = Annotated[str, Field(min_length=8, max_length=128)]


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: Username = Field(examples=["carlos.silva"])
    email: EmailStr
    full_name: FullName = Field(examples=["Carlos Silva"])
    password: Password
    role: RoleCode


class UserUpdate(BaseModel):
    """Campos omitidos não são alterados. Usuários são desativados, nunca excluídos."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr | None = None
    full_name: FullName | None = None
    role: RoleCode | None = None
    is_active: bool | None = None
    password: Password | None = Field(default=None, description="Redefine a senha do usuário")


class UserRead(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role: RoleCode
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime

    @classmethod
    def from_user(cls, user: Any) -> Self:
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role.code,
            is_active=user.is_active,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
        )


class CurrentUser(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role: RoleCode
    permissions: list[Permission]

    @classmethod
    def from_user(cls, user: Any) -> Self:
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role.code,
            permissions=sorted(permissions_for(user.role.code)),
        )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: CurrentUser


class RoleRead(BaseModel):
    code: RoleCode
    name: str
    description: str | None
    permissions: list[Permission]

    @classmethod
    def from_role(cls, role: Any) -> Self:
        return cls(
            code=role.code,
            name=role.name,
            description=role.description,
            permissions=sorted(permissions_for(role.code)),
        )


@dataclass(frozen=True)
class UserFilter:
    role: str | None = None
    is_active: bool | None = None
    q: str | None = None
