import uuid
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.models import ChartStatus
from app.schemas import ChartSpec
from app.services import (
    ChartService,
    ConflictError,
    ConversationService,
    NotFoundError,
    RunService,
    SqlQueryService,
)
from app.services.chart import chart_markdown, chart_url
from app.services.storage import chart_key, conversation_prefix
from tests.actors import ALICE, BOB
from tests.test_sql_query_service import library, running_run  # noqa: F401 - fixtures and helper

SPEC = {"type": "bar", "x": "région", "y": ["total"], "title": "Total par région"}
PNG = b"\x89PNG\r\n\x1a\nfake"


async def completed_query(session, dispatcher, library, run):  # noqa: F811
    queries = SqlQueryService(session, dispatcher)
    query = await queries.create(run.id, 'SELECT 1 AS "n"', {"f1": library.a.id})
    await queries.start(query.id)
    await queries.complete(query.id, {"columns": [{"name": "n", "type": "BIGINT"}], "rows": [[1]], "truncated": False})
    return query


@pytest.fixture
async def drawn(session, dispatcher, storage, library):  # noqa: F811
    """A running run with a completed query, and a service to chart it."""
    run = await running_run(session, dispatcher)
    query = await completed_query(session, dispatcher, library, run)
    return SimpleNamespace(run=run, query=query, charts=ChartService(session, dispatcher, storage))


async def test_a_chart_is_queued_under_the_conversation_and_the_message_the_run_reserved(drawn, dispatcher) -> None:
    chart = await drawn.charts.create(drawn.run.id, drawn.query.id, SPEC)

    assert chart.status == ChartStatus.QUEUED and dispatcher.charts == [chart.id]
    assert chart.message_id == drawn.run.answer_message_id and chart.conversation_id == drawn.run.conversation_id
    assert chart.s3_key == chart_key(chart.conversation_id, chart.message_id, chart.id)
    assert chart.s3_key.endswith(f"/conversations/{chart.conversation_id}/{chart.message_id}/{chart.id}.png")


async def test_the_answer_is_stored_under_the_id_the_run_reserved(session, dispatcher, drawn) -> None:
    await RunService(session, dispatcher).complete(drawn.run.id, "Voici le graphique.")

    messages = await ConversationService(session).history(drawn.run.conversation_id)

    assert messages[-1].id == drawn.run.answer_message_id


async def test_the_markdown_shows_the_image_through_the_backend_and_the_title_cannot_break_it(drawn) -> None:
    chart = await drawn.charts.create(drawn.run.id, drawn.query.id, {**SPEC, "title": "Ventes [2024]\nen €"})

    url = f"/api/conversations/{chart.conversation_id}/messages/{chart.message_id}/charts/{chart.id}"
    assert chart_url(chart) == url
    assert chart_markdown(chart) == f"![Ventes 2024 en €]({url})"


async def test_a_chart_needs_a_successful_query_of_the_same_run(session, dispatcher, storage, library, drawn) -> None:  # noqa: F811
    queries = SqlQueryService(session, dispatcher)
    pending = await queries.create(drawn.run.id, "SELECT 1", {"f1": library.a.id})

    with pytest.raises(ConflictError, match="successful query"):
        await drawn.charts.create(drawn.run.id, pending.id, SPEC)
    with pytest.raises(NotFoundError):
        await drawn.charts.create(drawn.run.id, uuid.uuid4(), SPEC)

    other = await running_run(session, dispatcher)
    with pytest.raises(NotFoundError, match="not a query of this run"):
        await drawn.charts.create(other.id, drawn.query.id, SPEC)


async def test_a_chart_is_only_accepted_while_the_run_is_running(session, dispatcher, drawn) -> None:
    await RunService(session, dispatcher).complete(drawn.run.id, "fini")

    with pytest.raises(ConflictError, match="only accepted while it is running"):
        await drawn.charts.create(drawn.run.id, drawn.query.id, SPEC)
    with pytest.raises(NotFoundError):
        await drawn.charts.create(uuid.uuid4(), drawn.query.id, SPEC)


async def test_an_answer_carries_a_bounded_number_of_charts(drawn, monkeypatch) -> None:
    from app.services import chart as chart_module

    monkeypatch.setattr(chart_module, "MAX_CHARTS_PER_RUN", 2)
    await drawn.charts.create(drawn.run.id, drawn.query.id, SPEC)
    await drawn.charts.create(drawn.run.id, drawn.query.id, SPEC)

    with pytest.raises(ConflictError, match="at most 2 charts"):
        await drawn.charts.create(drawn.run.id, drawn.query.id, SPEC)


async def test_an_unreachable_worker_fails_the_chart_instead_of_hanging(drawn, dispatcher) -> None:
    dispatcher.fail = True

    chart = await drawn.charts.create(drawn.run.id, drawn.query.id, SPEC)

    assert chart.status == ChartStatus.FAILED and "unreachable" in chart.error


