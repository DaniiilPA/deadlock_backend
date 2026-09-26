import uuid
from typing import Annotated
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import UnauthorizedException, decode_access_token
from app.db.models import SpecialStatusWindow, User
from app.db.session import get_db
from app.repositories.project_repo import ProjectRepository
from app.services.auth_service import AuthService

bearer_scheme = HTTPBearer(auto_error=False)


def get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    if request.client:
        return request.client.host[:45]
    return None


async def get_auth_service(
    db: Annotated[AsyncSession, Depends(get_db)]
) -> AuthService:
    return AuthService(session=db)


async def get_project_repo(
    db: Annotated[AsyncSession, Depends(get_db)]
) -> ProjectRepository:
    return ProjectRepository(session=db)


async def get_current_user(
    token_auth: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
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


def require_roles(*allowed_roles: str):
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
    async def access_checker(
        project_id: uuid.UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        project_repo: Annotated[ProjectRepository, Depends(get_project_repo)],
    ) -> User:
        if "admin" in current_user.roles:
            return current_user

        project = await project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Объект строительства не найден",
            )

        if project.creator_id == current_user.id:
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


def require_window_access(*allowed_project_roles: str):
    async def window_checker(
        window_id: uuid.UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> User:
        if "admin" in current_user.roles:
            return current_user

        window = await db.get(SpecialStatusWindow, window_id)
        if not window:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Окно специального статуса не найдено",
            )

        project_repo = ProjectRepository(db)
        project = await project_repo.get_by_id(window.project_id)
        if project and project.creator_id == current_user.id:
            return current_user

        assignment = await project_repo.get_assignment(window.project_id, current_user.id)
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

    return window_checker