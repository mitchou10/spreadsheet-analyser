import uuid
from datetime import datetime

from sqlalchemy import Row, delete, func, select

from app.models import TokenUsage
from app.repositories.base import BaseRepository


class TokenUsageRepository(BaseRepository[TokenUsage]):
    model = TokenUsage

    async def delete_for_run(self, run_id: uuid.UUID) -> None:
        await self.session.execute(delete(TokenUsage).where(TokenUsage.run_id == run_id))

    def _sums(self):
        return (
            func.coalesce(func.sum(TokenUsage.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(TokenUsage.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).label("total_tokens"),
            func.count().label("calls"),
        )

    def _scope(self, statement, since: datetime, user_id: str | None):
        statement = statement.where(TokenUsage.created_at >= since)
        return statement if user_id is None else statement.where(TokenUsage.user_id == user_id)

    async def totals(self, since: datetime, user_id: str | None) -> Row:
        return (await self.session.execute(self._scope(select(*self._sums()), since, user_id))).one()

    async def by_node(self, since: datetime, user_id: str | None) -> list[Row]:
        statement = self._scope(select(TokenUsage.node, *self._sums()), since, user_id)
        return list(
            await self.session.execute(
                statement.group_by(TokenUsage.node).order_by(func.sum(TokenUsage.total_tokens).desc())
            )
        )

    async def by_day(self, since: datetime, user_id: str | None) -> list[Row]:
        day = func.date(TokenUsage.created_at).label("day")
        statement = self._scope(select(day, *self._sums()), since, user_id)
        return list(await self.session.execute(statement.group_by(day).order_by(day)))

    async def by_model(self, since: datetime, user_id: str | None) -> list[Row]:
        statement = self._scope(select(TokenUsage.model, *self._sums()), since, user_id)
        return list(
            await self.session.execute(
                statement.group_by(TokenUsage.model).order_by(func.sum(TokenUsage.total_tokens).desc())
            )
        )

    async def by_user(self, since: datetime) -> list[Row]:
        statement = select(TokenUsage.user_id, func.max(TokenUsage.user_email).label("email"), *self._sums())
        statement = statement.where(TokenUsage.created_at >= since)
        return list(
            await self.session.execute(
                statement.group_by(TokenUsage.user_id).order_by(func.sum(TokenUsage.total_tokens).desc())
            )
        )
