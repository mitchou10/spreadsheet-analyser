from dataclasses import asdict

from fastapi import APIRouter, Query

from app.dependencies import ActorDep, UsageServiceDep
from app.schemas import UsageOut

router = APIRouter(prefix="/usage", tags=["Usage"])


@router.get("/me", summary="Tokens my questions consumed, in total and per graph node, day and model")
async def my_usage(actor: ActorDep, service: UsageServiceDep, days: int = Query(30, ge=1, le=365)) -> UsageOut:
    return UsageOut.model_validate(asdict(await service.mine(actor, days)))
