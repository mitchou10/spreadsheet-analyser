import logging
import tempfile
from pathlib import Path

from app.analysis.storage import AnalysisStorage
from app.backend_client import BackendClient, RunConflict
from app.chart.limits import ChartLimits
from app.chart.render import ChartError, render_chart
from app.query.engine import QueryError, run_query
from app.query.limits import QueryLimits
from app.query.task import _load_tables

logger = logging.getLogger(__name__)


def execute_chart(
    chart_id: str,
    client: BackendClient,
    storage: AnalysisStorage,
    limits: ChartLimits | None = None,
    query_limits: QueryLimits | None = None,
    work_dir: Path | None = None,
) -> str:
    """queued -> running -> completed/failed for one chart. Returns the outcome for logs/tests.

    The chart is drawn from a query the agent already ran: the same SQL runs again on the same files (the backend
    says which), with room for more points than the agent was shown, and the result is drawn with the spec. The PNG
    is written to the exact key the backend gave, then reported. A chart that cannot be drawn as asked fails with
    a message the author can act on, and the columns of the result."""
    limits = limits or ChartLimits()
    base = query_limits or QueryLimits()
    # Same bounds as any query (time, memory, files), but more rows, and no cut on the size of the text.
    query_limits = QueryLimits(
        max_rows=limits.max_points,
        max_result_chars=50_000_000,
        timeout_seconds=base.timeout_seconds,
        memory_limit=base.memory_limit,
        threads=base.threads,
        max_table_bytes=base.max_table_bytes,
        max_files=base.max_files,
    )
    try:
        client.chart_start(chart_id)
    except RunConflict:
        logger.info("Chart %s is no longer queued, skipping", chart_id)
        return "skipped"

    columns: list[dict] = []
    try:
        context = client.chart_context(chart_id)
        with tempfile.TemporaryDirectory(dir=work_dir, prefix="chart_") as tmp:
            sandbox = Path(tmp)
            tables = _load_tables(context, storage, sandbox, query_limits)
            result = run_query(context["sql"], tables, sandbox, query_limits)
        columns = result["columns"]
        png, width, height = render_chart(context["spec"], columns, result["rows"], result["truncated"], limits)
        storage.upload_bytes(context["s3_key"], png, "image/png")
        client.chart_complete(chart_id, context["s3_key"], width, height)
    except RunConflict:
        logger.info("Chart %s was taken or cancelled meanwhile, discarding it", chart_id)
        return "cancelled"
    except (ChartError, QueryError) as error:
        client.chart_fail(chart_id, str(error), columns)
        return "failed"
    except Exception as error:
        logger.exception("Chart %s failed", chart_id)
        client.chart_fail(chart_id, f"Erreur inattendue : {type(error).__name__}", columns)
        return "failed"
    return "completed"
