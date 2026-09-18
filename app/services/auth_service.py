import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    EmailAlreadyExistsException,
    InvalidCredentialsException,
    UnauthorizedException,
    create_access_token,
    generate_raw_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.db.models import RefreshToken, User
from app.repositories.token_repo import RefreshTokenRepository
from app.repositories.user_repo import UserRepository
from app.schemas import UserLoginRequest, UserRegisterRequest


@dataclass(slots=True, frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


@dataclass(slots=True, frozen=True)
class AuthResult:
    user: User
    tokens: TokenPair


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        user_repo: UserRepository | None = None,
        token_repo: RefreshTokenRepository | None = None,
    ) -> None:
        self._session = session
        self._user_repo = user_repo or UserRepository(session)
        self._token_repo = token_repo or RefreshTokenRepository(session)

    async def _issue_tokens(
        self,
        user: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        """Вспомогательный метод выпуска пары токенов (не коммитит сессию)"""
        raw_refresh = generate_raw_refresh_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=settings.REFRESH_TOKEN_EXPIRE_SECONDS
        )

        refresh_record = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw_refresh),
            user_agent=user_agent[:512] if user_agent else None,
            ip_address=ip_address,
            expires_at=expires_at,
        )
        self._token_repo.add(refresh_record)
        access_token = create_access_token(str(user.id), user.roles)

        return TokenPair(access_token=access_token, refresh_token=raw_refresh)

    async def register_user(
        self,
        data: UserRegisterRequest,
        ip_address: str | None,
        user_agent: str | None,
    ) -> AuthResult:
        # Проверяем занятость email (включая удаленных, если email unique в базе)
        if await self._user_repo.get_by_email(data.email, include_deleted=True):
            raise EmailAlreadyExistsException()

        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            roles=["user"],
        )
        self._user_repo.add(user)
        await self._session.flush()

        tokens = await self._issue_tokens(user, ip_address, user_agent)
        await self._session.commit()

        return AuthResult(user=user, tokens=tokens)

    async def authenticate_user(
        self,
        data: UserLoginRequest,
        ip_address: str | None,
        user_agent: str | None,
    ) -> AuthResult:
        user = await self._user_repo.get_by_email(data.email)
        if not user or not verify_password(data.password, user.password_hash):
            raise InvalidCredentialsException()

        tokens = await self._issue_tokens(user, ip_address, user_agent)
        await self._session.commit()

        return AuthResult(user=user, tokens=tokens)

    async def rotate_refresh_token(
        self,
        raw_refresh_token: str | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        if not raw_refresh_token:
            raise UnauthorizedException("Refresh токен отсутствует в cookies")

        token_hash = hash_token(raw_refresh_token)
        token_record = await self._token_repo.get_by_hash(token_hash, for_update=True)

        now = datetime.now(timezone.utc)
        if not token_record or token_record.expires_at < now:
            if token_record:
                await self._token_repo.delete(token_record)
                await self._session.commit()
            raise UnauthorizedException("Сессия истекла или недействительна")

        user = await self._user_repo.get_active_by_id(token_record.user_id)
        if not user:
            await self._token_repo.delete(token_record)
            await self._session.commit()
            raise UnauthorizedException("Пользователь деактивирован")

        # Удаляем старый токен и создаем новый
        await self._token_repo.delete(token_record)
        tokens = await self._issue_tokens(user, ip_address, user_agent)
        await self._session.commit()

        return tokens

    async def revoke_session(self, raw_refresh_token: str | None) -> None:
        if raw_refresh_token:
            token_hash = hash_token(raw_refresh_token)
            await self._token_repo.delete_by_hash(token_hash)
            await self._session.commit()

    async def revoke_all_sessions(self, user_id: uuid.UUID) -> None:
        await self._token_repo.delete_all_by_user_id(user_id)
        await self._session.commit()

    async def get_user_by_id(self, user_id: uuid.UUID) -> User:
        user = await self._user_repo.get_active_by_id(user_id)
        if not user:
            raise UnauthorizedException("Пользователь не найден или деактивирован")
        return user