import uuid
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Response, UploadFile, status

from app.config import S3Settings
from app.dependencies import ActorDep, AnalysisServiceDep, CollectionServiceDep, FileServiceDep
from app.models import AccessCollection, Collection, File
from app.schemas import (
    AccessCreate,
    AccessOut,
    AnalysisOut,
    AnalysisResultOut,
    CollectionCreate,
    CollectionOut,
    CollectionUpdate,
    FileOut,
)

collections_router = APIRouter(prefix="/collections", tags=["Collections"])
files_router = APIRouter(prefix="/files", tags=["Files"])

ALLOWED_EXTENSIONS = (".xlsx", ".xls", ".csv", ".ods")
_settings = S3Settings()


def _collection_out(collection: Collection, actor_user_id: str, file_count: int) -> CollectionOut:
    return CollectionOut(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        created_at=collection.created_at,
        is_owner=collection.created_by == actor_user_id,
        file_count=file_count,
    )


async def _files_out(files: list[File], analyses: AnalysisServiceDep) -> list[FileOut]:
    latest = await analyses.latest_by_file([file.id for file in files])
    out = []
    for file in files:
        analysis = latest.get(file.id)
        out.append(
            FileOut(
                id=file.id,
                collection_id=file.collection_id,
                name=file.name,
                size_bytes=file.size_bytes,
                version=file.version,
                uploaded_at=file.uploaded_at,
                updated_at=analysis.updated_at if analysis else file.uploaded_at,
                status=analysis.status if analysis else "pending",
            )
        )
    return out


# --- Collections ---


@collections_router.get("", summary="Collections I own or that were shared with me")
async def list_collections(actor: ActorDep, service: CollectionServiceDep) -> list[CollectionOut]:
    collections = await service.list_for_user(actor)
    counts = await service.file_counts(collections)
    return [_collection_out(c, actor.user_id, counts.get(c.id, 0)) for c in collections]


@collections_router.post("", status_code=status.HTTP_201_CREATED, summary="Create a collection")
async def create_collection(body: CollectionCreate, actor: ActorDep, service: CollectionServiceDep) -> CollectionOut:
    collection = await service.create(actor, body.name.strip(), body.description)
    return _collection_out(collection, actor.user_id, 0)


@collections_router.get("/{collection_id}", summary="Get a collection")
async def get_collection(collection_id: uuid.UUID, actor: ActorDep, service: CollectionServiceDep) -> CollectionOut:
    collection = await service.get(actor, collection_id)
    counts = await service.file_counts([collection])
    return _collection_out(collection, actor.user_id, counts.get(collection.id, 0))


@collections_router.patch("/{collection_id}", summary="Rename / describe a collection (owner only)")
async def update_collection(
    collection_id: uuid.UUID, body: CollectionUpdate, actor: ActorDep, service: CollectionServiceDep
) -> CollectionOut:
    collection = await service.update(actor, collection_id, body.name, body.description)
    counts = await service.file_counts([collection])
    return _collection_out(collection, actor.user_id, counts.get(collection.id, 0))


@collections_router.delete(
    "/{collection_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a collection and its files (owner only)"
)
async def delete_collection(collection_id: uuid.UUID, actor: ActorDep, service: CollectionServiceDep) -> None:
    await service.delete(actor, collection_id)


# --- Files of a collection ---


@collections_router.get("/{collection_id}/files", summary="Files of a collection with their analysis status")
async def list_files(
    collection_id: uuid.UUID, actor: ActorDep, files: FileServiceDep, analyses: AnalysisServiceDep
) -> list[FileOut]:
    return await _files_out(await files.list_in_collection(actor, collection_id), analyses)


@collections_router.post(
    "/{collection_id}/files",
    status_code=status.HTTP_201_CREATED,
    summary="Upload one or more spreadsheets (multipart, field name 'files') - owner only",
)
async def upload_files(
    collection_id: uuid.UUID,
    files: list[UploadFile],
    actor: ActorDep,
    file_service: FileServiceDep,
    analyses: AnalysisServiceDep,
) -> list[FileOut]:
    """Re-uploading a name already in the collection stores a new version. Each new version is
    queued for analysis (status `pending`); identical content is a no-op."""
    uploaded: list[File] = []
    for upload in files:
        name = upload.filename or ""
        if not name.lower().endswith(ALLOWED_EXTENSIONS):
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                f"{name or 'file'}: unsupported type, expected one of {', '.join(ALLOWED_EXTENSIONS)}",
            )
        content = await upload.read(_settings.MAX_UPLOAD_BYTES + 1)
        if len(content) > _settings.MAX_UPLOAD_BYTES:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE, f"{name}: exceeds {_settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB"
            )
        file = await file_service.upload(actor, collection_id, name, content, upload.content_type)
        await analyses.ensure_current(actor, file.id)
        uploaded.append(file)
    return await _files_out(uploaded, analyses)


# --- Sharing (owner only) ---


@collections_router.get("/{collection_id}/access", summary="Who the collection is shared with")
async def list_access(collection_id: uuid.UUID, actor: ActorDep, service: CollectionServiceDep) -> list[AccessOut]:
    return [AccessOut.model_validate(a) for a in await service.list_access(actor, collection_id)]


@collections_router.post(
    "/{collection_id}/access", status_code=status.HTTP_201_CREATED, summary="Share the collection (read-only) by email"
)
async def share_collection(
    collection_id: uuid.UUID, body: AccessCreate, actor: ActorDep, service: CollectionServiceDep
) -> AccessOut:
    access: AccessCollection = await service.share(actor, collection_id, body.email)
    return AccessOut.model_validate(access)


@collections_router.delete(
    "/{collection_id}/access/{email}", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke an email's access"
)
async def revoke_access(collection_id: uuid.UUID, email: str, actor: ActorDep, service: CollectionServiceDep) -> None:
    await service.revoke(actor, collection_id, email)


# --- Single file ---


@files_router.get("/{file_id}/download", summary="Download the current version of a file")
async def download_file(file_id: uuid.UUID, actor: ActorDep, service: FileServiceDep) -> Response:
    file, content = await service.download(actor, file_id)
    return Response(
        content,
        media_type=file.content_type or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(file.name)}"},
    )


@files_router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a file (owner only)")
async def delete_file(file_id: uuid.UUID, actor: ActorDep, service: FileServiceDep) -> None:
    await service.delete(actor, file_id)


@files_router.post(
    "/{file_id}/analysis", status_code=status.HTTP_202_ACCEPTED, summary="(Re)queue an analysis of the current version"
)
async def retry_analysis(
    file_id: uuid.UUID, actor: ActorDep, files: FileServiceDep, analyses: AnalysisServiceDep
) -> FileOut:
    await analyses.create(actor, file_id)
    return (await _files_out([await files.get(actor, file_id)], analyses))[0]


@files_router.post("/{file_id}/analysis/stop", summary="Stop the running analysis")
async def stop_analysis(
    file_id: uuid.UUID, actor: ActorDep, files: FileServiceDep, analyses: AnalysisServiceDep
) -> FileOut:
    await analyses.stop_latest(actor, file_id)
    return (await _files_out([await files.get(actor, file_id)], analyses))[0]


@files_router.get("/{file_id}/analysis", summary="Latest analysis of the file's current version, with its result")
async def get_analysis(file_id: uuid.UUID, actor: ActorDep, analyses: AnalysisServiceDep) -> AnalysisResultOut:
    analysis = await analyses.get_latest_for_file(actor, file_id)
    return AnalysisResultOut(
        **AnalysisOut.model_validate(analysis).model_dump(), result=await analyses.read_result(analysis)
    )
