from app.analysis.storage import AnalysisStorage
from app.analysis.task import execute_analysis
from app.backend_client import BackendClient
from app.celery_app import celery_app
from app.indexing import IndexManager, RedisCollectionLocks


def _indexer(client: BackendClient, storage: AnalysisStorage) -> IndexManager:
    return IndexManager(client, storage, RedisCollectionLocks.from_env())


@celery_app.task(name="analysis.run")
def run_analysis(
    analysis_id: str,
    client: BackendClient | None = None,
    storage: AnalysisStorage | None = None,
    indexer: IndexManager | None = None,
) -> str:
    """Profiles the spreadsheet of one analysis (see app.analysis), then adds it to its collection's search index.
    Runs on the `analysis` queue, in its own worker process with its own memory limit."""
    client = client or BackendClient.from_env()
    storage = storage or AnalysisStorage()
    return execute_analysis(analysis_id, client, storage, indexer=indexer or _indexer(client, storage))


@celery_app.task(name="analysis.forget_file")
def forget_file(collection_id: str, file_id: str, indexer: IndexManager | None = None) -> str:
    """A file was deleted: drop it from its collection's search index."""
    if indexer is None:
        client = BackendClient.from_env()
        indexer = _indexer(client, AnalysisStorage())
    return "removed" if indexer.forget_file(collection_id, file_id) else "absent"


@celery_app.task(name="analysis.rebuild_index")
def rebuild_index(collection_id: str, indexer: IndexManager | None = None) -> int:
    """Rebuilds a collection's search index from its ready analyses (backfill or repair). Returns the file count."""
    if indexer is None:
        client = BackendClient.from_env()
        indexer = _indexer(client, AnalysisStorage())
    return indexer.rebuild(collection_id)
