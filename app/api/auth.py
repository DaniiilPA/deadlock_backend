import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated
from fastapi import APIRouter, Cookie, Depends, Header, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    EmailAlreadyExistsException,
    InvalidCredentialsException,
    UnauthorizedException,
    create_access_token,
    decode_access_token,
    delete_refresh_cookie,
    generate_raw_refresh_token,
    hash_password,
    hash_token,
    set_refresh_cookie,
    verify_password,
)
from app.db.models import RefreshToken, User
from app.db.session import get_db
from app.schemas import (
    AuthResponse,
    MessageResponse,
    TokenRefreshResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Auth"])
bearer_scheme = HTTPBearer(auto_error=False)

# Вспомогательные функции и Dependency

def get_client_ip(request: Request) -> str | None:
    """Извлекает IP клиента с учетом Nginx / Reverse Proxy"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    if request.client:
        return request.client.host[:45]
    return None


async def create_user_refresh_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    user_agent: str | None,
    ip_address: str | None,
) -> str:
    """Генерирует токен, сохраняет хэш в БД и возвращает raw-токен для куки"""
    raw_token = generate_raw_refresh_token()
    token_hashed = hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=settings.REFRESH_TOKEN_EXPIRE_SECONDS
    )

    token_record = RefreshToken(
        user_id=user_id,
        token_hash=token_hashed,
        user_agent=user_agent[:512] if user_agent else None,
        ip_address=ip_address,
        expires_at=expires_at,
    )
    db.add(token_record)
    await db.commit()
    return raw_token


async def get_current_user(
    token_auth: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Dependency: Проверяет access токен и отдает живого пользователя"""
    if not token_auth:
        raise UnauthorizedException("Отсутствует токен авторизации")

    try:
        payload = decode_access_token(token_auth.credentials)
        if payload.get("type") != "access":
            raise UnauthorizedException("Неверный тип токена")
        user_id = uuid.UUID(payload.get("sub"))
    except Exception:
        raise UnauthorizedException("Токен недействителен или истек")

    # Исключаем пользователей с меткой мягкого удаления (deleted_at)
    stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedException("Пользователь не найден или деактивирован")

    return user

# Регистрация
@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: UserRegisterRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_agent: Annotated[str | None, Header()] = None,
):
    stmt = select(User).where(User.email == body.email)
    existing_user = (await db.execute(stmt)).scalar_one_or_none()
    if existing_user:
        raise EmailAlreadyExistsException()

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        first_name=body.first_name,
        last_name=body.last_name,
        roles=["user"],
    )
    db.add(user)
    await db.flush()

    raw_refresh = await create_user_refresh_token(
        db=db,
        user_id=user.id,
        user_agent=user_agent,
        ip_address=get_client_ip(request),
    )
    set_refresh_cookie(response, raw_refresh)

    access_token = create_access_token(str(user.id), user.roles)

    return AuthResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_SECONDS,
        user=UserResponse.model_validate(user),
    )


# Логин
@router.post("/login", response_model=AuthResponse)
async def login(
    body: UserLoginRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_agent: Annotated[str | None, Header()] = None,
):
    stmt = select(User).where(User.email == body.email, User.deleted_at.is_(None))
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise InvalidCredentialsException()

    raw_refresh = await create_user_refresh_token(
        db=db,
        user_id=user.id,
        user_agent=user_agent,
        ip_address=get_client_ip(request),
    )
    set_refresh_cookie(response, raw_refresh)

    access_token = create_access_token(str(user.id), user.roles)

    return AuthResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_SECONDS,
        user=UserResponse.model_validate(user),
    )


# Обновление токенов (Refresh)
@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie()] = None,
    user_agent: Annotated[str | None, Header()] = None,
):
    if not refresh_token:
        raise UnauthorizedException("Refresh токен отсутствует в cookies")

    hashed = hash_token(refresh_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == hashed)
    token_record = (await db.execute(stmt)).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if not token_record or token_record.expires_at < now:
        if token_record:
            await db.delete(token_record)
            await db.commit()
        delete_refresh_cookie(response)
        raise UnauthorizedException("Сессия истекла или недействительна")

    user_stmt = select(User).where(User.id == token_record.user_id, User.deleted_at.is_(None))
    user = (await db.execute(user_stmt)).scalar_one_or_none()
    if not user:
        await db.delete(token_record)
        await db.commit()
        delete_refresh_cookie(response)
        raise UnauthorizedException("Пользователь деактивирован")

    await db.delete(token_record)

    new_raw_token = await create_user_refresh_token(
        db=db,
        user_id=user.id,
        user_agent=user_agent,
        ip_address=get_client_ip(request),
    )
    set_refresh_cookie(response, new_raw_token)

    access_token = create_access_token(str(user.id), user.roles)

    return TokenRefreshResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_SECONDS,
    )


# Текущий профиль (Me)
@router.get("/me", response_model=UserResponse)
async def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    return UserResponse.model_validate(current_user)


# Выход (Logout)
@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie()] = None,
):
    if refresh_token:
        hashed = hash_token(refresh_token)
        await db.execute(delete(RefreshToken).where(RefreshToken.token_hash == hashed))
        await db.commit()

    delete_refresh_cookie(response)
    return MessageResponse(message="Successfully logged out")


# Выход со всех устройств (Logout-all)
@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == current_user.id))
    await db.commit()

    delete_refresh_cookie(response)
    return MessageResponse(message="All sessions revoked")