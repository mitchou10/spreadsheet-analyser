import logging

from app.agent import generate_reply
from app.backend_client import BackendClient, RunConflict
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="worker.run_agent")
def run_agent(run_id: str, client: BackendClient | None = None) -> str:
    """Executes one assistant run: queued -> running -> completed/failed, reporting through the backend.

    Returns the final status for logs/tests. `client` is injectable for tests."""
    client = client or BackendClient()
    try:
        client.start(run_id)
    except RunConflict:
        logger.info("Run %s is no longer queued (cancelled?), skipping", run_id)
        return "skipped"

    try:
        reply = generate_reply(client.context(run_id))
        client.complete(run_id, reply)
    except RunConflict:
        logger.info("Run %s was cancelled while running, discarding the reply", run_id)
        return "cancelled"
    except Exception as error:
        logger.exception("Run %s failed", run_id)
        client.fail(run_id, f"{type(error).__name__}: {error}")
        return "failed"
    return "completed"
