import uuid
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_hash(self, token_hash: str, for_update: bool = False) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        if for_update:

            stmt = stmt.with_for_update()
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    def add(self, token: RefreshToken) -> None:
        self._session.add(token)

    async def delete(self, token: RefreshToken) -> None:
        await self._session.delete(token)

    async def delete_by_hash(self, token_hash: str) -> None:
        stmt = delete(RefreshToken).where(RefreshToken.token_hash == token_hash)
        await self._session.execute(stmt)

    async def delete_all_by_user_id(self, user_id: uuid.UUID) -> None:
        stmt = delete(RefreshToken).where(RefreshToken.user_id == user_id)
        await self._session.execute(stmt)