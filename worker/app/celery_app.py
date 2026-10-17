import os

from celery import Celery

celery_app = Celery("worker", broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"), include=["app.tasks"])


@celery_app.task(name="worker.ping")
def ping() -> str:
    return "pong"
