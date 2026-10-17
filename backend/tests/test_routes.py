import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import get_session
from app.dependencies import get_actor, get_dispatcher, get_model_catalog, get_storage
from app.main import app
from app.services import Actor
from tests.actors import BOB


@pytest.fixture
async def client(session, storage, dispatcher, catalog) -> AsyncIterator[AsyncClient]:
    """API client as the full-access dev user (dev-user / dev@example.com), on the rolled-back test
    session and the in-memory storage."""
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_dispatcher] = lambda: dispatcher
    app.dependency_overrides[get_model_catalog] = lambda: catalog
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()


async def _create(client: AsyncClient, name: str = "Sales") -> dict:
    response = await client.post("/api/collections", json={"name": name, "description": "d"})
    assert response.status_code == 201
    return response.json()


def _xlsx(name: str = "a.xlsx", content: bytes = b"data") -> list:
    return [("files", (name, content, "application/octet-stream"))]


async def test_create_and_list_collections(client) -> None:
    created = await _create(client)

    assert created["name"] == "Sales"
    assert created["is_owner"] is True
    assert created["file_count"] == 0
    listed = (await client.get("/api/collections")).json()
    assert [c["id"] for c in listed] == [created["id"]]


async def test_create_collection_validates_name(client) -> None:
    assert (await client.post("/api/collections", json={"name": ""})).status_code == 422


async def test_unknown_collection_is_404(client) -> None:
    assert (await client.get("/api/collections/00000000-0000-0000-0000-000000000000")).status_code == 404


async def test_upload_multiple_files_queues_analysis_and_updates_count(client, storage) -> None:
    collection = await _create(client)

    response = await client.post(
        f"/api/collections/{collection['id']}/files",
        files=[
            ("files", ("a.xlsx", b"1", "application/octet-stream")),
            ("files", ("b.csv", b"2", "text/csv")),
        ],
    )

    assert response.status_code == 201
    body = response.json()
    assert [f["name"] for f in body] == ["a.xlsx", "b.csv"]
    assert {f["status"] for f in body} == {"pending"}
    assert body[0]["size_bytes"] == 1
    assert any(key.endswith("/versions/1/a.xlsx") for key in storage.objects)
    listed = (await client.get(f"/api/collections/{collection['id']}/files")).json()
    assert len(listed) == 2
    assert (await client.get(f"/api/collections/{collection['id']}")).json()["file_count"] == 2


async def test_reupload_same_content_is_noop_and_new_content_bumps_version(client) -> None:
    collection = await _create(client)
    url = f"/api/collections/{collection['id']}/files"

    first = (await client.post(url, files=_xlsx())).json()[0]
    again = (await client.post(url, files=_xlsx())).json()[0]
    changed = (await client.post(url, files=_xlsx(content=b"new"))).json()[0]

    assert again["id"] == first["id"] and again["version"] == 1
    assert changed["id"] == first["id"] and changed["version"] == 2
    assert len((await client.get(url)).json()) == 1


async def test_upload_rejects_unsupported_extension_and_oversize(client, monkeypatch) -> None:
    collection = await _create(client)
    url = f"/api/collections/{collection['id']}/files"

    assert (await client.post(url, files=_xlsx("evil.exe"))).status_code == 415

    monkeypatch.setattr("app.routers.collections._settings.MAX_UPLOAD_BYTES", 3)
    assert (await client.post(url, files=_xlsx(content=b"toolong"))).status_code == 413
    assert (await client.get(url)).json() == []


async def test_upload_without_files_is_422(client) -> None:
    collection = await _create(client)
    assert (await client.post(f"/api/collections/{collection['id']}/files")).status_code == 422


async def test_download_and_delete_file(client, storage) -> None:
    collection = await _create(client)
    file = (await client.post(f"/api/collections/{collection['id']}/files", files=_xlsx(content=b"abc"))).json()[0]

    download = await client.get(f"/api/files/{file['id']}/download")
    assert download.status_code == 200
    assert download.content == b"abc"
    assert "a.xlsx" in download.headers["content-disposition"]

    assert (await client.delete(f"/api/files/{file['id']}")).status_code == 204
    assert (await client.get(f"/api/files/{file['id']}/download")).status_code == 404
    assert storage.objects == {}


async def test_retry_and_stop_analysis(client) -> None:
    collection = await _create(client)
    file = (await client.post(f"/api/collections/{collection['id']}/files", files=_xlsx())).json()[0]

    stopped = await client.post(f"/api/files/{file['id']}/analysis/stop")
    assert stopped.json()["status"] == "stopped"

    retried = await client.post(f"/api/files/{file['id']}/analysis")
    assert retried.status_code == 202
    assert retried.json()["status"] == "pending"


