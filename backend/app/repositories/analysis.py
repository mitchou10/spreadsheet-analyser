import uuid
from collections.abc import Sequence

from sqlalchemy.dialects.postgresql import distinct_on

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

    async def latest_by_files(self, file_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, Analysis]:
        """Most recent analysis of each file (any version) - one query, Postgres DISTINCT ON."""
        if not file_ids:
            return {}
        analyses = await self._all(
            self._select()
            .where(Analysis.file_id.in_(file_ids))
            .ext(distinct_on(Analysis.file_id))
            .order_by(Analysis.file_id, Analysis.created_at.desc())
        )
        return {analysis.file_id: analysis for analysis in analyses}
