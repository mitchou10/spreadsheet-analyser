from app.analysis.storage import AnalysisStorage
from app.analysis.task import execute_analysis
from app.backend_client import BackendClient
from app.celery_app import celery_app
from app.chart.task import execute_chart
from app.query.task import execute_query


@celery_app.task(name="analysis.run")
def run_analysis(analysis_id: str, client: BackendClient | None = None, storage: AnalysisStorage | None = None) -> str:
    """Profiles the spreadsheet of one analysis (see app.analysis). Runs on the `analysis` queue, in its own
    worker process with its own memory limit. The search indexes are not its business: the backend tells the
    index worker when an analysis is ready."""
    return execute_analysis(analysis_id, client or BackendClient.from_env(), storage or AnalysisStorage())


@celery_app.task(name="analysis.query")
def run_query(query_id: str, client: BackendClient | None = None, storage: AnalysisStorage | None = None) -> str:
    """Runs one SQL query over the Parquet copies of sheets (see app.query). Own queue, same worker image: a person
    waiting for an answer must not queue behind the analysis of a large file."""
    return execute_query(query_id, client or BackendClient.from_env(), storage or AnalysisStorage())


@celery_app.task(name="analysis.chart")
def draw_chart(chart_id: str, client: BackendClient | None = None, storage: AnalysisStorage | None = None) -> str:
    """Draws one chart from the result of a query (see app.chart). Same queue and worker as the SQL queries."""
    return execute_chart(chart_id, client or BackendClient.from_env(), storage or AnalysisStorage())
