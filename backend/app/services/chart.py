import logging
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chart, ChartStatus, RunStatus, SqlQueryStatus
from app.repositories import ChartRepository, RunRepository, SqlQueryRepository
from app.services.conversation import ConversationService
from app.services.dispatcher import RunDispatcher
from app.services.errors import ConflictError, NotFoundError
from app.services.storage import StorageService, chart_key

logger = logging.getLogger(__name__)

# Charts one answer can carry: more is noise, and each one costs a rendering.
MAX_CHARTS_PER_RUN = 6


def chart_url(chart: Chart) -> str:
    """Where the image of a chart is served: under the message that shows it, behind the backend."""
    return f"/api/conversations/{chart.conversation_id}/messages/{chart.message_id}/charts/{chart.id}"


def chart_markdown(chart: Chart) -> str:
    """The markdown that shows a chart in an answer. The title is the alt text: it cannot close the brackets."""
    alt = " ".join(re.sub(r"[\[\]]", " ", chart.title).split())
    return f"![{alt}]({chart_url(chart)})"


class ChartService:
    """Charts of an answer: the agent asks for one from the result of a query it ran, the query worker draws it, the
    backend keeps the record and is the only way to the image."""

    def __init__(self, session: AsyncSession, dispatcher: RunDispatcher, storage: StorageService) -> None:
        self.session = session
        self.dispatcher = dispatcher
        self.storage = storage
        self.charts = ChartRepository(session)
        self.runs = RunRepository(session)
        self.queries = SqlQueryRepository(session)
        self.conversations = ConversationService(session)

    # --- Agent side ---

    async def create(self, run_id: uuid.UUID, query_id: uuid.UUID, spec: dict) -> Chart:
        """Queues the drawing of `spec` over the result of `query_id`, a query this run ran and that succeeded."""
        run = await self.runs.get(run_id)
        if run is None:
            raise NotFoundError(f"Run {run_id} not found")
        if run.status != RunStatus.RUNNING:
            raise ConflictError(f"Run {run_id} is {run.status}: charts are only accepted while it is running")
        query = await self.queries.get(query_id)
        if query is None or query.run_id != run_id:
            raise NotFoundError(f"Query {query_id} is not a query of this run")
        if query.status != SqlQueryStatus.COMPLETED:
            raise ConflictError(f"Query {query_id} is {query.status}: a chart needs the result of a successful query")
        if await self.charts.count_by_run(run_id) >= MAX_CHARTS_PER_RUN:
            raise ConflictError(f"An answer carries at most {MAX_CHARTS_PER_RUN} charts")

        if run.answer_message_id is None:  # a run created before charts existed
            run.answer_message_id = uuid.uuid4()
        chart_id = uuid.uuid4()
        chart = await self.charts.add(
            Chart(
                id=chart_id,
                run_id=run_id,
                conversation_id=run.conversation_id,
                message_id=run.answer_message_id,
                query_id=query_id,
                title=spec["title"],
                spec=spec,
                s3_key=chart_key(run.conversation_id, run.answer_message_id, chart_id),
            )
        )
        await self.session.commit()
        try:
            chart.task_id = await self.dispatcher.enqueue_chart(chart.id)
        except Exception:
            logger.exception("Could not hand chart %s to the worker", chart.id)
            return await self._finish(chart, ChartStatus.FAILED, error="The chart worker is unreachable")
        await self.session.commit()
        return chart

    async def get(self, chart_id: uuid.UUID) -> Chart:
        chart = await self.charts.get(chart_id)
        if chart is None:
            raise NotFoundError(f"Chart {chart_id} not found")
        return chart

    # --- Worker side ---

    async def context(self, chart_id: uuid.UUID) -> tuple[Chart, str, list[dict]]:
        """The chart, and the SQL and the files of the query it is drawn from."""
        chart = await self.get(chart_id)
        query = await self.queries.get(chart.query_id)
        if query is None:
            raise NotFoundError(f"Query {chart.query_id} not found")
        return chart, query.sql, query.tables

    async def start(self, chart_id: uuid.UUID) -> Chart:
        chart = await self.get(chart_id)
        if chart.status != ChartStatus.QUEUED:
            raise ConflictError(f"Chart {chart_id} is {chart.status}, not queued")
        chart.status = ChartStatus.RUNNING
        await self.session.commit()
        return chart

    async def complete(self, chart_id: uuid.UUID, s3_key: str, width: int, height: int) -> Chart:
        chart = await self.get(chart_id)
        if chart.status != ChartStatus.RUNNING:
            raise ConflictError(f"Chart {chart_id} is {chart.status}, not running")
        if s3_key != chart.s3_key:  # same rule as the analyses: the worker writes exactly where it was told to
            raise ConflictError(f"Unexpected key {s3_key}")
        chart.width, chart.height = width, height
        return await self._finish(chart, ChartStatus.COMPLETED)

    async def fail(self, chart_id: uuid.UUID, error: str, columns: list[dict] | None = None) -> Chart:
        chart = await self.get(chart_id)
        if chart.status in (ChartStatus.COMPLETED, ChartStatus.FAILED):
            return chart
        chart.available_columns = columns or None
        return await self._finish(chart, ChartStatus.FAILED, error=error[:4000])

    # --- User side ---

    async def read_image(self, actor, conversation_id: uuid.UUID, message_id: uuid.UUID, chart_id: uuid.UUID) -> bytes:
        """The PNG of a chart, for the owner of the conversation only. The ids in the URL must all agree: a chart
        is reachable under its own message and conversation, nowhere else."""
        await self.conversations.get(actor, conversation_id)  # ownership: 404 for anyone else
        chart = await self.charts.get(chart_id)
        if (
            chart is None
            or chart.conversation_id != conversation_id
            or chart.message_id != message_id
            or chart.status != ChartStatus.COMPLETED
        ):
            raise NotFoundError(f"Chart {chart_id} not found")
        return await self.storage.get_object(chart.s3_key)

    async def _finish(self, chart: Chart, status: ChartStatus, error: str | None = None) -> Chart:
        chart.status = status
        chart.error = error
        chart.finished_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(chart)
        return chart
