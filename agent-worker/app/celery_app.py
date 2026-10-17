import os

from celery import Celery

celery_app = Celery(
    "agent-worker", broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"), include=["app.tasks"]
)

# The agent worker only consumes its own queue; spreadsheet analysis has its own worker (analysis-worker).
celery_app.conf.task_routes = {"worker.run_agent": {"queue": "agent"}}


@celery_app.task(name="worker.ping")
def ping() -> str:
    return "pong"
