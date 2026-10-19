import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import get_session
from app.dependencies import get_dispatcher, get_model_catalog, get_storage
from app.main import app
from app.repositories import CollectionRepository
from app.services import (
    AdminService,
    AnalysisService,
    CollectionService,
    ConflictError,
    ConversationService,
    EphemeralService,
    InvalidRequestError,
    NotFoundError,
    RunService,
)
from tests.actors import ALICE, BOB

CSV = ("ventes.csv", b"region,total\nNord,10\nSud,20\n", "text/csv")
OTHER = ("stock.csv", b"produit,qte\nA,1\n", "text/csv")


@pytest.fixture
def service(session, storage, dispatcher) -> EphemeralService:
    return EphemeralService(session, storage, dispatcher)


async def _finish(session, storage, dispatcher, analysis_id: uuid.UUID, fail: bool = False) -> None:
    """What the analysis worker does for every file of the ephemeral analysis."""
    analyses = AnalysisService(session, storage, dispatcher)
    files = await EphemeralService(session, storage, dispatcher).files.files.list_by_collection(analysis_id)
    latest = await analyses.latest_by_file([f.id for f in files])
    for analysis in latest.values():
        await analyses.start(analysis.id)
        if fail:
            await analyses.fail(analysis.id, "unreadable")
        else:
            context = await analyses.context(analysis.id)
            await storage.put_json(context.result_key, {"sheets": []})
            await analyses.complete(analysis.id, context.result_key)


async def test_files_are_stored_and_pre_analysed_and_the_collection_stays_hidden(
    session, storage, dispatcher, service
) -> None:
    created = await service.create(ALICE, [CSV, OTHER])

    assert created.status == "processing" and len(created.files) == 2
    assert {f.status.value for f in created.files} == {"pending"}
    assert len(dispatcher.analyses) == 2  # the pre-analysis of each file was queued
    delta = created.expires_at - datetime.now(UTC)
    assert timedelta(hours=23) < delta <= timedelta(hours=24)
    # Nobody lists it: not the owner, not the administrators, not the search of the account.
    assert await CollectionService(session, storage).list_for_user(ALICE) == []
    assert created.id not in [c.collection_id for c in await AdminService(session).collection_access()]
    assert await CollectionRepository(session).ids_readable_by_email(ALICE.email) == []


async def test_the_state_follows_the_pre_analysis(session, storage, dispatcher, service) -> None:
    created = await service.create(ALICE, [CSV])

    await _finish(session, storage, dispatcher, created.id)

    ready = await service.get(ALICE, created.id)
    assert ready.status == "ready" and [f.status.value for f in ready.files] == ["ready"]
    assert dispatcher.indexed == []  # it is not added to any search index


async def test_the_input_is_checked(service) -> None:
    with pytest.raises(InvalidRequestError):
        await service.create(ALICE, [])
    with pytest.raises(InvalidRequestError):
        await service.create(ALICE, [CSV], ttl_hours=0)
    with pytest.raises(InvalidRequestError):
        await service.create(ALICE, [CSV], ttl_hours=24 * 365)
    with pytest.raises(InvalidRequestError):
        await service.create(ALICE, [(f"f{i}.csv", b"a\n1\n" + bytes([i]), None) for i in range(21)])


async def test_a_run_waits_for_the_pre_analysis_then_answers_about_the_files(
    session, storage, dispatcher, service
) -> None:
    created = await service.create(ALICE, [CSV], ttl_hours=2)
    with pytest.raises(ConflictError):
        await service.start_run(ALICE, created.id, "Total ?")

    await _finish(session, storage, dispatcher, created.id)
    before = (await service.get(ALICE, created.id)).expires_at
    run = await service.start_run(ALICE, created.id, "Total par région ?", default_model="m")

    assert run.model == "m" and dispatcher.enqueued == [run.id]
    context = await RunService(session, dispatcher).context(run.id)
    assert context.collection_ids == [created.id]  # the question is about these files only
    assert (await service.get(ALICE, created.id)).expires_at >= before
    # The conversation of the analysis is not one of the person's conversations.
    assert await ConversationService(session).list_for_user(ALICE) == []

    pending = await service.get_run(ALICE, run.id)
    assert pending.answer is None and pending.analysis_id == created.id
    runs = RunService(session, dispatcher)
    await runs.start(run.id)
    await runs.complete(run.id, "Le Sud : 20.")
    done = await service.get_run(ALICE, run.id)
    assert (done.run.status.value, done.answer.content) == ("completed", "Le Sud : 20.")


