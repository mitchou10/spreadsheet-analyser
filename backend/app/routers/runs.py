import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends

from app.dependencies import (
    ActorDep,
    AnalysisServiceDep,
    ConversationServiceDep,
    RunServiceDep,
    require_internal_token,
)
from app.schemas import (
    AnalysisCompleteIn,
    AnalysisContextOut,
    AnalysisFailIn,
    AnalysisOut,
    InternalMessageOut,
    RunCompleteIn,
    RunContextOut,
    RunFailIn,
    RunOut,
    ScopeFileOut,
)

router = APIRouter(prefix="/runs", tags=["Runs"])
internal_router = APIRouter(
    prefix="/internal", tags=["Internal (worker)"], dependencies=[Depends(require_internal_token)]
)


@router.get("/{run_id}", summary="Status of a run")
async def get_run(run_id: uuid.UUID, actor: ActorDep, service: RunServiceDep) -> RunOut:
    return RunOut.model_validate(await service.get(actor, run_id))


@router.post("/{run_id}/cancel", summary="Cancel a queued or running run")
async def cancel_run(run_id: uuid.UUID, actor: ActorDep, service: RunServiceDep) -> RunOut:
    return RunOut.model_validate(await service.cancel(actor, run_id))


# --- Called by the worker, authenticated with the internal Bearer token ---


@internal_router.get("/runs/{run_id}/context", summary="Conversation history and scope the run works on")
async def run_context(run_id: uuid.UUID, service: RunServiceDep) -> RunContextOut:
    return RunContextOut(**asdict(await service.context(run_id)))


@internal_router.get("/runs/{run_id}/files", summary="Files the agent may search, with their latest analysis")
async def run_files(run_id: uuid.UUID, service: RunServiceDep) -> list[ScopeFileOut]:
    return [ScopeFileOut(**asdict(file)) for file in await service.scope_files(run_id)]


@internal_router.post("/runs/{run_id}/start", summary="queued -> running (409 if cancelled meanwhile)")
async def start_run(run_id: uuid.UUID, service: RunServiceDep) -> RunOut:
    return RunOut.model_validate(await service.start(run_id))


@internal_router.post("/runs/{run_id}/complete", summary="Store the assistant reply, running -> completed")
async def complete_run(run_id: uuid.UUID, body: RunCompleteIn, service: RunServiceDep) -> RunOut:
    return RunOut.model_validate(await service.complete(run_id, body.content))


@internal_router.post("/runs/{run_id}/fail", summary="Mark the run failed")
async def fail_run(run_id: uuid.UUID, body: RunFailIn, service: RunServiceDep) -> RunOut:
    return RunOut.model_validate(await service.fail(run_id, body.error))


@internal_router.get(
    "/conversations/{conversation_id}/messages", summary="Full history of a conversation, oldest first"
)
async def conversation_history(conversation_id: uuid.UUID, service: ConversationServiceDep) -> list[InternalMessageOut]:
    """What the agent reads: every message with the collection/file scope the user attached to it."""
    return [
        InternalMessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            collection_ids=[c.id for c in m.collections],
            file_ids=[f.id for f in m.files],
            created_at=m.created_at,
        )
        for m in await service.history(conversation_id)
    ]


# --- Spreadsheet analysis worker ---


@internal_router.get("/analyses/{analysis_id}/context", summary="Where to read the file and write analyse.json")
async def analysis_context(analysis_id: uuid.UUID, service: AnalysisServiceDep) -> AnalysisContextOut:
    return AnalysisContextOut(**asdict(await service.context(analysis_id)))


@internal_router.post("/analyses/{analysis_id}/start", summary="pending -> processing (409 if stopped meanwhile)")
async def start_analysis(analysis_id: uuid.UUID, service: AnalysisServiceDep) -> AnalysisOut:
    return AnalysisOut.model_validate(await service.start(analysis_id))


@internal_router.post("/analyses/{analysis_id}/complete", summary="analyse.json is written: processing -> ready")
async def complete_analysis(
    analysis_id: uuid.UUID, body: AnalysisCompleteIn, service: AnalysisServiceDep
) -> AnalysisOut:
    return AnalysisOut.model_validate(await service.complete(analysis_id, body.s3_key))


@internal_router.post("/analyses/{analysis_id}/fail", summary="Mark the analysis failed")
async def fail_analysis(analysis_id: uuid.UUID, body: AnalysisFailIn, service: AnalysisServiceDep) -> AnalysisOut:
    return AnalysisOut.model_validate(await service.fail(analysis_id, body.error))
