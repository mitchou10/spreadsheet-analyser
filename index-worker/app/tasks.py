from app.backend_client import BackendClient
from app.celery_app import celery_app
from app.indexing import Indexer, RedisDebouncer, RedisLocks
from app.storage import IndexStorage


def _schedule_user_rebuild(email: str, countdown: int) -> None:
    celery_app.send_task("index.rebuild_user", args=[email], queue="index", countdown=countdown)


def _indexer() -> Indexer:
    return Indexer(
        BackendClient.from_env(),
        IndexStorage(),
        RedisLocks.from_env(),
        RedisDebouncer.from_env(),
        _schedule_user_rebuild,
    )


@celery_app.task(name="index.file_analysed")
def file_analysed(analysis_id: str, indexer: Indexer | None = None) -> None:
    """An analysis became ready: add its file to the index of its collection (then refresh the readers' indexes)."""
    (indexer or _indexer()).file_analysed(analysis_id)


@celery_app.task(name="index.forget_file")
def forget_file(collection_id: str, file_id: str, indexer: Indexer | None = None) -> str:
    """A file was deleted: drop it from the index of its collection."""
    return "removed" if (indexer or _indexer()).forget_file(collection_id, file_id) else "absent"


@celery_app.task(name="index.rebuild_collection")
def rebuild_collection(collection_id: str, indexer: Indexer | None = None) -> int:
    """Rebuilds a collection's index from its ready analyses (backfill or repair). Returns the file count."""
    return (indexer or _indexer()).rebuild_collection(collection_id)


@celery_app.task(name="index.rebuild_user")
def rebuild_user(email: str, indexer: Indexer | None = None) -> int:
    """Rebuilds the index of everything a person can read. Returns the file count."""
    return (indexer or _indexer()).rebuild_user(email)
