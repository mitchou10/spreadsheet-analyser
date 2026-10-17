from fastapi import APIRouter, HTTPException, status

from app.dependencies import ActorDep, ModelCatalogDep
from app.schemas import ModelOut, ModelsOut
from app.services.models import ModelProviderError

router = APIRouter(prefix="/models", tags=["Models"])


@router.get("", summary="LLMs the assistant can use (as listed by the OpenAI-compatible provider)")
async def list_models(_: ActorDep, catalog: ModelCatalogDep) -> ModelsOut:
    """`default` is used when a message does not choose a model; pass any `models[].id` as `model` when sending."""
    try:
        models = await catalog.list_models()
    except ModelProviderError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error
    return ModelsOut(
        default=await catalog.resolve_default(),
        models=[ModelOut(id=m.id, owned_by=m.owned_by) for m in models],
    )
