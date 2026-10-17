import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import AnalysisStatus, ConversationStatus, MessageRole, RunStatus, SqlQueryStatus


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class CollectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class CollectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    # False for collections shared with the caller (read-only).
    is_owner: bool
    file_count: int


class FileOut(BaseModel):
    id: uuid.UUID
    collection_id: uuid.UUID
    name: str
    size_bytes: int
    version: int
    uploaded_at: datetime
    # Last analysis activity (falls back to the upload time).
    updated_at: datetime
    status: AnalysisStatus


class AccessCreate(BaseModel):
    email: str = Field(max_length=320)

    @field_validator("email")
    @classmethod
    def _looks_like_an_email(cls, value: str) -> str:
        value = value.strip()
        if "@" not in value[1:-1]:
            raise ValueError("invalid email")
        return value


class AccessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    granted_by: str
    created_at: datetime


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    # An id from GET /models; omitted = the default model.
    model: str | None = Field(default=None, max_length=255)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    model: str | None = Field(default=None, min_length=1, max_length=255)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    # The conversation's model; null = the default one.
    model: str | None
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(min_length=1)
    # Optional scope: aim this question at some collections / specific files (must be readable by the caller).
    collection_ids: list[uuid.UUID] = []
    file_ids: list[uuid.UUID] = []
    # Switches the conversation's model from this message on; omitted = keep the conversation's model.
    model: str | None = None


class TraceStep(BaseModel):
    """One tool call of the agent: what it asked and what it got back (the output is cut by the worker)."""

    tool: str = Field(max_length=100)
    arguments: dict = {}
    output: str = Field(default="", max_length=8000)


class TraceFile(BaseModel):
    file_id: str = Field(max_length=64)
    file_name: str = Field(max_length=255)
    collection_name: str = Field(default="", max_length=255)


class RunTrace(BaseModel):
    """What the agent worked from to produce an answer: its plan, the files in scope and its tool calls."""

    plan: str = Field(default="", max_length=8000)
    files: list[TraceFile] = Field(default=[], max_length=200)
    steps: list[TraceStep] = Field(default=[], max_length=50)


class MessageSourceCollection(BaseModel):
    id: uuid.UUID
    name: str


class MessageSourceFile(BaseModel):
    id: uuid.UUID
    name: str
    collection_id: uuid.UUID
    collection_name: str


class MessageOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole
    content: str | None
    tool_calls: list[dict] | None
    tool_call_id: str | None
    collection_ids: list[uuid.UUID]
    file_ids: list[uuid.UUID]
    # The same scope with names, to show what a question was about (a file with the collection it comes from).
    collections: list[MessageSourceCollection]
    files: list[MessageSourceFile]
    # Assistant answers only: how it was produced (plan, files consulted, tool calls).
    trace: RunTrace | None = None
    created_at: datetime


class MessagePage(BaseModel):
    # Oldest first. `has_more`: older messages exist (ask again with `before` = the first item's id).
    items: list[MessageOut]
    has_more: bool


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    # The user message this run answers.
    message_id: uuid.UUID
    model: str | None
    status: RunStatus
    # Set once the run is COMPLETED: the assistant message to display.
    result_message_id: uuid.UUID | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class SendMessageOut(BaseModel):
    message: MessageOut
    run: RunOut


class RunContextOut(BaseModel):
    run_id: uuid.UUID
    conversation_id: uuid.UUID
    user_id: str
    requester_email: str | None
    model: str | None
    messages: list[dict]
    collection_ids: list[uuid.UUID]
    file_ids: list[uuid.UUID]


class RunCompleteIn(BaseModel):
    content: str = Field(min_length=1)
    trace: RunTrace | None = None


class RunFailIn(BaseModel):
    error: str


class InternalMessageOut(BaseModel):
    id: uuid.UUID
    role: MessageRole
    content: str | None
    collection_ids: list[uuid.UUID]
    file_ids: list[uuid.UUID]
    created_at: datetime


class ModelOut(BaseModel):
    id: str
    owned_by: str | None


class ModelsOut(BaseModel):
    default: str
    models: list[ModelOut]


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_id: uuid.UUID
    file_version: int
    status: AnalysisStatus
    error: str | None
    created_at: datetime
    updated_at: datetime


