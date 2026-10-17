import os

from celery import Celery

celery_app = Celery(
    "analysis-worker", broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"), include=["app.tasks"]
)

# Spreadsheet analysis has its own queue and its own worker (the agent runs elsewhere: agent-worker).
celery_app.conf.task_routes = {"analysis.run": {"queue": "analysis"}, "analysis.query": {"queue": "query"}}


@celery_app.task(name="analysis.ping")
def ping() -> str:
    return "pong"
