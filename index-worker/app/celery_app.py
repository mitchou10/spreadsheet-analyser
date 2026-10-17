import os

from celery import Celery

celery_app = Celery(
    "index-worker", broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"), include=["app.tasks"]
)

# Everything about the search indexes (of the collections and of the users) is this worker's job, on its own queue.
celery_app.conf.task_routes = {
    "index.file_analysed": {"queue": "index"},
    "index.forget_file": {"queue": "index"},
    "index.rebuild_collection": {"queue": "index"},
    "index.rebuild_user": {"queue": "index"},
}


@celery_app.task(name="index.ping")
def ping() -> str:
    return "pong"
