import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RunStatus, SqlQuery, SqlQueryStatus
from app.repositories import RunRepository, SqlQueryRepository
from app.services.dispatcher import RunDispatcher
from app.services.errors import ConflictError, NotFoundError
from app.services.run import RunService

logger = logging.getLogger(__name__)

# One query joins at most this many files (the worker downloads and opens each of them).
MAX_QUERY_FILES = 10


@dataclass
class QueryContext:
    """What the query worker needs to run a query."""

    query_id: uuid.UUID
    sql: str
    tables: list[dict]  # [{"ref", "file_id", "file_name", "result_key"}]


class SqlQueryService:
    """SQL over the files of a run: the agent asks, the analysis worker computes, the backend decides what may be
    read and keeps the result. Workers never talk to each other or to the database: everything goes through here."""

    def __init__(self, session: AsyncSession, dispatcher: RunDispatcher) -> None:
        self.session = session
        self.dispatcher = dispatcher
        self.queries = SqlQueryRepository(session)
        self.runs = RunRepository(session)
        self.run_service = RunService(session, dispatcher)

    # --- Agent side ---

    async def create(self, run_id: uuid.UUID, sql: str, files: dict[str, uuid.UUID]) -> SqlQuery:
        """Queues `sql` over `files` ({schema name: file id}). Only files of the run's scope, with a ready
        analysis, can be read: the same files, and so the same access rights, as the agent's other tools."""
        run = await self.runs.get(run_id)
        if run is None:
            raise NotFoundError(f"Run {run_id} not found")
        if run.status != RunStatus.RUNNING:
            raise ConflictError(f"Run {run_id} is {run.status}: queries are only accepted while it is running")
        if not files:
            raise ConflictError("Name at least one file to query")
        if len(files) > MAX_QUERY_FILES:
            raise ConflictError(f"Too many files in one query ({len(files)}): {MAX_QUERY_FILES} at most")

        scope = {file.file_id: file for file in await self.run_service.scope_files(run_id)}
        tables = []
        for ref, file_id in files.items():
            file = scope.get(file_id)
            if file is None:
                raise NotFoundError(f"File {ref} is not in the scope of this run")
            if file.result_key is None:
                raise ConflictError(f"File {file.file_name} has no ready analysis ({file.analysis_status or 'none'})")
            tables.append(
                {"ref": ref, "file_id": str(file_id), "file_name": file.file_name, "result_key": file.result_key}
            )

        query = await self.queries.add(SqlQuery(run_id=run_id, sql=sql, tables=tables))
        await self.session.commit()
        try:
            query.task_id = await self.dispatcher.enqueue_query(query.id)
        except Exception:
            logger.exception("Could not hand query %s to the worker", query.id)
            return await self._finish(query, SqlQueryStatus.FAILED, error="The query worker is unreachable")
        await self.session.commit()
        return query

    async def get(self, query_id: uuid.UUID) -> SqlQuery:
        query = await self.queries.get(query_id)
        if query is None:
            raise NotFoundError(f"Query {query_id} not found")
        return query

    # --- Worker side ---

    async def context(self, query_id: uuid.UUID) -> QueryContext:
        query = await self.get(query_id)
        return QueryContext(query_id=query.id, sql=query.sql, tables=query.tables)

    async def start(self, query_id: uuid.UUID) -> SqlQuery:
        query = await self.get(query_id)
        if query.status != SqlQueryStatus.QUEUED:
            raise ConflictError(f"Query {query_id} is {query.status}, not queued")
        query.status = SqlQueryStatus.RUNNING
        query.started_at = datetime.now(UTC)
        await self.session.commit()
        return query

    async def complete(self, query_id: uuid.UUID, result: dict) -> SqlQuery:
        query = await self.get(query_id)
        if query.status != SqlQueryStatus.RUNNING:
            raise ConflictError(f"Query {query_id} is {query.status}, not running")
        query.result = result
        return await self._finish(query, SqlQueryStatus.COMPLETED)

    async def fail(self, query_id: uuid.UUID, error: str, tables: list[dict] | None = None) -> SqlQuery:
        query = await self.get(query_id)
        if query.status in (SqlQueryStatus.COMPLETED, SqlQueryStatus.FAILED):
            return query
        query.available_tables = tables or None
        return await self._finish(query, SqlQueryStatus.FAILED, error=error[:4000])

    async def _finish(self, query: SqlQuery, status: SqlQueryStatus, error: str | None = None) -> SqlQuery:
        query.status = status
        query.error = error
        query.finished_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(query)
        return query
