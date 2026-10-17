import uuid

from sqlalchemy import func, select

from app.models import Chart
from app.repositories.base import BaseRepository


class ChartRepository(BaseRepository[Chart]):
    model = Chart

    async def count_by_run(self, run_id: uuid.UUID) -> int:
        return await self.session.scalar(select(func.count(Chart.id)).where(Chart.run_id == run_id)) or 0
