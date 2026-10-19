import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.dependencies import ActorDep, ChartServiceDep, ConversationServiceDep, ModelCatalogDep, RunServiceDep
from app.models import Message
from app.schemas import (
    ConversationCreate,
    ConversationOut,
    ConversationUpdate,
    MessageCreate,
    MessageOut,
    MessagePage,
    MessageSourceCollection,
    MessageSourceFile,
    RunOut,
    RunRetryIn,
    SendMessageOut,
)
from app.services.models import ModelNotAvailableError, ModelProviderError

router = APIRouter(prefix="/conversations", tags=["Conversations"])


def _message_out(message: Message) -> MessageOut:
    return MessageOut(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        tool_calls=message.tool_calls,
        tool_call_id=message.tool_call_id,
        collection_ids=[collection.id for collection in message.collections],
        file_ids=[file.id for file in message.files],
        collections=[MessageSourceCollection(id=c.id, name=c.name) for c in message.collections],
        files=[
            MessageSourceFile(id=f.id, name=f.name, collection_id=f.collection_id, collection_name=f.collection.name)
            for f in message.files
        ],
        trace=message.trace,
        created_at=message.created_at,
    )


@router.get("", summary="My conversations, most recently active first")
async def list_conversations(actor: ActorDep, service: ConversationServiceDep) -> list[ConversationOut]:
    return [ConversationOut.model_validate(c) for c in await service.list_for_user(actor)]


async def _check_model(catalog: ModelCatalogDep, model: str | None) -> None:
    """422 unless the provider lists `model`; 502 if the provider cannot be asked."""
    if not model:
        return
    try:
        await catalog.ensure_available(model)
    except ModelNotAvailableError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
    except ModelProviderError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error


@router.post("", status_code=status.HTTP_201_CREATED, summary="Start a conversation, optionally on a given model")
async def create_conversation(
    body: ConversationCreate, actor: ActorDep, service: ConversationServiceDep, catalog: ModelCatalogDep
) -> ConversationOut:
    await _check_model(catalog, body.model)
    return ConversationOut.model_validate(await service.create(actor, body.title, body.model))


@router.patch("/{conversation_id}", summary="Rename a conversation or switch its model")
async def update_conversation(
    conversation_id: uuid.UUID,
    body: ConversationUpdate,
    actor: ActorDep,
    service: ConversationServiceDep,
    catalog: ModelCatalogDep,
) -> ConversationOut:
    await _check_model(catalog, body.model)
    return ConversationOut.model_validate(await service.update(actor, conversation_id, body.title, body.model))


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a conversation")
async def delete_conversation(conversation_id: uuid.UUID, actor: ActorDep, service: ConversationServiceDep) -> None:
    await service.delete(actor, conversation_id)


@router.get("/{conversation_id}/messages", summary="A page of messages, oldest first within the page")
async def list_messages(
    conversation_id: uuid.UUID,
    actor: ActorDep,
    service: ConversationServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    before: Annotated[uuid.UUID | None, Query(description="Id of the oldest message already loaded")] = None,
) -> MessagePage:
    """Without `before`: the latest `limit` messages. With it: the `limit` messages just before that one."""
    messages, has_more = await service.page_messages(actor, conversation_id, limit, before)
    return MessagePage(items=[_message_out(m) for m in messages], has_more=has_more)


@router.post(
    "/{conversation_id}/messages",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send a user message; the assistant's answer is produced asynchronously by a run",
)
async def send_message(
    conversation_id: uuid.UUID,
    body: MessageCreate,
    actor: ActorDep,
    service: RunServiceDep,
    catalog: ModelCatalogDep,
) -> SendMessageOut:
    """Returns right away with the stored message and its run (poll `GET /runs/{id}` until it is finished).
    The run uses the conversation's model (`model` here switches it first). 409 while a previous run is in progress."""
    await _check_model(catalog, body.model)  # the conversation's own model and the default are trusted
    message, run = await service.send_message(
        actor,
        conversation_id,
        body.content,
        collection_ids=body.collection_ids,
        file_ids=body.file_ids,
        model=body.model,
        default_model=await catalog.resolve_default(),
    )
    return SendMessageOut(message=_message_out(message), run=RunOut.model_validate(run))


@router.post(
    "/{conversation_id}/runs/retry",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Run the assistant again on the last message, when it got no answer (failed or cancelled run)",
)
async def retry_run(
    conversation_id: uuid.UUID,
    actor: ActorDep,
    service: RunServiceDep,
    catalog: ModelCatalogDep,
    body: RunRetryIn | None = None,
) -> RunOut:
    """Same scope as the message, no new message. `model` switches the conversation's model first.
    409 while a run is in progress, or when the last message already has an answer."""
    model = body.model if body else None
    await _check_model(catalog, model)
    run = await service.retry(actor, conversation_id, model=model, default_model=await catalog.resolve_default())
    return RunOut.model_validate(run)


@router.get("/{conversation_id}/active-run", summary="The run currently in progress, if any (null otherwise)")
async def get_active_run(conversation_id: uuid.UUID, actor: ActorDep, service: RunServiceDep) -> RunOut | None:
    run = await service.get_active(actor, conversation_id)
    return RunOut.model_validate(run) if run else None


@router.get(
    "/{conversation_id}/messages/{message_id}/charts/{chart_id}",
    summary="The image of a chart of an answer (PNG), only for the owner of the conversation",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
async def get_chart_image(
    conversation_id: uuid.UUID, message_id: uuid.UUID, chart_id: uuid.UUID, actor: ActorDep, charts: ChartServiceDep
) -> Response:
    """Charts live in S3 but are never linked to directly: they are served here, behind the same session as the
    rest of the conversation. The content of a chart never changes, so it can be cached by the browser."""
    image = await charts.read_image(actor, conversation_id, message_id, chart_id)
    return Response(
        content=image,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=86400, immutable", "X-Content-Type-Options": "nosniff"},
    )
