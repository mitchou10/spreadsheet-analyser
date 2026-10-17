from app.celery_app import ping


def test_ping() -> None:
    assert ping.run() == "pong"
