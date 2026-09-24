"""Primitivas de segurança: hash de senha, tokens JWT e chaves de instrumentos."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.exceptions import AuthenticationError

# bcrypt considera apenas os primeiros 72 bytes da senha.
_BCRYPT_MAX_BYTES = 72
# Fator de custo do bcrypt. Os testes reduzem este valor para rodar rápido.
BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode()[:_BCRYPT_MAX_BYTES], bcrypt.gensalt(BCRYPT_ROUNDS)
    ).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:_BCRYPT_MAX_BYTES], password_hash.encode())
    except ValueError:
        return False


# Usado quando o usuário não existe, para que a resposta leve o mesmo tempo e não
# revele quais usernames são válidos (mitigação de enumeração por tempo).
DUMMY_PASSWORD_HASH = hash_password("labtrack-dummy-password")


@dataclass(frozen=True)
class TokenPayload:
    user_id: int
    role: str
    expires_at: datetime


def create_access_token(
    user_id: int, role: str, *, secret: str, algorithm: str, expires_minutes: int
) -> tuple[str, datetime]:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=expires_minutes)
    claims = {"sub": str(user_id), "role": role, "iat": now, "exp": expires_at, "typ": "access"}
    return jwt.encode(claims, secret, algorithm=algorithm), expires_at


def decode_access_token(token: str, *, secret: str, algorithm: str) -> TokenPayload:
    try:
        claims = jwt.decode(
            token, secret, algorithms=[algorithm], options={"require": ["sub", "exp", "iat"]}
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError(
            "Sessão expirada. Faça login novamente.", code="TOKEN_EXPIRED"
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Token de acesso inválido.", code="INVALID_TOKEN") from exc

    if claims.get("typ") != "access" or not str(claims["sub"]).isdigit():
        raise AuthenticationError("Token de acesso inválido.", code="INVALID_TOKEN")
    return TokenPayload(
        user_id=int(claims["sub"]),
        role=str(claims.get("role", "")),
        expires_at=datetime.fromtimestamp(claims["exp"], tz=UTC),
    )


# --- Chaves de API dos instrumentos -------------------------------------------

INSTRUMENT_KEY_PREFIX = "lt_inst_"
INSTRUMENT_KEY_MAX_LENGTH = 128


def generate_instrument_key() -> str:
    """Chave aleatória de 256 bits. É exibida uma única vez; o banco guarda só o hash."""
    return INSTRUMENT_KEY_PREFIX + secrets.token_urlsafe(32)


def hash_instrument_key(key: str) -> str:
    """SHA-256 da chave.

    A chave já tem alta entropia, então um hash rápido basta (diferente de senhas,
    que precisam de bcrypt). Por ser determinístico, permite localizar o
    instrumento pelo hash sem jamais armazenar a chave.
    """
    return hashlib.sha256(key.encode()).hexdigest()
