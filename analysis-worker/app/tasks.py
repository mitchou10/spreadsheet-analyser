from app.analysis.storage import AnalysisStorage
from app.analysis.task import execute_analysis
from app.backend_client import BackendClient
from app.celery_app import celery_app


@celery_app.task(name="analysis.run")
def run_analysis(analysis_id: str, client: BackendClient | None = None, storage: AnalysisStorage | None = None) -> str:
    """Profiles the spreadsheet of one analysis (see app.analysis). Runs on the `analysis` queue, in its own
    worker process with its own memory limit."""
    return execute_analysis(analysis_id, client or BackendClient.from_env(), storage or AnalysisStorage())
