import uuid
from typing import Annotated
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import UnauthorizedException, decode_access_token
from app.db.models import User
from app.db.session import get_db
from app.services.auth_service import AuthService

bearer_scheme = HTTPBearer(auto_error=False)


def get_client_ip(request: Request) -> str | None:
    """Извлекает IP-адрес клиента с учетом прокси"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    if request.client:
        return request.client.host[:45]
    return None


async def get_auth_service(
    db: Annotated[AsyncSession, Depends(get_db)]
) -> AuthService:
    """Фабрика зависимостей: создает AuthService с текущей сессией БД"""
    return AuthService(session=db)


async def get_current_user(
    token_auth: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    """Защищает роуты: валидирует JWT и возвращает пользователя из БД"""
    if not token_auth:
        raise UnauthorizedException("Отсутствует токен авторизации")

    try:
        payload = decode_access_token(token_auth.credentials)
        if payload.get("type") != "access":
            raise UnauthorizedException("Неверный тип токена")
        user_id = uuid.UUID(payload.get("sub"))
    except Exception:
        raise UnauthorizedException("Токен недействителен или истек")

    return await auth_service.get_user_by_id(user_id)