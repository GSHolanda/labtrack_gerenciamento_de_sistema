from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, CreatedAtMixin, IdMixin, TimestampMixin, enum_check
from app.domain.enums import RoleCode


class Role(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (enum_check("code", RoleCode),)

    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)

    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(IdMixin, TimestampMixin, Base):
    """Usuário do sistema. Nunca é excluído, apenas desativado (RN-25)."""

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    full_name: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), index=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    last_login_at: Mapped[datetime | None]

    role: Mapped[Role] = relationship(back_populates="users", lazy="joined")
