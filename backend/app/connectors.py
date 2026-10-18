import redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import RedisSettings
from app.db import engine as db_engine
from app.services.storage import StorageService


class RedisConnector:
    def __init__(self, url: str) -> None:
        self.client = redis.Redis.from_url(url, decode_responses=True)

    def get_health(self) -> dict:
        try:
            self.client.ping()
            return {"name": "redis", "status": "healthy"}
        except redis.RedisError as error:
            return {
                "name": "redis",
                "status": "unhealthy",
                "extras": {"error": str(error)},
            }


class DatabaseConnector:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def get_health(self) -> dict:
        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return {"name": "database", "status": "healthy"}
        except Exception as error:
            return {
                "name": "database",
                "status": "unhealthy",
                "extras": {"error": str(error)},
            }


class StorageConnector:
    """S3 is reported but never makes the API unready: auth and the rest keep working while it is down."""

    def __init__(self, storage: StorageService) -> None:
        self.storage = storage

    async def get_health(self) -> dict:
        extras = {"bucket": self.storage.bucket, "endpoint": self.storage.endpoint}
        try:
            await self.storage.check_bucket()
            return {"name": "s3", "status": "healthy", "critical": False, "extras": extras}
        except Exception as error:
            return {
                "name": "s3",
                "status": "unhealthy",
                "critical": False,
                "extras": {**extras, "error": f"{type(error).__name__}: {error}"},
            }


redis_settings = RedisSettings()
redis_connector = RedisConnector(redis_settings.REDIS_URL)
db_connector = DatabaseConnector(db_engine)
