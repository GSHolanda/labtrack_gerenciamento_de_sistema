from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

SECRET = "s" * 40


def test_password_is_hashed_and_verified() -> None:
    password_hash = hash_password("Senha@2026")

    assert password_hash != "Senha@2026"
    assert verify_password("Senha@2026", password_hash)
    assert not verify_password("senha@2026", password_hash)


def test_same_password_produces_different_hashes() -> None:
    assert hash_password("Senha@2026") != hash_password("Senha@2026")


def test_verify_against_malformed_hash_returns_false() -> None:
    assert not verify_password("x", "not-a-bcrypt-hash")


def test_token_roundtrip() -> None:
    token, expires_at = create_access_token(
        42, "ANALYST", secret=SECRET, algorithm="HS256", expires_minutes=30
    )

    payload = decode_access_token(token, secret=SECRET, algorithm="HS256")
    assert payload.user_id == 42
    assert payload.role == "ANALYST"
    assert abs((payload.expires_at - expires_at).total_seconds()) < 1


def test_expired_token_is_rejected() -> None:
    past = datetime.now(UTC) - timedelta(hours=2)
    token = jwt.encode(
        {"sub": "1", "iat": past, "exp": past + timedelta(minutes=5), "typ": "access"},
        SECRET,
        algorithm="HS256",
    )

    with pytest.raises(AuthenticationError) as error:
        decode_access_token(token, secret=SECRET, algorithm="HS256")
    assert error.value.code == "TOKEN_EXPIRED"


@pytest.mark.parametrize(
    "token",
    [
        jwt.encode({"sub": "1", "iat": 1, "exp": 9_999_999_999, "typ": "access"}, "outra" * 10),
        jwt.encode({"sub": "1", "iat": 1, "exp": 9_999_999_999, "typ": "refresh"}, SECRET),
        jwt.encode({"sub": "abc", "iat": 1, "exp": 9_999_999_999, "typ": "access"}, SECRET),
        "isto-nao-e-um-jwt",
    ],
    ids=["assinatura-invalida", "tipo-errado", "sub-invalido", "malformado"],
)
def test_invalid_tokens_are_rejected(token: str) -> None:
    with pytest.raises(AuthenticationError) as error:
        decode_access_token(token, secret=SECRET, algorithm="HS256")
    assert error.value.code == "INVALID_TOKEN"


def test_algorithm_none_is_rejected() -> None:
    token = jwt.encode({"sub": "1", "iat": 1, "exp": 9_999_999_999, "typ": "access"}, None, "none")

    with pytest.raises(AuthenticationError):
        decode_access_token(token, secret=SECRET, algorithm="HS256")
