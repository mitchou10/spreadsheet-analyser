import logging

from app.agent import build_graph, build_llm
from app.backend_client import BackendClient, RunConflict
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="worker.run_agent")
def run_agent(run_id: str, client: BackendClient | None = None, llm=None) -> str:
    """Executes one assistant run: queued -> running -> completed/failed, reporting through the backend.

    The agent graph only needs the conversation id; the run id is just for lifecycle reporting.
    Returns the final status for logs/tests. `client` and `llm` are injectable for tests."""
    client = client or BackendClient.from_env()
    try:
        client.start(run_id)
    except RunConflict:
        logger.info("Run %s is no longer queued (cancelled?), skipping", run_id)
        return "skipped"

    try:
        context = client.context(run_id)
        graph = build_graph(llm or build_llm(context.get("model")), client)
        result = graph.invoke({"conversation_id": context["conversation_id"]})
        client.complete(run_id, result["answer"])
    except RunConflict:
        logger.info("Run %s was cancelled while running, discarding the reply", run_id)
        return "cancelled"
    except Exception as error:
        logger.exception("Run %s failed", run_id)
        client.fail(run_id, f"{type(error).__name__}: {error}")
        return "failed"
    return "completed"