class AnalysisResultOut(AnalysisOut):
    # Content of analyse.json (sheets, columns, statistics...); null until the analysis is ready.
    result: dict | None


class AnalysisContextOut(BaseModel):
    analysis_id: uuid.UUID
    file_id: uuid.UUID
    file_name: str
    collection_id: uuid.UUID
    collection_name: str
    file_version: int
    content_type: str | None
    size_bytes: int
    source_key: str
    result_key: str


class AnalysisCompleteIn(BaseModel):
    s3_key: str


class AnalysisFailIn(BaseModel):
    error: str


class ScopeFileOut(BaseModel):
    file_id: uuid.UUID
    file_name: str
    collection_id: uuid.UUID
    collection_name: str
    version: int
    size_bytes: int
    analysis_id: uuid.UUID | None
    analysis_status: AnalysisStatus | None
    # S3 key of analyse.json, set once the analysis is ready.
    result_key: str | None


class AccountFileOut(BaseModel):
    file_id: uuid.UUID
    name: str
    version: int
    size_bytes: int
    uploaded_at: datetime
    analysis_status: AnalysisStatus | None


class AccountCollectionOut(BaseModel):
    collection_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    is_owner: bool
    # Number of people it is shared with (owner only; null for a collection shared with the requester).
    shared_with: int | None
    files: list[AccountFileOut]


class AccountOut(BaseModel):
    collections: list[AccountCollectionOut]
    truncated: bool


class SqlQueryFileIn(BaseModel):
    # The schema name the SQL uses for this file (the agent's reference: f1, f2...).
    ref: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,31}$")
    file_id: uuid.UUID


class SqlQueryIn(BaseModel):
    sql: str = Field(min_length=1, max_length=20_000)
    files: list[SqlQueryFileIn] = Field(min_length=1, max_length=10)


class SqlColumnOut(BaseModel):
    name: str = Field(max_length=500)
    type: str = Field(max_length=100)


class SqlResult(BaseModel):
    """A bounded query result: the worker already cut it, this is the backend's own ceiling."""

    columns: list[SqlColumnOut] = Field(max_length=500)
    rows: list[list] = Field(max_length=500)
    truncated: bool = False


class SqlTableOut(BaseModel):
    # A table as the SQL must name it (f1."Ventes"), with its columns.
    table: str = Field(max_length=600)
    columns: list[SqlColumnOut] = Field(max_length=500)


class SqlQueryFailIn(BaseModel):
    error: str
    tables: list[SqlTableOut] = Field(default=[], max_length=300)


class SqlQueryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    status: SqlQueryStatus
    result: SqlResult | None
    error: str | None
    available_tables: list[SqlTableOut] | None


class SqlQueryContextOut(BaseModel):
    query_id: uuid.UUID
    sql: str
    tables: list[dict]


class AdminAccessEntryOut(BaseModel):
    email: str
    granted_by: str
    created_at: datetime


class AdminCollectionOut(BaseModel):
    collection_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    owner_id: str
    owner_email: str | None
    file_count: int
    shared_with: list[AdminAccessEntryOut]


class AdminPersonCollectionOut(BaseModel):
    collection_id: uuid.UUID
    name: str
    role: str


class AdminPersonOut(BaseModel):
    email: str | None
    user_id: str | None
    collections: list[AdminPersonCollectionOut]


class CollectionAnalysisOut(BaseModel):
    file_id: uuid.UUID
    file_name: str
    collection_name: str
    version: int
    # S3 key of the file's analyse.json (its latest analysis, ready).
    result_key: str


class CollectionAudienceOut(BaseModel):
    collection_id: uuid.UUID
    # null for collections created before owner emails were recorded (until their owner next uses the app)
    owner_email: str | None
    emails: list[str]  # the people it is shared with


class UserCollectionsOut(BaseModel):
    collection_ids: list[uuid.UUID]


class UserIndexRebuildIn(BaseModel):
    email: str = Field(max_length=320)

    @field_validator("email")
    @classmethod
    def _looks_like_an_email(cls, value: str) -> str:
        value = value.strip()
        if "@" not in value[1:-1]:
            raise ValueError("invalid email")
        return value