async def test_the_worker_gets_the_query_draws_and_reports_where_it_wrote(drawn) -> None:
    chart = await drawn.charts.create(drawn.run.id, drawn.query.id, SPEC)

    found, sql, tables = await drawn.charts.context(chart.id)
    assert (found.id, sql, tables[0]["ref"]) == (chart.id, 'SELECT 1 AS "n"', "f1")
    assert (await drawn.charts.start(chart.id)).status == ChartStatus.RUNNING
    with pytest.raises(ConflictError):
        await drawn.charts.start(chart.id)  # taken
    with pytest.raises(ConflictError, match="Unexpected key"):
        await drawn.charts.complete(chart.id, "elsewhere/x.png", 900, 540)

    done = await drawn.charts.complete(chart.id, chart.s3_key, 900, 540)

    assert (done.status, done.width, done.height) == (ChartStatus.COMPLETED, 900, 540)


async def test_a_failed_chart_keeps_the_columns_of_the_query_and_a_late_report_changes_nothing(drawn) -> None:
    chart = await drawn.charts.create(drawn.run.id, drawn.query.id, SPEC)
    await drawn.charts.start(chart.id)
    columns = [{"name": "n", "type": "BIGINT"}]

    failed = await drawn.charts.fail(chart.id, "Colonne 'région' introuvable", columns)

    assert failed.status == ChartStatus.FAILED and failed.available_columns == columns
    assert (await drawn.charts.fail(chart.id, "again")).error == "Colonne 'région' introuvable"


async def test_only_the_owner_reads_the_image_and_only_under_its_own_message(session, drawn, storage) -> None:
    chart = await drawn.charts.create(drawn.run.id, drawn.query.id, SPEC)
    await drawn.charts.start(chart.id)
    await storage.put_object(chart.s3_key, PNG)
    args = (chart.conversation_id, chart.message_id, chart.id)

    with pytest.raises(NotFoundError):
        await drawn.charts.read_image(ALICE, *args)  # still being drawn

    await drawn.charts.complete(chart.id, chart.s3_key, 900, 540)

    assert await drawn.charts.read_image(ALICE, *args) == PNG
    with pytest.raises(NotFoundError):
        await drawn.charts.read_image(BOB, *args)  # someone else's conversation
    with pytest.raises(NotFoundError):
        await drawn.charts.read_image(ALICE, chart.conversation_id, uuid.uuid4(), chart.id)  # not its message
    with pytest.raises(NotFoundError):
        await drawn.charts.read_image(ALICE, uuid.uuid4(), chart.message_id, chart.id)  # not its conversation


async def test_deleting_a_conversation_deletes_its_charts_from_s3(session, drawn, storage) -> None:
    chart = await drawn.charts.create(drawn.run.id, drawn.query.id, SPEC)
    await storage.put_object(chart.s3_key, PNG)
    await storage.put_object("somewhere/else.png", PNG)
    assert chart.s3_key.startswith(conversation_prefix(chart.conversation_id))

    await ConversationService(session, storage).delete(ALICE, chart.conversation_id)

    assert chart.s3_key not in storage.objects and "somewhere/else.png" in storage.objects


@pytest.mark.parametrize(
    "spec",
    [
        {"type": "bar", "x": "a", "title": "t"},  # no y
        {"type": "pie", "x": "a", "y": ["b", "c"], "title": "t"},
        {"type": "pie", "x": "a", "y": ["b"], "color": "c", "title": "t"},
        {"type": "line", "x": "a", "y": ["b", "c"], "color": "d", "title": "t"},
        {"type": "histogram", "x": "a", "y": ["b"], "title": "t"},
        {"type": "donut", "x": "a", "y": ["b"], "title": "t"},
        {"type": "bar", "x": "a", "y": ["b"], "title": ""},
        {"type": "bar", "x": "a", "y": ["b"] * 7, "title": "t"},
    ],
)
def test_an_inconsistent_chart_spec_is_refused(spec) -> None:
    with pytest.raises(ValidationError):
        ChartSpec(**spec)


@pytest.mark.parametrize(
    "spec",
    [
        {"type": "bar", "x": "a", "y": ["b", "c"], "title": "t", "stacked": True, "sort": "y_desc"},
        {"type": "line", "x": "a", "y": ["b"], "color": "c", "title": "t"},
        {"type": "pie", "x": "a", "y": ["b"], "title": "t"},
        {"type": "histogram", "x": "a", "title": "t"},
        {"type": "scatter", "x": "a", "y": ["b"], "title": "t", "x_label": "X", "y_label": "Y"},
    ],
)
def test_the_chart_kinds_the_agent_can_ask_for(spec) -> None:
    assert ChartSpec(**spec).type == spec["type"]


async def test_regenerating_an_answer_deletes_its_charts(session, dispatcher, storage, drawn) -> None:
    chart = await drawn.charts.create(drawn.run.id, drawn.query.id, SPEC)
    await storage.put_object(chart.s3_key, PNG)
    service = RunService(session, dispatcher, storage)
    await service.complete(drawn.run.id, "Voici le graphique.")

    await service.retry(ALICE, drawn.run.conversation_id)

    assert chart.s3_key not in storage.objects
    with pytest.raises(NotFoundError):
        await drawn.charts.read_image(ALICE, drawn.run.conversation_id, drawn.run.answer_message_id, chart.id)
