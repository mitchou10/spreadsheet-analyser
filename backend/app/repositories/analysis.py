import uuid

from app.models import Analysis
from app.repositories.base import BaseRepository


class AnalysisRepository(BaseRepository[Analysis]):
    model = Analysis

    async def list_by_file(self, file_id: uuid.UUID) -> list[Analysis]:
        return await self._all(self._select().where(Analysis.file_id == file_id).order_by(Analysis.created_at.desc()))

    async def get_latest(self, file_id: uuid.UUID, file_version: int) -> Analysis | None:
        return await self._first(
            self._select()
            .where(Analysis.file_id == file_id, Analysis.file_version == file_version)
            .order_by(Analysis.created_at.desc())
            .limit(1)
        )
