from fastapi import APIRouter, Response, status

from app.connectors import db_connector, redis_connector

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Perform a health check",
    status_code=status.HTTP_200_OK,
)
async def get_health(response: Response) -> dict:
    dependencies = [redis_connector.get_health(), await db_connector.get_health()]

    api_status = "healthy"
    for dependency in dependencies:
        if dependency["status"] == "unhealthy":
            api_status = "unhealthy"
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {"status": api_status, "dependencies": dependencies}
