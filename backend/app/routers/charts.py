import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies import ChartServiceDep, require_internal_token
from app.models import Chart
from app.schemas import ChartCompleteIn, ChartContextOut, ChartFailIn, ChartIn, ChartOut
from app.services.chart import chart_markdown, chart_url

internal_router = APIRouter(
    prefix="/internal", tags=["Internal (charts)"], dependencies=[Depends(require_internal_token)]
)


def chart_out(chart: Chart) -> ChartOut:
    return ChartOut(
        id=chart.id,
        status=chart.status,
        title=chart.title,
        error=chart.error,
        available_columns=chart.available_columns,
        width=chart.width,
        height=chart.height,
        url=chart_url(chart),
        markdown=chart_markdown(chart),
    )


@internal_router.post(
    "/runs/{run_id}/charts",
    status_code=status.HTTP_202_ACCEPTED,
    summary="The agent asks for a chart of the result of a query of its run (poll GET /charts/{id})",
)
async def create_chart(run_id: uuid.UUID, body: ChartIn, service: ChartServiceDep) -> ChartOut:
    return chart_out(await service.create(run_id, body.query_id, body.spec.model_dump()))


@internal_router.get("/charts/{chart_id}", summary="State of a chart, and the markdown that shows it")
async def get_chart(chart_id: uuid.UUID, service: ChartServiceDep) -> ChartOut:
    return chart_out(await service.get(chart_id))


@internal_router.get("/charts/{chart_id}/context", summary="What to draw, from which query, and where to write it")
async def chart_context(chart_id: uuid.UUID, service: ChartServiceDep) -> ChartContextOut:
    chart, sql, tables = await service.context(chart_id)
    return ChartContextOut(chart_id=chart.id, spec=chart.spec, sql=sql, tables=tables, s3_key=chart.s3_key)


@internal_router.post("/charts/{chart_id}/start", summary="queued -> running (409 if taken)")
async def start_chart(chart_id: uuid.UUID, service: ChartServiceDep) -> ChartOut:
    return chart_out(await service.start(chart_id))


@internal_router.post("/charts/{chart_id}/complete", summary="The PNG is written: running -> completed")
async def complete_chart(chart_id: uuid.UUID, body: ChartCompleteIn, service: ChartServiceDep) -> ChartOut:
    return chart_out(await service.complete(chart_id, body.s3_key, body.width, body.height))


@internal_router.post("/charts/{chart_id}/fail", summary="Mark the chart failed, with the columns of the query")
async def fail_chart(chart_id: uuid.UUID, body: ChartFailIn, service: ChartServiceDep) -> ChartOut:
    return chart_out(await service.fail(chart_id, body.error, [column.model_dump() for column in body.columns]))
