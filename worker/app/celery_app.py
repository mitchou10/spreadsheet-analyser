import os

from celery import Celery

celery_app = Celery("worker", broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"), include=["app.tasks"])

# Each kind of work has its own queue, consumed by its own worker service (see docker-compose.yaml).
celery_app.conf.task_routes = {
    "worker.run_agent": {"queue": "agent"},
    "analysis.run": {"queue": "analysis"},
}


@celery_app.task(name="worker.ping")
def ping() -> str:
    return "pong"
