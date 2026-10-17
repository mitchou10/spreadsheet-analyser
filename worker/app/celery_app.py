import os

from celery import Celery

celery_app = Celery("worker", broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"), include=["app.tasks"])

# Agent runs have their own queue so other workers (e.g. spreadsheet analysis) can consume theirs separately.
celery_app.conf.task_routes = {"worker.run_agent": {"queue": "agent"}}


@celery_app.task(name="worker.ping")
def ping() -> str:
    return "pong"
