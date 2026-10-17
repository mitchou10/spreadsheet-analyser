import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import AdminDep, AdminServiceDep, AnalysisServiceDep, get_admin
from app.schemas import AccessCreate, AccessOut, AdminCollectionOut, AdminPersonOut

# Every route here requires the administrator role, whatever the route's own parameters.
router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(get_admin)])


@router.get("/collections", summary="Every collection with its owner and who it is shared with")
async def collections_access(service: AdminServiceDep) -> list[AdminCollectionOut]:
    return [AdminCollectionOut(**asdict(item)) for item in await service.collection_access()]


@router.get("/people", summary="Every person (by email) with the collections they own or can read")
async def people_access(service: AdminServiceDep) -> list[AdminPersonOut]:
    return [AdminPersonOut(**asdict(person)) for person in await service.people_access()]


@router.post(
    "/collections/{collection_id}/access",
    status_code=status.HTTP_201_CREATED,
    summary="Give an email read access to any collection",
)
async def grant_access(
    collection_id: uuid.UUID, body: AccessCreate, admin: AdminDep, service: AdminServiceDep
) -> AccessOut:
    return AccessOut.model_validate(await service.grant(admin, collection_id, body.email))


@router.delete(
    "/collections/{collection_id}/access/{email}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an email's read access to a collection",
)
async def revoke_access(collection_id: uuid.UUID, email: str, service: AdminServiceDep) -> None:
    await service.revoke(collection_id, email)


@router.post(
    "/collections/{collection_id}/search-index",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Rebuild a collection's saved search index from its analyses (backfill or repair)",
)
async def rebuild_search_index(
    collection_id: uuid.UUID, service: AdminServiceDep, analyses: AnalysisServiceDep
) -> None:
    """The analysis worker keeps the index up to date as files come and go; this is for collections analysed
    before the index existed, or after the index format changed."""
    await service.get_collection(collection_id)
    try:
        await analyses.request_index_rebuild(collection_id)
    except Exception as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The analysis worker is unreachable") from error