async def test_nothing_can_be_asked_when_no_file_could_be_analysed(session, storage, dispatcher, service) -> None:
    created = await service.create(ALICE, [CSV])
    await _finish(session, storage, dispatcher, created.id, fail=True)

    assert (await service.get(ALICE, created.id)).status == "failed"
    with pytest.raises(InvalidRequestError):
        await service.start_run(ALICE, created.id, "Total ?")


async def test_it_is_private_to_its_creator_and_is_not_a_chat(session, storage, dispatcher, service) -> None:
    created = await service.create(ALICE, [CSV])
    await _finish(session, storage, dispatcher, created.id)
    run = await service.start_run(ALICE, created.id, "Total ?")

    for call in (
        service.get(BOB, created.id),
        service.start_run(BOB, created.id, "x"),
        service.get_run(BOB, run.id),
        service.delete(BOB, created.id),
    ):
        with pytest.raises(NotFoundError):
            await call
    # A normal collection and a run of the chat are not ephemeral analyses.
    normal = await CollectionService(session, storage).create(ALICE, "Sales")
    with pytest.raises(NotFoundError):
        await service.get(ALICE, normal.id)
    chat = await ConversationService(session).create(ALICE)
    _, chat_run = await RunService(session, dispatcher).send_message(ALICE, chat.id, "hi")
    with pytest.raises(NotFoundError):
        await service.get_run(ALICE, chat_run.id)


async def test_deleting_removes_everything_now(session, storage, dispatcher, service) -> None:
    created = await service.create(ALICE, [CSV])
    await _finish(session, storage, dispatcher, created.id)
    await service.start_run(ALICE, created.id, "Total ?")
    assert any(str(created.id) in key for key in storage.objects)

    await service.delete(ALICE, created.id)

    assert not any(str(created.id) in key for key in storage.objects)
    assert await CollectionRepository(session).get(created.id) is None
    with pytest.raises(NotFoundError):
        await service.get(ALICE, created.id)


async def test_expired_analyses_are_purged_and_the_others_kept(session, storage, dispatcher, service) -> None:
    old = await service.create(ALICE, [CSV])
    recent = await service.create(ALICE, [OTHER])
    (await CollectionRepository(session).get(old.id)).expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await session.commit()

    assert await service.purge_expired() == 1

    assert await CollectionRepository(session).get(old.id) is None
    assert not any(str(old.id) in key for key in storage.objects)
    assert (await service.get(ALICE, recent.id)).id == recent.id


# --- routes ---


@pytest.fixture
async def api(session, storage, dispatcher, catalog):
    from app.dependencies import get_actor
    from app.services import Actor

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_dispatcher] = lambda: dispatcher
    app.dependency_overrides[get_model_catalog] = lambda: catalog
    app.dependency_overrides[get_actor] = lambda: Actor(user_id=ALICE.user_id, email=ALICE.email)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def test_upload_pre_analysis_run_and_answer_over_http(api, session, storage, dispatcher) -> None:
    created = await api.post(
        "/api/ephemeral/analyses",
        files=[("files", CSV), ("files", OTHER)],
        data={"ttl_hours": "3"},
    )
    assert created.status_code == 202
    analysis = created.json()
    assert analysis["status"] == "processing" and len(analysis["files"]) == 2

    early = await api.post(f"/api/ephemeral/analyses/{analysis['id']}/runs", json={"query": "Total ?"})
    assert early.status_code == 409

    await _finish(session, storage, dispatcher, uuid.UUID(analysis["id"]))
    assert (await api.get(f"/api/ephemeral/analyses/{analysis['id']}")).json()["status"] == "ready"

    started = await api.post(f"/api/ephemeral/analyses/{analysis['id']}/runs", json={"query": "Total par région ?"})
    assert started.status_code == 202
    run_id = started.json()["id"]
    waiting = (await api.get(f"/api/ephemeral/runs/{run_id}")).json()
    assert (waiting["status"], waiting["answer"], waiting["analysis_id"]) == ("queued", None, analysis["id"])

    runs = RunService(session, dispatcher)
    await runs.start(uuid.UUID(run_id))
    await runs.complete(uuid.UUID(run_id), "Le Sud : 20.")
    answered = (await api.get(f"/api/ephemeral/runs/{run_id}")).json()
    assert (answered["status"], answered["answer"]) == ("completed", "Le Sud : 20.")

    assert (await api.delete(f"/api/ephemeral/analyses/{analysis['id']}")).status_code == 204
    assert (await api.get(f"/api/ephemeral/analyses/{analysis['id']}")).status_code == 404


