"""
Тесты компонента авторизации.

Покрывает: hash_password, verify_password, create_access_token, decode_access_token.
Запуск: python3 -m pytest tests/test_auth.py -v
"""
import pytest
from fastapi import HTTPException

from src.auth.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


# ── hash_password ─────────────────────────────────────────────────────────────

def test_hash_password_not_equal_to_plain():
    """Хэш не совпадает с исходным паролем."""
    hashed = hash_password("secret123")
    assert hashed != "secret123"


def test_hash_password_different_hashes_for_same_password():
    """Два вызова с одним паролем дают разные хэши (соль)."""
    hash1 = hash_password("secret123")
    hash2 = hash_password("secret123")
    assert hash1 != hash2


# ── verify_password ───────────────────────────────────────────────────────────

def test_verify_password_correct():
    """Правильный пароль принимается."""
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed) is True


def test_verify_password_wrong():
    """Неправильный пароль отклоняется."""
    hashed = hash_password("mypassword")
    assert verify_password("wrongpassword", hashed) is False


def test_verify_password_empty():
    """Пустой пароль не принимается."""
    hashed = hash_password("mypassword")
    assert verify_password("", hashed) is False


# ── create_access_token ───────────────────────────────────────────────────────

def test_create_access_token_returns_string():
    """Токен создаётся и является строкой."""
    token = create_access_token(user_id=42)
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_and_decode_token_same_user_id():
    """encode → decode возвращает тот же user_id."""
    user_id = 99
    token = create_access_token(user_id=user_id)
    decoded_id = decode_access_token(token)
    assert decoded_id == user_id


# ── decode_access_token ───────────────────────────────────────────────────────

def test_decode_access_token_correct_user_id():
    """Из токена достаётся правильный user_id."""
    token = create_access_token(user_id=7)
    assert decode_access_token(token) == 7


def test_decode_access_token_invalid_token_raises():
    """Невалидный токен → HTTPException 401."""
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token("this.is.not.a.valid.token")
    assert exc_info.value.status_code == 401


def test_decode_access_token_no_sub_raises():
    """Токен без поля sub → HTTPException 401."""
    from jose import jwt
    from config.config import JWT_SECRET, JWT_ALGORITHM
    from datetime import datetime, timedelta, timezone

    payload = {"exp": datetime.now(timezone.utc) + timedelta(days=1)}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)
    assert exc_info.value.status_code == 401
