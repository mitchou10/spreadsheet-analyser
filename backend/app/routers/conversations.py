import uuid

from fastapi import APIRouter, status

from app.dependencies import ActorDep, ConversationServiceDep, RunServiceDep
from app.models import Message
from app.schemas import ConversationCreate, ConversationOut, MessageCreate, MessageOut, RunOut, SendMessageOut

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
        created_at=message.created_at,
    )


@router.get("", summary="My conversations, most recently active first")
async def list_conversations(actor: ActorDep, service: ConversationServiceDep) -> list[ConversationOut]:
    return [ConversationOut.model_validate(c) for c in await service.list_for_user(actor)]


@router.post("", status_code=status.HTTP_201_CREATED, summary="Start a conversation")
async def create_conversation(
    body: ConversationCreate, actor: ActorDep, service: ConversationServiceDep
) -> ConversationOut:
    return ConversationOut.model_validate(await service.create(actor, body.title))


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a conversation")
async def delete_conversation(conversation_id: uuid.UUID, actor: ActorDep, service: ConversationServiceDep) -> None:
    await service.delete(actor, conversation_id)


@router.get("/{conversation_id}/messages", summary="Messages of a conversation, oldest first")
async def list_messages(
    conversation_id: uuid.UUID, actor: ActorDep, service: ConversationServiceDep
) -> list[MessageOut]:
    return [_message_out(m) for m in await service.list_messages(actor, conversation_id)]


@router.post(
    "/{conversation_id}/messages",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send a user message; the assistant's answer is produced asynchronously by a run",
)
async def send_message(
    conversation_id: uuid.UUID, body: MessageCreate, actor: ActorDep, service: RunServiceDep
) -> SendMessageOut:
    """Returns right away with the stored message and its run (poll `GET /runs/{id}` until it is finished).
    409 while a previous run of this conversation is still in progress."""
    message, run = await service.send_message(
        actor, conversation_id, body.content, collection_ids=body.collection_ids, file_ids=body.file_ids
    )
    return SendMessageOut(message=_message_out(message), run=RunOut.model_validate(run))


@router.get("/{conversation_id}/active-run", summary="The run currently in progress, if any (null otherwise)")
async def get_active_run(conversation_id: uuid.UUID, actor: ActorDep, service: RunServiceDep) -> RunOut | None:
    run = await service.get_active(actor, conversation_id)
    return RunOut.model_validate(run) if run else None