async def test_upload_is_validated_over_http(api) -> None:
    bad_type = await api.post("/api/ephemeral/analyses", files=[("files", ("notes.txt", b"x", "text/plain"))])
    assert bad_type.status_code == 415
    assert (await api.post("/api/ephemeral/analyses", files=[])).status_code == 422
    too_long = await api.post("/api/ephemeral/analyses", files=[("files", CSV)], data={"ttl_hours": "100000"})
    assert too_long.status_code == 422
    assert (await api.post("/api/ephemeral/analyses/not-a-uuid/runs", json={"query": "x"})).status_code == 422


async def test_the_charts_of_a_run_are_read_through_the_run(api, session, storage, dispatcher) -> None:
    from app.dependencies import get_actor
    from app.services import Actor, ChartService, SqlQueryService
    from app.services.chart import chart_markdown

    created = (await api.post("/api/ephemeral/analyses", files=[("files", CSV)])).json()
    await _finish(session, storage, dispatcher, uuid.UUID(created["id"]))
    run_id = uuid.UUID(
        (await api.post(f"/api/ephemeral/analyses/{created['id']}/runs", json={"query": "Un graphique"})).json()["id"]
    )
    runs = RunService(session, dispatcher)
    await runs.start(run_id)
    file_id = uuid.UUID(created["files"][0]["id"])
    queries = SqlQueryService(session, dispatcher)
    query = await queries.create(run_id, 'SELECT 1 AS "n"', {"f1": file_id})
    await queries.start(query.id)
    await queries.complete(query.id, {"columns": [{"name": "n", "type": "BIGINT"}], "rows": [[1]], "truncated": False})
    charts = ChartService(session, dispatcher, storage)
    chart = await charts.create(
        run_id, query.id, {"type": "bar", "x": "région", "y": ["total"], "title": "Total par région"}
    )
    await charts.start(chart.id)
    await storage.put_object(chart.s3_key, b"\x89PNG\r\n\x1a\nfake")
    await charts.complete(chart.id, chart.s3_key, 640, 480)
    await runs.complete(run_id, f"Voici le total.\n\n{chart_markdown(chart)}")

    run = (await api.get(f"/api/ephemeral/runs/{run_id}")).json()

    url = f"/api/ephemeral/runs/{run_id}/charts/{chart.id}"
    assert [(c["id"], c["title"], c["status"], c["url"]) for c in run["charts"]] == [
        (str(chart.id), "Total par région", "completed", url)
    ]
    assert url in run["answer"] and "/api/conversations/" not in run["answer"]  # the answer points to the run's route
    image = await api.get(url)
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"
    assert image.content == b"\x89PNG\r\n\x1a\nfake"
    unknown = "00000000-0000-0000-0000-000000000000"
    assert (await api.get(f"/api/ephemeral/runs/{run_id}/charts/{unknown}")).status_code == 404

    app.dependency_overrides[get_actor] = lambda: Actor(user_id=BOB.user_id, email=BOB.email)
    assert (await api.get(url)).status_code == 404