async def test_delete_collection(client, storage) -> None:
    collection = await _create(client)
    await client.post(f"/api/collections/{collection['id']}/files", files=_xlsx())

    assert (await client.delete(f"/api/collections/{collection['id']}")).status_code == 204
    assert (await client.get("/api/collections")).json() == []
    assert storage.objects == {}


async def test_share_flow_and_read_only_for_shared_user(client) -> None:
    collection = await _create(client)
    base = f"/api/collections/{collection['id']}"
    file = (await client.post(f"{base}/files", files=_xlsx())).json()[0]

    shared = await client.post(f"{base}/access", json={"email": " Bob@Example.com "})
    assert shared.status_code == 201
    assert shared.json()["email"] == "bob@example.com"
    assert (await client.post(f"{base}/access", json={"email": "not-an-email"})).status_code == 422
    assert [a["email"] for a in (await client.get(f"{base}/access")).json()] == ["bob@example.com"]

    app.dependency_overrides[get_actor] = lambda: Actor(user_id=BOB.user_id, email=BOB.email)
    listed = (await client.get("/api/collections")).json()
    assert [(c["id"], c["is_owner"]) for c in listed] == [(collection["id"], False)]
    assert (await client.get(f"{base}/files")).status_code == 200
    assert (await client.get(f"/api/files/{file['id']}/download")).status_code == 200
    assert (await client.post(f"{base}/files", files=_xlsx("b.xlsx"))).status_code == 403
    assert (await client.delete(f"/api/files/{file['id']}")).status_code == 403
    assert (await client.delete(base)).status_code == 403
    assert (await client.get(f"{base}/access")).status_code == 403

    del app.dependency_overrides[get_actor]
    assert (await client.delete(f"{base}/access/bob@example.com")).status_code == 204
    app.dependency_overrides[get_actor] = lambda: Actor(user_id=BOB.user_id, email=BOB.email)
    assert (await client.get(base)).status_code == 404


async def test_conversation_flow(client) -> None:
    created = await client.post("/api/conversations", json={})
    assert created.status_code == 201
    conversation = created.json()
    assert conversation["title"] == "Nouvelle conversation"

    collection = await _create(client)
    sent = await client.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"content": "Résume ce fichier", "collection_ids": [collection["id"]]},
    )
    assert sent.status_code == 202
    assert sent.json()["message"]["role"] == "user"
    assert sent.json()["message"]["collection_ids"] == [collection["id"]]
    assert sent.json()["run"]["status"] == "queued"

    messages = (await client.get(f"/api/conversations/{conversation['id']}/messages")).json()
    assert [m["content"] for m in messages] == ["Résume ce fichier"]
    listed = (await client.get("/api/conversations")).json()
    assert [(c["id"], c["title"]) for c in listed] == [(conversation["id"], "Résume ce fichier")]

    assert (await client.delete(f"/api/conversations/{conversation['id']}")).status_code == 204
    assert (await client.get(f"/api/conversations/{conversation['id']}/messages")).status_code == 404
    assert (await client.get("/api/conversations")).json() == []


async def test_send_message_validation_and_privacy(client) -> None:
    conversation = (await client.post("/api/conversations", json={})).json()
    url = f"/api/conversations/{conversation['id']}/messages"

    assert (await client.post(url, json={"content": ""})).status_code == 422
    unknown = "00000000-0000-0000-0000-000000000000"
    assert (await client.post(url, json={"content": "x", "file_ids": [unknown]})).status_code == 404

    app.dependency_overrides[get_actor] = lambda: Actor(user_id=BOB.user_id, email=BOB.email)
    assert (await client.get(url)).status_code == 404
    assert (await client.post(url, json={"content": "x"})).status_code == 404
    assert (await client.delete(f"/api/conversations/{conversation['id']}")).status_code == 404
    assert (await client.get("/api/conversations")).json() == []


async def _send(client, conversation_id: str, content: str = "q") -> dict:
    response = await client.post(f"/api/conversations/{conversation_id}/messages", json={"content": content})
    return response


