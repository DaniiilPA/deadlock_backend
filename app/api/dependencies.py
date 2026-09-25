import uuid
from typing import Annotated
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import UnauthorizedException, decode_access_token
from app.db.models import User
from app.db.session import get_db
from app.repositories.project_repo import ProjectRepository
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


async def get_project_repo(
    db: Annotated[AsyncSession, Depends(get_db)]
) -> ProjectRepository:
    """Фабрика зависимостей: создает ProjectRepository с текущей сессией БД"""
    return ProjectRepository(session=db)


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


#Проверка прав доступа

def require_roles(*allowed_roles: str):
    """Проверяет глобальные роли пользователя (users.roles)"""
    async def role_checker(
        current_user: Annotated[User, Depends(get_current_user)]
    ) -> User:
        if "admin" in current_user.roles:
            return current_user

        has_permission = any(role in current_user.roles for role in allowed_roles)
        if not has_permission:
            roles_str = ", ".join(allowed_roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Недостаточно прав. Требуется глобальная роль: {roles_str}",
            )
        return current_user

    return role_checker


def require_project_access(*allowed_project_roles: str):
    """
    Проверяет доступ к объекту через ProjectRepository.
    """
    async def access_checker(
        project_id: uuid.UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        project_repo: Annotated[ProjectRepository, Depends(get_project_repo)],
    ) -> User:
        if "admin" in current_user.roles:
            return current_user

        assignment = await project_repo.get_assignment(project_id, current_user.id)

        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Вы не назначены на данный объект строительства",
            )

        if (
            allowed_project_roles
            and assignment.role_in_project not in allowed_project_roles
        ):
            roles_str = ", ".join(allowed_project_roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Недостаточно прав на объекте. Требуется роль: {roles_str}",
            )

        return current_user

    return access_checker