"""Criação do primeiro administrador (usada pelo CLI e pelos dados de demonstração)."""

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.domain.audit import Actor, AuditAction
from app.domain.enums import RoleCode
from app.models import User
from app.repositories.user_repository import RoleRepository, UserRepository
from app.services.audit_service import AuditService


def ensure_admin(
    session: Session, username: str, email: str, full_name: str, password: str
) -> tuple[User, bool]:
    """Retorna o administrador e se ele foi criado agora. Um usuário existente não é alterado."""
    users = UserRepository(session)
    existing = users.find_by_username(username)
    if existing is not None:
        return existing, False
    role = RoleRepository(session).find_by_code(RoleCode.ADMIN)
    if role is None:
        raise SystemExit("Perfis não encontrados. Execute 'alembic upgrade head' antes.")

    user = users.add(
        User(
            username=username,
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            role=role,
        )
    )
    AuditService(session).record(
        Actor.system("LabTrack CLI"),
        AuditAction.USER_CREATED,
        entity_type="user",
        entity_id=user.id,
        entity_label=user.username,
        new_value={"username": username, "email": email, "role": RoleCode.ADMIN},
    )
    session.commit()
    return user, True
