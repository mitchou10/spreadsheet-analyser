import uuid

from sqlalchemy import delete, func, select

from app.models import Chart
from app.repositories.base import BaseRepository


class ChartRepository(BaseRepository[Chart]):
    model = Chart

    async def list_by_run(self, run_id: uuid.UUID) -> list[Chart]:
        return await self._all(self._select().where(Chart.run_id == run_id).order_by(Chart.created_at, Chart.id))

    async def delete_by_message(self, message_id: uuid.UUID) -> None:
        """The charts of one answer; the message id has no foreign key, so nothing cascades."""
        await self.session.execute(delete(Chart).where(Chart.message_id == message_id))

    async def count_by_run(self, run_id: uuid.UUID) -> int:
        return await self.session.scalar(select(func.count(Chart.id)).where(Chart.run_id == run_id)) or 0
