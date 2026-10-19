import uuid
from collections.abc import Sequence

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import distinct_on

from app.models import Analysis, AnalysisStatus, File
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

    async def find_reusable(
        self, file_hash: str, extension: str, analyzer_version: str, excluding_file_id: uuid.UUID
    ) -> Analysis | None:
        """A READY analysis of another file with the same content (sha256 and extension, which decides how the file
        is read) made with the same analyzer version, and for the version of that file that has this content."""
        return await self._first(
            self._select()
            .join(File, File.id == Analysis.file_id)
            .where(
                File.file_hash == file_hash,
                File.id != excluding_file_id,
                func.lower(File.name).like(f"%{extension.lower()}"),
                Analysis.file_version == File.version,
                Analysis.status == AnalysisStatus.READY,
                Analysis.s3_key.is_not(None),
                Analysis.analyzer_version == analyzer_version,
            )
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