async def test_run_flow_through_internal_api(client, dispatcher, monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    worker = {"Authorization": "Bearer secret"}
    conversation = (await client.post("/api/conversations", json={})).json()

    sent = await _send(client, conversation["id"], "Résume")
    run = sent.json()["run"]
    assert sent.status_code == 202 and run["status"] == "queued"
    assert dispatcher.enqueued == [uuid.UUID(run["id"])]

    active = await client.get(f"/api/conversations/{conversation['id']}/active-run")
    assert active.json()["id"] == run["id"]
    assert (await _send(client, conversation["id"], "again")).status_code == 409

    context = await client.get(f"/api/internal/runs/{run['id']}/context", headers=worker)
    assert context.json()["messages"] == [{"role": "user", "content": "Résume"}]
    assert (await client.post(f"/api/internal/runs/{run['id']}/start", headers=worker)).json()["status"] == "running"
    assert (await client.get(f"/api/runs/{run['id']}")).json()["status"] == "running"

    done = await client.post(f"/api/internal/runs/{run['id']}/complete", json={"content": "Réponse"}, headers=worker)
    assert done.json()["status"] == "completed"
    assert done.json()["result_message_id"]

    messages = (await client.get(f"/api/conversations/{conversation['id']}/messages")).json()
    assert [(m["role"], m["content"]) for m in messages] == [("user", "Résume"), ("assistant", "Réponse")]
    assert (await client.get(f"/api/conversations/{conversation['id']}/active-run")).json() is None


async def test_cancel_run_route_and_worker_conflict(client, monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    worker = {"Authorization": "Bearer secret"}
    conversation = (await client.post("/api/conversations", json={})).json()
    run = (await _send(client, conversation["id"])).json()["run"]

    cancelled = await client.post(f"/api/runs/{run['id']}/cancel")

    assert cancelled.json()["status"] == "cancelled"
    assert (await client.post(f"/api/internal/runs/{run['id']}/start", headers=worker)).status_code == 409


async def test_internal_api_requires_the_token(client, monkeypatch) -> None:
    run_id = "00000000-0000-0000-0000-000000000000"

    monkeypatch.delenv("INTERNAL_API_TOKEN", raising=False)
    assert (await client.post(f"/api/internal/runs/{run_id}/start")).status_code == 503

    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    assert (await client.post(f"/api/internal/runs/{run_id}/start")).status_code == 401
    wrong = await client.post(f"/api/internal/runs/{run_id}/start", headers={"Authorization": "Bearer nope"})
    assert wrong.status_code == 401
    right = await client.post(f"/api/internal/runs/{run_id}/start", headers={"Authorization": "Bearer secret"})
    assert right.status_code == 404


async def test_runs_are_private_over_http(client) -> None:
    conversation = (await client.post("/api/conversations", json={})).json()
    run = (await _send(client, conversation["id"])).json()["run"]

    app.dependency_overrides[get_actor] = lambda: Actor(user_id=BOB.user_id, email=BOB.email)

    assert (await client.get(f"/api/runs/{run['id']}")).status_code == 404
    assert (await client.post(f"/api/runs/{run['id']}/cancel")).status_code == 404
    assert (await client.get(f"/api/conversations/{conversation['id']}/active-run")).status_code == 404


async def test_internal_history_exposes_messages_with_scope(client, monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    collection = await _create(client)
    conversation = (await client.post("/api/conversations", json={})).json()
    await client.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"content": "Résume", "collection_ids": [collection["id"]]},
    )
    url = f"/api/internal/conversations/{conversation['id']}/messages"

    assert (await client.get(url)).status_code == 401
    history = (await client.get(url, headers={"Authorization": "Bearer secret"})).json()

    assert [(m["role"], m["content"], m["collection_ids"]) for m in history] == [("user", "Résume", [collection["id"]])]
    missing = "/api/internal/conversations/00000000-0000-0000-0000-000000000000/messages"
    assert (await client.get(missing, headers={"Authorization": "Bearer secret"})).status_code == 404


async def test_list_models(client, catalog) -> None:
    response = await client.get("/api/models")

    assert response.status_code == 200
    assert response.json() == {
        "default": "gpt-test",
        "models": [{"id": "gpt-test", "owned_by": "openai"}, {"id": "other-model", "owned_by": "acme"}],
    }

    catalog.down = True
    assert (await client.get("/api/models")).status_code == 502


async def test_send_message_with_a_model(client) -> None:
    conversation = (await client.post("/api/conversations", json={})).json()
    url = f"/api/conversations/{conversation['id']}/messages"

    picked = await client.post(url, json={"content": "q", "model": "other-model"})
    assert picked.status_code == 202 and picked.json()["run"]["model"] == "other-model"
    await client.post(f"/api/runs/{picked.json()['run']['id']}/cancel")

    # The pick sticks to the conversation: later messages keep using it without repeating it.
    sticky = await client.post(url, json={"content": "q2"})
    assert sticky.json()["run"]["model"] == "other-model"
    await client.post(f"/api/runs/{sticky.json()['run']['id']}/cancel")

    unknown = await client.post(url, json={"content": "q3", "model": "nope"})
    assert unknown.status_code == 422 and "nope" in unknown.json()["detail"]
    assert len((await client.get(url)).json()) == 2  # the rejected message was not stored
    assert (await client.get("/api/conversations")).json()[0]["model"] == "other-model"


async def test_send_message_with_a_model_when_provider_is_down(client, catalog) -> None:
    conversation = (await client.post("/api/conversations", json={})).json()
    catalog.down = True
    url = f"/api/conversations/{conversation['id']}/messages"

    assert (await client.post(url, json={"content": "q", "model": "gpt-test"})).status_code == 502
    assert (await client.post(url, json={"content": "q"})).status_code == 202  # default needs no provider call


async def test_run_context_carries_the_model(client, monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    conversation = (await client.post("/api/conversations", json={})).json()
    run = (
        await client.post(
            f"/api/conversations/{conversation['id']}/messages", json={"content": "q", "model": "other-model"}
        )
    ).json()["run"]

    context = await client.get(f"/api/internal/runs/{run['id']}/context", headers={"Authorization": "Bearer secret"})

    assert context.json()["model"] == "other-model"


async def test_conversation_model_lifecycle(client, monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    worker = {"Authorization": "Bearer secret"}

    plain = (await client.post("/api/conversations", json={})).json()
    assert plain["model"] is None
    first = (await client.post(f"/api/conversations/{plain['id']}/messages", json={"content": "a"})).json()["run"]
    assert first["model"] == "gpt-test"  # no model on the conversation: the default
    await client.post(f"/api/runs/{first['id']}/cancel")

    created = await client.post("/api/conversations", json={"model": "other-model"})
    assert created.status_code == 201 and created.json()["model"] == "other-model"
    conversation = created.json()

    run = (await client.post(f"/api/conversations/{conversation['id']}/messages", json={"content": "q"})).json()["run"]
    assert run["model"] == "other-model"
    context = await client.get(f"/api/internal/runs/{run['id']}/context", headers=worker)
    assert context.json()["model"] == "other-model"  # what the worker will call
    await client.post(f"/api/runs/{run['id']}/cancel")

    patched = await client.patch(
        f"/api/conversations/{conversation['id']}", json={"model": "gpt-test", "title": "Ventes"}
    )
    assert (patched.json()["model"], patched.json()["title"]) == ("gpt-test", "Ventes")
    after = (await client.post(f"/api/conversations/{conversation['id']}/messages", json={"content": "q2"})).json()
    assert after["run"]["model"] == "gpt-test"


async def test_conversation_model_is_validated_on_create_and_patch(client, catalog) -> None:
    assert (await client.post("/api/conversations", json={"model": "nope"})).status_code == 422
    conversation = (await client.post("/api/conversations", json={})).json()
    url = f"/api/conversations/{conversation['id']}"

    assert (await client.patch(url, json={"model": "nope"})).status_code == 422
    assert (await client.patch(url, json={"model": ""})).status_code == 422
    assert (await client.patch(url, json={"title": "Renamed"})).json()["title"] == "Renamed"

    catalog.down = True
    assert (await client.patch(url, json={"model": "gpt-test"})).status_code == 502


async def test_patch_conversation_is_private(client) -> None:
    conversation = (await client.post("/api/conversations", json={})).json()
    app.dependency_overrides[get_actor] = lambda: Actor(user_id=BOB.user_id, email=BOB.email)

    assert (await client.patch(f"/api/conversations/{conversation['id']}", json={"title": "x"})).status_code == 404


async def test_model_can_be_sent_with_every_message(client) -> None:
    conversation = (await client.post("/api/conversations", json={})).json()
    url = f"/api/conversations/{conversation['id']}/messages"
    used = []

    for model in ("gpt-test", "other-model", "gpt-test"):
        run = (await client.post(url, json={"content": "q", "model": model})).json()["run"]
        used.append(run["model"])
        await client.post(f"/api/runs/{run['id']}/cancel")

    assert used == ["gpt-test", "other-model", "gpt-test"]
    assert (await client.get("/api/conversations")).json()[0]["model"] == "gpt-test"


async def test_upload_queues_the_analysis_and_exposes_its_result(client, dispatcher, storage, monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    worker = {"Authorization": "Bearer secret"}
    collection = await _create(client)
    file = (await client.post(f"/api/collections/{collection['id']}/files", files=_xlsx())).json()[0]

    pending = (await client.get(f"/api/files/{file['id']}/analysis")).json()
    assert (pending["status"], pending["result"]) == ("pending", None)
    analysis_id = pending["id"]
    assert dispatcher.analyses == [uuid.UUID(analysis_id)]

    # What the analysis worker does: read the context, start, write analyse.json, complete.
    context = (await client.get(f"/api/internal/analyses/{analysis_id}/context", headers=worker)).json()
    assert context["source_key"].endswith("/versions/1/a.xlsx") and context["result_key"].endswith("/analyse.json")
    assert context["source_key"] in storage.objects
    started = await client.post(f"/api/internal/analyses/{analysis_id}/start", headers=worker)
    assert started.json()["status"] == "processing"
    storage.objects[context["result_key"]] = {"summary": {"rows": 3}}
    wrong = await client.post(
        f"/api/internal/analyses/{analysis_id}/complete", json={"s3_key": "elsewhere.json"}, headers=worker
    )
    assert wrong.status_code == 409
    done = await client.post(
        f"/api/internal/analyses/{analysis_id}/complete", json={"s3_key": context["result_key"]}, headers=worker
    )
    assert done.json()["status"] == "ready"

    ready = (await client.get(f"/api/files/{file['id']}/analysis")).json()
    assert (ready["status"], ready["result"]) == ("ready", {"summary": {"rows": 3}})
    listed = (await client.get(f"/api/collections/{collection['id']}/files")).json()
    assert listed[0]["status"] == "ready"


async def test_failed_analysis_is_reported_with_its_error(client, monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    worker = {"Authorization": "Bearer secret"}
    collection = await _create(client)
    file = (await client.post(f"/api/collections/{collection['id']}/files", files=_xlsx())).json()[0]
    analysis_id = (await client.get(f"/api/files/{file['id']}/analysis")).json()["id"]

    await client.post(f"/api/internal/analyses/{analysis_id}/start", headers=worker)
    await client.post(f"/api/internal/analyses/{analysis_id}/fail", json={"error": "Corrupt archive"}, headers=worker)

    failed = (await client.get(f"/api/files/{file['id']}/analysis")).json()
    assert (failed["status"], failed["error"], failed["result"]) == ("error", "Corrupt archive", None)


async def test_analysis_is_readable_by_a_shared_user_only(client) -> None:
    collection = await _create(client)
    file = (await client.post(f"/api/collections/{collection['id']}/files", files=_xlsx())).json()[0]
    await client.post(f"/api/collections/{collection['id']}/access", json={"email": BOB.email})

    app.dependency_overrides[get_actor] = lambda: Actor(user_id=BOB.user_id, email=BOB.email)
    assert (await client.get(f"/api/files/{file['id']}/analysis")).status_code == 200
    app.dependency_overrides[get_actor] = lambda: Actor(user_id="carol", email="carol@example.com")
    assert (await client.get(f"/api/files/{file['id']}/analysis")).status_code == 404


async def test_internal_analysis_api_requires_the_token(client, monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    missing = "00000000-0000-0000-0000-000000000000"

    assert (await client.get(f"/api/internal/analyses/{missing}/context")).status_code == 401
    assert (await client.post(f"/api/internal/analyses/{missing}/start")).status_code == 401
    unknown = await client.post(f"/api/internal/analyses/{missing}/start", headers={"Authorization": "Bearer secret"})
    assert unknown.status_code == 404


async def test_internal_run_files_lists_the_agents_scope(client, storage, monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    collection = await _create(client)
    file = (await client.post(f"/api/collections/{collection['id']}/files", files=_xlsx())).json()[0]
    conversation = (await client.post("/api/conversations", json={})).json()
    run = (await client.post(f"/api/conversations/{conversation['id']}/messages", json={"content": "q"})).json()["run"]
    url = f"/api/internal/runs/{run['id']}/files"

    assert (await client.get(url)).status_code == 401
    [item] = (await client.get(url, headers={"Authorization": "Bearer secret"})).json()

    assert (item["file_id"], item["file_name"], item["collection_name"]) == (file["id"], "a.xlsx", "Sales")
    assert (item["analysis_status"], item["result_key"]) == ("pending", None)
