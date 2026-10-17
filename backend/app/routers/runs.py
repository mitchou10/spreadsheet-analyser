import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends

from app.dependencies import ActorDep, RunServiceDep, require_internal_token
from app.schemas import RunCompleteIn, RunContextOut, RunFailIn, RunOut

router = APIRouter(prefix="/runs", tags=["Runs"])
internal_router = APIRouter(
    prefix="/internal/runs", tags=["Internal (worker)"], dependencies=[Depends(require_internal_token)]
)


@router.get("/{run_id}", summary="Status of a run")
async def get_run(run_id: uuid.UUID, actor: ActorDep, service: RunServiceDep) -> RunOut:
    return RunOut.model_validate(await service.get(actor, run_id))


@router.post("/{run_id}/cancel", summary="Cancel a queued or running run")
async def cancel_run(run_id: uuid.UUID, actor: ActorDep, service: RunServiceDep) -> RunOut:
    return RunOut.model_validate(await service.cancel(actor, run_id))


# --- Called by the worker, authenticated with X-Internal-Token ---


@internal_router.get("/{run_id}/context", summary="Conversation history and scope the run works on")
async def run_context(run_id: uuid.UUID, service: RunServiceDep) -> RunContextOut:
    return RunContextOut(**asdict(await service.context(run_id)))


@internal_router.post("/{run_id}/start", summary="queued -> running (409 if cancelled meanwhile)")
async def start_run(run_id: uuid.UUID, service: RunServiceDep) -> RunOut:
    return RunOut.model_validate(await service.start(run_id))


@internal_router.post("/{run_id}/complete", summary="Store the assistant reply, running -> completed")
async def complete_run(run_id: uuid.UUID, body: RunCompleteIn, service: RunServiceDep) -> RunOut:
    return RunOut.model_validate(await service.complete(run_id, body.content))


@internal_router.post("/{run_id}/fail", summary="Mark the run failed")
async def fail_run(run_id: uuid.UUID, body: RunFailIn, service: RunServiceDep) -> RunOut:
    return RunOut.model_validate(await service.fail(run_id, body.error))
