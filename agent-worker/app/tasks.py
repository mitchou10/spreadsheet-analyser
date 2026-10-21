import logging

from app.backend_client import BackendClient, RunConflict
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


# Bounds accepted by the backend for a trace.
MAX_TRACE_STEPS = 50
MAX_TRACE_FILES = 200
MAX_TRACE_PLAN_CHARS = 8000
MAX_TRACE_USAGE_CALLS = 100


def _usage(calls: list[dict]) -> dict | None:
    """Tokens per LLM call (node) and in total; None when the provider reported nothing."""
    if not calls:
        return None
    return {
        "input_tokens": sum(c["input_tokens"] for c in calls),
        "output_tokens": sum(c["output_tokens"] for c in calls),
        "total_tokens": sum(c["total_tokens"] for c in calls),
        "calls": calls[:MAX_TRACE_USAGE_CALLS],
    }


def _trace(result: dict, usage_calls: list[dict]) -> dict:
    """What the agent worked from, for the backend to store with the answer."""
    trace = {
        "plan": (result.get("plan") or "")[:MAX_TRACE_PLAN_CHARS],
        "files": result.get("files", [])[:MAX_TRACE_FILES],
        "steps": result.get("trace_steps", [])[:MAX_TRACE_STEPS],
    }
    usage = _usage(usage_calls)
    if usage:
        trace["usage"] = usage
    return trace


def _report_usage(client: BackendClient, run_id: str, calls: list[dict]) -> None:
    """Tokens were spent whatever became of the run: tell the backend, without ever failing the run for it."""
    if not calls:
        return
    try:
        client.record_usage(run_id, calls[:MAX_TRACE_USAGE_CALLS])
    except Exception:
        logger.exception("Run %s: could not report its token usage", run_id)


@celery_app.task(name="worker.run_agent")
def run_agent(run_id: str, client: BackendClient | None = None, llm=None, storage=None) -> str:
    """Executes one assistant run: queued -> running -> completed/failed, reporting through the backend.

    The agent graph takes the conversation id as input; the run id also tells it which files (and
    analyses) are in scope.
    Returns the final status for logs/tests. `client`, `llm` and `storage` are injectable for tests."""
    # Imported here so that merely importing this module (Celery start-up, tests of other parts) stays light.
    from app.agent import build_graph, build_llm
    from app.agent.storage import S3Reader

    client = client or BackendClient.from_env()
    try:
        client.start(run_id)
    except RunConflict:
        logger.info("Run %s is no longer queued (cancelled?), skipping", run_id)
        return "skipped"

    usage_calls: list[dict] = []
    try:
        context = client.context(run_id)
        graph = build_graph(
            llm or build_llm(context.get("model")),
            client,
            storage or S3Reader(),
            run_id,
            user_email=context.get("requester_email"),
            usage_sink=usage_calls,
        )
        result = graph.invoke({"conversation_id": context["conversation_id"]})
        _report_usage(client, run_id, usage_calls)
        client.complete(run_id, result["answer"], _trace(result, usage_calls))
    except RunConflict:
        logger.info("Run %s was cancelled while running, discarding the reply", run_id)
        _report_usage(client, run_id, usage_calls)
        return "cancelled"
    except Exception as error:
        logger.exception("Run %s failed", run_id)
        _report_usage(client, run_id, usage_calls)
        client.fail(run_id, f"{type(error).__name__}: {error}")
        return "failed"
    return "completed"
