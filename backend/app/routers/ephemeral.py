import uuid
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile, status

from app.config import S3Settings
from app.dependencies import ActorDep, EphemeralServiceDep, ModelCatalogDep, require_internal_token
from app.routers.collections import ALLOWED_EXTENSIONS
from app.routers.conversations import _check_model
from app.schemas import EphemeralAnalysisOut, EphemeralChartOut, EphemeralRunCreate, EphemeralRunOut, RunOut
from app.services.chart import chart_url
from app.services.ephemeral import EphemeralRun

router = APIRouter(prefix="/ephemeral", tags=["Ephemeral analysis"])
internal_router = APIRouter(
    prefix="/internal/ephemeral", tags=["Internal (worker)"], dependencies=[Depends(require_internal_token)]
)
_settings = S3Settings()


def _chart_url(run_id: uuid.UUID, chart_id: uuid.UUID) -> str:
    return f"/api/ephemeral/runs/{run_id}/charts/{chart_id}"


def _run_out(item: EphemeralRun) -> EphemeralRunOut:
    run = item.run
    answer = item.answer.content if item.answer else None
    if answer:
        # The answer shows its charts through the chat's route (under the conversation, which an API client never
        # sees): point them to the route of the run instead.
        for chart in item.charts:
            answer = answer.replace(chart_url(chart), _chart_url(run.id, chart.id))
    return EphemeralRunOut(
        id=run.id,
        analysis_id=item.analysis_id,
        status=run.status,
        error=run.error,
        model=run.model,
        created_at=run.created_at,
        finished_at=run.finished_at,
        answer=answer,
        trace=item.answer.trace if item.answer else None,
        charts=[
            EphemeralChartOut(
                id=c.id,
                title=c.title,
                status=c.status,
                error=c.error,
                width=c.width,
                height=c.height,
                url=_chart_url(run.id, c.id),
            )
            for c in item.charts
        ],
    )


@router.post(
    "/analyses",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload one or more spreadsheets for an analysis that is deleted after a while (multipart, field 'files')",
)
async def create_analysis(
    files: list[UploadFile],
    actor: ActorDep,
    service: EphemeralServiceDep,
    ttl_hours: Annotated[int | None, Form(description="Hours to keep it after the last run (default 24)")] = None,
) -> EphemeralAnalysisOut:
    """Starts the pre-analysis of each file (profile of the sheets and columns) and returns right away: poll
    `GET /analyses/{id}` until `status` is `ready`, then ask a question with `POST /analyses/{id}/runs`."""
    uploads = []
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
        uploads.append((name, content, upload.content_type))
    return _analysis_out(await service.create(actor, uploads, ttl_hours))


def _analysis_out(analysis) -> EphemeralAnalysisOut:
    data = asdict(analysis)
    data["files"] = [{**file, "id": file["file_id"]} for file in data["files"]]
    return EphemeralAnalysisOut.model_validate(data)


@router.get("/analyses/{analysis_id}", summary="State of the pre-analysis of the files")
async def get_analysis(analysis_id: uuid.UUID, actor: ActorDep, service: EphemeralServiceDep) -> EphemeralAnalysisOut:
    return _analysis_out(await service.get(actor, analysis_id))


@router.post(
    "/analyses/{analysis_id}/runs",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ask a question about the files; returns the run to poll",
)
async def create_run(
    analysis_id: uuid.UUID,
    body: EphemeralRunCreate,
    actor: ActorDep,
    service: EphemeralServiceDep,
    catalog: ModelCatalogDep,
) -> RunOut:
    """409 while the files are still being analysed or a previous run is in progress, 422 if none of the files
    could be analysed. The answer is read with `GET /runs/{id}`."""
    await _check_model(catalog, body.model)
    run = await service.start_run(
        actor, analysis_id, body.query, model=body.model, default_model=await catalog.resolve_default()
    )
    return RunOut.model_validate(run)


@router.get("/runs/{run_id}", summary="Status of a run and, once completed, the assistant's answer")
async def get_run(run_id: uuid.UUID, actor: ActorDep, service: EphemeralServiceDep) -> EphemeralRunOut:
    return _run_out(await service.get_run(actor, run_id))


@router.get(
    "/runs/{run_id}/charts/{chart_id}",
    summary="The image of a chart drawn by a run (PNG)",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
async def get_chart_image(
    run_id: uuid.UUID, chart_id: uuid.UUID, actor: ActorDep, service: EphemeralServiceDep
) -> Response:
    image = await service.read_chart(actor, run_id, chart_id)
    return Response(
        content=image,
        media_type="image/png",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.delete(
    "/analyses/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete the files and results now"
)
async def delete_analysis(analysis_id: uuid.UUID, actor: ActorDep, service: EphemeralServiceDep) -> None:
    await service.delete(actor, analysis_id)


@internal_router.post("/purge", summary="Delete the ephemeral analyses past their expiry (for a scheduler)")
async def purge(service: EphemeralServiceDep) -> dict[str, int]:
    return {"purged": await service.purge_expired()}
