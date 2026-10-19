import logging

from fastapi import APIRouter, Response, status

from app.connectors import StorageConnector, db_connector, redis_connector
from app.dependencies import ActorDep, StorageDep
from app.version import app_version

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Perform a health check",
    status_code=status.HTTP_200_OK,
)
async def get_health(response: Response, storage: StorageDep) -> dict:
    dependencies = [
        redis_connector.get_health(),
        await db_connector.get_health(),
        await StorageConnector(storage).get_health(),
    ]

    api_status = "healthy"
    for dependency in dependencies:
        if dependency["status"] != "unhealthy":
            continue
        # The reason is in the response body, but a probe only keeps the status code: log it too.
        logger.warning("Health check: %s is unhealthy: %s", dependency["name"], dependency.get("extras"))
        if dependency.get("critical", True):
            api_status = "unhealthy"
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {"status": api_status, "dependencies": dependencies}


@router.get("/version", summary="Version of the application (for signed-in users)")
async def get_version(_: ActorDep) -> dict[str, str]:
    return {"version": app_version()}
