from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.domain.audit import Actor, AuditAction
from app.domain.pagination import PageRequest, PageResult
from app.models import Role, User
from app.repositories.user_repository import RoleRepository, UserRepository
from app.schemas.users import UserCreate, UserFilter, UserUpdate
from app.services.audit_service import AuditService, diff

PASSWORD_MASK = "********"


def _snapshot(user: User) -> dict[str, Any]:
    """Estado auditável do usuário. O hash da senha nunca vai para o audit trail."""
    return {
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.code,
        "is_active": user.is_active,
    }


class UserService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.roles = RoleRepository(session)
        self.audit = AuditService(session)

    def search(self, filters: UserFilter, page: PageRequest) -> PageResult[User]:
        return self.users.search(filters, page)

    def get(self, user_id: int) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError(f"Usuário {user_id} não encontrado.", code="USER_NOT_FOUND")
        return user

    def list_roles(self) -> list[Role]:
        return self.roles.list_all()

    def create(self, data: UserCreate, actor: User) -> User:
        if self.users.find_by_username(data.username):
            raise ConflictError(
                f"O usuário '{data.username}' já existe.", code="USERNAME_ALREADY_EXISTS"
            )
        if self.users.exists_with_email(data.email):
            raise ConflictError(
                f"O e-mail '{data.email}' já está em uso.", code="EMAIL_ALREADY_EXISTS"
            )

        user = self.users.add(
            User(
                username=data.username,
                email=data.email.lower(),
                full_name=data.full_name,
                password_hash=hash_password(data.password),
                role=self._role(data.role),
            )
        )
        self.audit.record(
            Actor.user(actor.id, actor.full_name),
            AuditAction.USER_CREATED,
            entity_type="user",
            entity_id=user.id,
            entity_label=user.username,
            new_value=_snapshot(user),
        )
        self.session.commit()
        return user

    def update(self, user_id: int, data: UserUpdate, actor: User) -> User:
        user = self.get(user_id)
        changes = data.model_dump(exclude_unset=True, exclude_none=True)

        if user.id == actor.id and (
            changes.get("is_active") is False
            or changes.get("role", user.role.code) != user.role.code
        ):
            raise ConflictError(
                "Você não pode desativar nem alterar o perfil do próprio usuário.",
                code="SELF_MODIFICATION_NOT_ALLOWED",
            )
        if "email" in changes and self.users.exists_with_email(
            changes["email"], exclude_id=user.id
        ):
            raise ConflictError(
                f"O e-mail '{changes['email']}' já está em uso.", code="EMAIL_ALREADY_EXISTS"
            )

        before = _snapshot(user)
        if "email" in changes:
            user.email = changes["email"].lower()
        if "full_name" in changes:
            user.full_name = changes["full_name"]
        if "is_active" in changes:
            user.is_active = changes["is_active"]
        if "role" in changes:
            user.role = self._role(changes["role"])
        old_value, new_value = diff(before, _snapshot(user))

        if "password" in changes:
            user.password_hash = hash_password(changes["password"])
            old_value["password"] = PASSWORD_MASK
            new_value["password"] = "redefinida"

        if new_value:
            self.session.flush()
            self.audit.record(
                Actor.user(actor.id, actor.full_name),
                AuditAction.USER_UPDATED,
                entity_type="user",
                entity_id=user.id,
                entity_label=user.username,
                old_value=old_value,
                new_value=new_value,
            )
        self.session.commit()
        return user

    def _role(self, code: str) -> Role:
        role = self.roles.find_by_code(code)
        if role is None:  # perfis são criados pela migração; ausência indica banco inconsistente
            raise NotFoundError(f"Perfil {code} não encontrado.", code="ROLE_NOT_FOUND")
        return role
