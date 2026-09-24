import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AuthenticationError
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    decode_access_token,
    verify_password,
)
from app.domain.audit import Actor, AuditAction
from app.models import User
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

INVALID_CREDENTIALS = "Usuário ou senha inválidos."


@dataclass(frozen=True)
class LoginResult:
    user: User
    access_token: str
    expires_at: datetime


class AuthService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)
        self.audit = AuditService(session)

    def login(self, username: str, password: str, *, ip_address: str | None = None) -> LoginResult:
        user = self.users.find_by_username(username.strip())
        # Sempre executa a verificação de senha, mesmo sem usuário (tempo constante).
        password_ok = verify_password(password, user.password_hash if user else DUMMY_PASSWORD_HASH)

        if user is None or not password_ok or not user.is_active:
            reason = (
                "usuário inexistente"
                if user is None
                else ("usuário inativo" if password_ok else "senha incorreta")
            )
            self._record_failure(username, user, reason, ip_address)
            raise AuthenticationError(INVALID_CREDENTIALS, code="INVALID_CREDENTIALS")

        user.last_login_at = datetime.now(UTC)
        token, expires_at = create_access_token(
            user.id,
            user.role.code,
            secret=self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm,
            expires_minutes=self.settings.access_token_expire_minutes,
        )
        self.audit.record(
            Actor.user(user.id, user.full_name),
            AuditAction.LOGIN_SUCCEEDED,
            entity_type="user",
            entity_id=user.id,
            entity_label=user.username,
            ip_address=ip_address,
        )
        self.session.commit()
        return LoginResult(user=user, access_token=token, expires_at=expires_at)

    def authenticate(self, token: str) -> User:
        """Valida o token e confirma no banco que o usuário continua ativo.

        Desativar um usuário revoga o acesso imediatamente, sem esperar o token expirar.
        """
        payload = decode_access_token(
            token, secret=self.settings.jwt_secret_key, algorithm=self.settings.jwt_algorithm
        )
        user = self.users.get(payload.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Usuário inativo ou inexistente.", code="INVALID_TOKEN")
        return user

    def _record_failure(
        self, username: str, user: User | None, reason: str, ip_address: str | None
    ) -> None:
        logger.warning("Falha de login para '%s': %s", username, reason)
        actor = (
            Actor.user(user.id, user.full_name)
            if user
            else Actor.system(f"anônimo ({username[:50]})")
        )
        self.audit.record(
            actor,
            AuditAction.LOGIN_FAILED,
            entity_type="user",
            entity_id=user.id if user else "-",
            entity_label=username[:120],
            reason=reason,
            ip_address=ip_address,
        )
        self.session.commit()
