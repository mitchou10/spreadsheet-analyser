import pytest

from app.services import ConversationService, RunService
from app.services.usage import UsageService
from tests.actors import ALICE, BOB


def call(node: str, input_tokens: int, output_tokens: int) -> dict:
    return {
        "node": node,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


async def answer(session, dispatcher, storage, actor, calls: list[dict] | None) -> None:
    conversation = await ConversationService(session).create(actor)
    service = RunService(session, dispatcher, storage)
    _, run = await service.send_message(actor, conversation.id, "Résume")
    await service.start(run.id)
    if calls is not None:
        await service.record_usage(run.id, calls)
    await service.complete(run.id, "done")


@pytest.fixture
async def usage(session, dispatcher, storage) -> UsageService:
    await answer(session, dispatcher, storage, ALICE, [call("plan", 100, 10), call("agent", 300, 30)])
    await answer(session, dispatcher, storage, ALICE, [call("plan", 50, 5)])
    await answer(session, dispatcher, storage, BOB, [call("agent", 1000, 100)])
    await answer(session, dispatcher, storage, BOB, None)
    return UsageService(session)


async def test_my_usage_only_counts_my_runs_and_splits_them_by_node(usage) -> None:
    report = await usage.mine(ALICE, 30)

    assert (report.totals.input_tokens, report.totals.output_tokens, report.totals.calls) == (450, 45, 3)
    assert {n.node: n.total_tokens for n in report.by_node} == {"plan": 165, "agent": 330}
    assert report.by_user == []  # who else consumed is for the administrators


async def test_the_administrator_sees_everyone_and_where_it_consumes_the_most(usage) -> None:
    report = await usage.overall(30)

    assert report.totals.total_tokens == 495 + 1100
    assert [n.node for n in report.by_node] == ["agent", "plan"]  # biggest first
    assert [(u.user_id, u.total_tokens) for u in report.by_user] == [(BOB.user_id, 1100), (ALICE.user_id, 495)]
    assert sum(d.total_tokens for d in report.by_day) == report.totals.total_tokens


async def test_the_administrator_can_look_at_one_person(usage) -> None:
    report = await usage.overall(30, ALICE.user_id)

    assert report.totals.total_tokens == 495
    assert {n.node for n in report.by_node} == {"plan", "agent"}


async def test_a_run_without_usage_stores_nothing(session, dispatcher, storage) -> None:
    await answer(session, dispatcher, storage, ALICE, None)

    assert (await UsageService(session).mine(ALICE, 30)).totals.calls == 0


async def test_a_failed_or_cancelled_run_keeps_the_tokens_it_spent(session, dispatcher, storage) -> None:
    service = RunService(session, dispatcher, storage)
    failed = await ConversationService(session).create(ALICE)
    _, run = await service.send_message(ALICE, failed.id, "Q")
    await service.start(run.id)
    await service.record_usage(run.id, [call("plan", 100, 10)])
    await service.fail(run.id, "boom")
    cancelled = await ConversationService(session).create(ALICE)
    _, run2 = await service.send_message(ALICE, cancelled.id, "Q")
    await service.start(run2.id)
    await service.cancel(ALICE, run2.id)
    await service.record_usage(run2.id, [call("plan", 5, 5)])

    assert (await UsageService(session).mine(ALICE, 30)).totals.total_tokens == 120


async def test_reporting_a_run_again_replaces_its_previous_report(session, dispatcher, storage) -> None:
    service = RunService(session, dispatcher, storage)
    conversation = await ConversationService(session).create(ALICE)
    _, run = await service.send_message(ALICE, conversation.id, "Q")

    await service.record_usage(run.id, [call("plan", 100, 10)])
    await service.record_usage(run.id, [call("plan", 100, 10), call("agent", 200, 20)])

    report = await UsageService(session).mine(ALICE, 30)
    assert (report.totals.calls, report.totals.total_tokens) == (2, 330)


async def test_the_worker_reports_usage_over_http(session, dispatcher, storage) -> None:
    from httpx import ASGITransport, AsyncClient

    from app.dependencies import get_dispatcher, get_session, get_storage, require_internal_token
    from app.main import app

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_dispatcher] = lambda: dispatcher
    app.dependency_overrides[require_internal_token] = lambda: None
    try:
        conversation = await ConversationService(session).create(ALICE)
        _, run = await RunService(session, dispatcher, storage).send_message(ALICE, conversation.id, "Q")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as api:
            reply = await api.post(f"/api/internal/runs/{run.id}/usage", json={"calls": [call("plan", 1, 2)]})
    finally:
        app.dependency_overrides.clear()

    assert reply.status_code == 204
    assert (await UsageService(session).mine(ALICE, 30)).totals.total_tokens == 3
