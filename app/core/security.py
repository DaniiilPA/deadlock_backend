import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
import bcrypt
import jwt
from fastapi import Response

from app.core.config import settings


# Исключения под единый формат ошибок
class AppException(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[dict[str, Any]] | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


class EmailAlreadyExistsException(AppException):
    def __init__(self):
        super().__init__(
            status_code=409,
            code="EMAIL_ALREADY_EXISTS",
            message="Пользователь с таким email уже зарегистрирован",
            details=None,
        )


class InvalidCredentialsException(AppException):
    def __init__(self):
        super().__init__(
            status_code=401,
            code="INVALID_CREDENTIALS",
            message="Неверный email или пароль",
            details=None,
        )


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Требуется авторизация"):
        super().__init__(
            status_code=401,
            code="UNAUTHORIZED",
            message=message,
            details=None,
        )


# Хэширование паролей
def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


# JWT Access Token
def create_access_token(user_id: str, roles: list[str]) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(seconds=settings.ACCESS_TOKEN_EXPIRE_SECONDS)
    payload = {
        "sub": str(user_id),
        "roles": roles,
        "exp": expire,
        "iat": now,
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# Refresh Token & Sessions
def generate_raw_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_token(raw_token: str) -> str:
    """Хэшируем токен перед сохранением в базу (SHA-256)"""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


# Cookies 
def set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path=settings.COOKIE_PATH,
        max_age=settings.REFRESH_TOKEN_EXPIRE_SECONDS,
    )


def delete_refresh_cookie(response: Response) -> None:
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value="",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path=settings.COOKIE_PATH,
        max_age=0,
    )