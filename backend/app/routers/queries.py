import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, status

from app.dependencies import SqlQueryServiceDep, require_internal_token
from app.schemas import SqlQueryContextOut, SqlQueryFailIn, SqlQueryIn, SqlQueryOut, SqlResult

internal_router = APIRouter(
    prefix="/internal", tags=["Internal (SQL queries)"], dependencies=[Depends(require_internal_token)]
)


@internal_router.post(
    "/runs/{run_id}/queries",
    status_code=status.HTTP_202_ACCEPTED,
    summary="The agent asks for a SQL query over some files of its run (poll GET /queries/{id})",
)
async def create_query(run_id: uuid.UUID, body: SqlQueryIn, service: SqlQueryServiceDep) -> SqlQueryOut:
    files = {item.ref: item.file_id for item in body.files}
    return SqlQueryOut.model_validate(await service.create(run_id, body.sql, files))


@internal_router.get("/queries/{query_id}", summary="State and result of a SQL query")
async def get_query(query_id: uuid.UUID, service: SqlQueryServiceDep) -> SqlQueryOut:
    return SqlQueryOut.model_validate(await service.get(query_id))


@internal_router.get("/queries/{query_id}/context", summary="The SQL and the files a query may read (query worker)")
async def query_context(query_id: uuid.UUID, service: SqlQueryServiceDep) -> SqlQueryContextOut:
    return SqlQueryContextOut(**asdict(await service.context(query_id)))


@internal_router.post("/queries/{query_id}/start", summary="queued -> running (409 if taken or cancelled)")
async def start_query(query_id: uuid.UUID, service: SqlQueryServiceDep) -> SqlQueryOut:
    return SqlQueryOut.model_validate(await service.start(query_id))


@internal_router.post("/queries/{query_id}/complete", summary="Store the result, running -> completed")
async def complete_query(query_id: uuid.UUID, body: SqlResult, service: SqlQueryServiceDep) -> SqlQueryOut:
    return SqlQueryOut.model_validate(await service.complete(query_id, body.model_dump()))


@internal_router.post("/queries/{query_id}/fail", summary="Mark the query failed, with what could have been queried")
async def fail_query(query_id: uuid.UUID, body: SqlQueryFailIn, service: SqlQueryServiceDep) -> SqlQueryOut:
    return SqlQueryOut.model_validate(
        await service.fail(query_id, body.error, [table.model_dump() for table in body.tables])
    )
