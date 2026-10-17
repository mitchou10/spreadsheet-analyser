import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Base


class BaseRepository[ModelT: Base]:
    """Data access only: flushes but never commits - the service owns the transaction."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id: uuid.UUID) -> ModelT | None:
        return await self.session.get(self.model, id)

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        # Loads server-side defaults (created_at...) now: async sessions can't lazy-load them later.
        await self.session.refresh(entity)
        return entity

    async def delete(self, entity: ModelT) -> None:
        await self.session.delete(entity)
        await self.session.flush()

    async def _all(self, statement) -> list[ModelT]:
        return list((await self.session.scalars(statement)).all())

    async def _first(self, statement) -> ModelT | None:
        return await self.session.scalar(statement)

    def _select(self):
        return select(self.model)
