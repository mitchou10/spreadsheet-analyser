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

    messages = (await client.get(f"/api/conversations/{conversation['id']}/messages")).json()["items"]
    assert [m["content"] for m in messages] == ["Résume ce fichier"]
    listed = (await client.get("/api/conversations")).json()
    assert [(c["id"], c["title"]) for c in listed] == [(conversation["id"], "Résume ce fichier")]

    assert (await client.delete(f"/api/conversations/{conversation['id']}")).status_code == 204
    assert (await client.get(f"/api/conversations/{conversation['id']}/messages")).status_code == 404
    assert (await client.get("/api/conversations")).json() == []


async def test_messages_name_their_sources_with_the_collection_of_each_file(client, storage) -> None:
    conversation = (await client.post("/api/conversations", json={})).json()
    collection = await _create(client)
    uploaded = (
        await client.post(
            f"/api/collections/{collection['id']}/files", files=[("files", ("ventes.csv", b"a", "text/csv"))]
        )
    ).json()

    sent = await client.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"content": "q", "collection_ids": [collection["id"]], "file_ids": [uploaded[0]["id"]]},
    )

    assert sent.status_code == 202
    expected_file = {
        "id": uploaded[0]["id"],
        "name": "ventes.csv",
        "collection_id": collection["id"],
        "collection_name": collection["name"],
    }
    expected_collection = {"id": collection["id"], "name": collection["name"]}
    message = sent.json()["message"]
    assert message["files"] == [expected_file]
    assert message["collections"] == [expected_collection]
    listed = (await client.get(f"/api/conversations/{conversation['id']}/messages")).json()["items"]
    assert listed[0]["files"] == [expected_file]
    assert listed[0]["collections"] == [expected_collection]


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


async def test_retry_run_on_the_last_message(client, dispatcher) -> None:
    conversation = (await client.post("/api/conversations", json={})).json()
    url = f"/api/conversations/{conversation['id']}/runs/retry"
    assert (await client.post(url)).status_code == 409  # nothing to retry yet

    sent = (await _send(client, conversation["id"], "Résume")).json()
    assert (await client.post(url)).status_code == 409  # still answering
    await client.post(f"/api/runs/{sent['run']['id']}/cancel")

    retried = await client.post(url)

    assert retried.status_code == 202
    assert retried.json()["status"] == "queued"
    assert retried.json()["message_id"] == sent["message"]["id"]
    assert retried.json()["id"] != sent["run"]["id"]
    messages = (await client.get(f"/api/conversations/{conversation['id']}/messages")).json()["items"]
    assert len(messages) == 1

    app.dependency_overrides[get_actor] = lambda: Actor(user_id=BOB.user_id, email=BOB.email)
    assert (await client.post(url)).status_code == 404


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

    messages = (await client.get(f"/api/conversations/{conversation['id']}/messages")).json()["items"]
    assert [(m["role"], m["content"]) for m in messages] == [("user", "Résume"), ("assistant", "Réponse")]
    assert (await client.get(f"/api/conversations/{conversation['id']}/active-run")).json() is None


async def test_the_agents_trace_is_stored_with_the_answer_and_listed_with_the_messages(client, monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    worker = {"Authorization": "Bearer secret"}
    conversation = (await client.post("/api/conversations", json={})).json()
    run = (await _send(client, conversation["id"])).json()["run"]
    await client.post(f"/api/internal/runs/{run['id']}/start", headers=worker)
    trace = {
        "plan": "Chercher la colonne prix",
        "files": [{"file_id": "f1", "file_name": "ventes.csv", "collection_name": "Ventes"}],
        "steps": [{"tool": "search", "arguments": {"query": "prix"}, "output": '{"columns": []}'}],
    }

    done = await client.post(
        f"/api/internal/runs/{run['id']}/complete", json={"content": "42", "trace": trace}, headers=worker
    )

    assert done.status_code == 200
    messages = (await client.get(f"/api/conversations/{conversation['id']}/messages")).json()["items"]
    assert messages[0]["trace"] is None  # the user's message has none
    assert messages[1]["trace"] == trace


async def test_a_trace_that_is_too_large_is_refused(client, monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    worker = {"Authorization": "Bearer secret"}
    conversation = (await client.post("/api/conversations", json={})).json()
    run = (await _send(client, conversation["id"])).json()["run"]
    await client.post(f"/api/internal/runs/{run['id']}/start", headers=worker)
    steps = [{"tool": "search", "arguments": {}, "output": "x"}] * 51

    refused = await client.post(
        f"/api/internal/runs/{run['id']}/complete", json={"content": "a", "trace": {"steps": steps}}, headers=worker
    )

    assert refused.status_code == 422


async def test_internal_run_account_describes_the_requesters_collections_and_files(
    client, storage, monkeypatch
) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    worker = {"Authorization": "Bearer secret"}
    collection = await _create(client)
    await client.post(f"/api/collections/{collection['id']}/files", files=[("files", ("a.csv", b"1", "text/csv"))])
    conversation = (await client.post("/api/conversations", json={})).json()
    run = (await _send(client, conversation["id"])).json()["run"]

    account = await client.get(f"/api/internal/runs/{run['id']}/account", headers=worker)

    assert account.status_code == 200
    body = account.json()
    assert body["truncated"] is False
    assert [(c["name"], c["is_owner"], c["shared_with"]) for c in body["collections"]] == [
        (collection["name"], True, 0)
    ]
    assert [(f["name"], f["analysis_status"]) for f in body["collections"][0]["files"]] == [("a.csv", "pending")]
    missing = "/api/internal/runs/00000000-0000-0000-0000-000000000000/account"
    assert (await client.get(missing, headers=worker)).status_code == 404
    assert (await client.get(f"/api/internal/runs/{run['id']}/account")).status_code == 401


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


async def test_internal_collection_analyses_feed_the_search_index(client, storage, monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    worker = {"Authorization": "Bearer secret"}
    collection = await _create(client)
    file = (await client.post(f"/api/collections/{collection['id']}/files", files=_xlsx())).json()[0]
    url = f"/api/internal/collections/{collection['id']}/analyses"
    assert (await client.get(url)).status_code == 401
    assert (await client.get(url, headers=worker)).json() == []  # nothing analysed yet

    analysis_id = (await client.get(f"/api/files/{file['id']}/analysis")).json()["id"]
    context = (await client.get(f"/api/internal/analyses/{analysis_id}/context", headers=worker)).json()
    assert (context["collection_id"], context["collection_name"]) == (collection["id"], "Sales")
    await client.post(f"/api/internal/analyses/{analysis_id}/start", headers=worker)
    storage.objects[context["result_key"]] = {"sheets": []}
    await client.post(
        f"/api/internal/analyses/{analysis_id}/complete", json={"s3_key": context["result_key"]}, headers=worker
    )

    ready = (await client.get(url, headers=worker)).json()
    assert ready == [
        {
            "file_id": file["id"],
            "file_name": "a.xlsx",
            "collection_name": "Sales",
            "version": 1,
            "result_key": context["result_key"],
        }
    ]
    missing = "/api/internal/collections/00000000-0000-0000-0000-000000000000/analyses"
    assert (await client.get(missing, headers=worker)).status_code == 404


async def test_deleting_a_file_asks_the_worker_to_drop_it_from_the_search_index(client, dispatcher) -> None:
    collection = await _create(client)
    file = (await client.post(f"/api/collections/{collection['id']}/files", files=_xlsx())).json()[0]

    assert (await client.delete(f"/api/files/{file['id']}")).status_code == 204

    assert dispatcher.forgotten == [(uuid.UUID(collection["id"]), uuid.UUID(file["id"]))]


async def test_deleting_a_file_still_works_when_the_queue_is_down(client, dispatcher) -> None:
    collection = await _create(client)
    file = (await client.post(f"/api/collections/{collection['id']}/files", files=_xlsx())).json()[0]
    dispatcher.fail = True

    assert (await client.delete(f"/api/files/{file['id']}")).status_code == 204


async def test_a_refused_file_deletion_does_not_touch_the_search_index(client, dispatcher) -> None:
    collection = await _create(client)
    file = (await client.post(f"/api/collections/{collection['id']}/files", files=_xlsx())).json()[0]
    await client.post(f"/api/collections/{collection['id']}/access", json={"email": BOB.email})

    app.dependency_overrides[get_actor] = lambda: Actor(user_id=BOB.user_id, email=BOB.email)
    assert (await client.delete(f"/api/files/{file['id']}")).status_code == 403

    assert dispatcher.forgotten == []


async def test_internal_collection_audience_and_user_collections_feed_the_index_worker(client, monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    worker = {"Authorization": "Bearer secret"}
    collection = await _create(client)
    await client.post(f"/api/collections/{collection['id']}/access", json={"email": BOB.email})
    audience_url = f"/api/internal/collections/{collection['id']}/audience"
    assert (await client.get(audience_url)).status_code == 401

    audience = (await client.get(audience_url, headers=worker)).json()
    assert audience == {"collection_id": collection["id"], "owner_email": "dev@example.com", "emails": [BOB.email]}
    missing = "/api/internal/collections/00000000-0000-0000-0000-000000000000/audience"
    assert (await client.get(missing, headers=worker)).status_code == 404

    url = "/api/internal/users/collections"
    assert (await client.get(url, params={"email": BOB.email})).status_code == 401
    assert (await client.get(url, params={"email": BOB.email}, headers=worker)).json() == {
        "collection_ids": [collection["id"]]
    }
    owner = (await client.get(url, params={"email": "DEV@example.com"}, headers=worker)).json()["collection_ids"]
    assert collection["id"] in owner
    assert (await client.get(url, params={"email": "nobody@example.com"}, headers=worker)).json() == {
        "collection_ids": []
    }


async def test_sharing_over_http_refreshes_the_index_of_the_person(client, dispatcher) -> None:
    collection = await _create(client)

    await client.post(f"/api/collections/{collection['id']}/access", json={"email": BOB.email})
    await client.delete(f"/api/collections/{collection['id']}/access/{BOB.email}")

    assert dispatcher.user_rebuilds == [BOB.email, BOB.email]


async def _running_run_with_a_ready_file(client, storage):
    """A run being executed on a collection holding one analysed file; returns (run id, file id)."""
    worker = {"Authorization": "Bearer secret"}
    collection = await _create(client)
    file = (await client.post(f"/api/collections/{collection['id']}/files", files=_xlsx())).json()[0]
    analysis_id = (await client.get(f"/api/files/{file['id']}/analysis")).json()["id"]
    context = (await client.get(f"/api/internal/analyses/{analysis_id}/context", headers=worker)).json()
    await client.post(f"/api/internal/analyses/{analysis_id}/start", headers=worker)
    storage.objects[context["result_key"]] = {"sheets": []}
    await client.post(
        f"/api/internal/analyses/{analysis_id}/complete", json={"s3_key": context["result_key"]}, headers=worker
    )
    conversation = (await client.post("/api/conversations", json={})).json()
    run = (await _send(client, conversation["id"])).json()["run"]
    await client.post(f"/api/internal/runs/{run['id']}/start", headers=worker)
    return run["id"], file["id"]


async def test_sql_query_routes_cover_the_agent_and_the_query_worker(client, storage, dispatcher, monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    worker = {"Authorization": "Bearer secret"}
    run_id, file_id = await _running_run_with_a_ready_file(client, storage)
    url = f"/api/internal/runs/{run_id}/queries"
    body = {"sql": 'SELECT * FROM f1."Sheet1"', "files": [{"ref": "f1", "file_id": file_id}]}

    assert (await client.post(url, json=body)).status_code == 401
    created = await client.post(url, json=body, headers=worker)
    assert created.status_code == 202
    query = created.json()
    assert query["status"] == "queued" and query["result"] is None and dispatcher.queries == [uuid.UUID(query["id"])]

    base = f"/api/internal/queries/{query['id']}"
    context = (await client.get(f"{base}/context", headers=worker)).json()
    assert context["sql"] == body["sql"] and context["tables"][0]["ref"] == "f1"
    assert (await client.post(f"{base}/start", headers=worker)).json()["status"] == "running"
    assert (await client.post(f"{base}/start", headers=worker)).status_code == 409
    result = {"columns": [{"name": "n", "type": "BIGINT"}], "rows": [[1], [2]], "truncated": False}
    assert (await client.post(f"{base}/complete", json=result, headers=worker)).json()["status"] == "completed"

    polled = (await client.get(base, headers=worker)).json()
    assert polled["status"] == "completed" and polled["result"] == result


async def test_a_failed_sql_query_is_polled_with_its_error_and_the_tables(client, storage, monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    worker = {"Authorization": "Bearer secret"}
    run_id, file_id = await _running_run_with_a_ready_file(client, storage)
    body = {"sql": "SELEC", "files": [{"ref": "f1", "file_id": file_id}]}
    query = (await client.post(f"/api/internal/runs/{run_id}/queries", json=body, headers=worker)).json()
    base = f"/api/internal/queries/{query['id']}"
    await client.post(f"{base}/start", headers=worker)
    tables = [{"table": '"f1"."Sheet1"', "columns": [{"name": "x", "type": "BIGINT"}]}]

    await client.post(f"{base}/fail", json={"error": "SQL invalide", "tables": tables}, headers=worker)

    polled = (await client.get(base, headers=worker)).json()
    assert (polled["status"], polled["error"], polled["available_tables"]) == ("failed", "SQL invalide", tables)


async def test_sql_query_requests_are_validated(client, storage, monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    worker = {"Authorization": "Bearer secret"}
    run_id, file_id = await _running_run_with_a_ready_file(client, storage)
    url = f"/api/internal/runs/{run_id}/queries"
    one_file = [{"ref": "f1", "file_id": file_id}]

    assert (await client.post(url, json={"sql": "", "files": one_file}, headers=worker)).status_code == 422
    assert (await client.post(url, json={"sql": "SELECT 1", "files": []}, headers=worker)).status_code == 422
    bad_ref = [{"ref": 'f1"; DROP', "file_id": file_id}]
    assert (await client.post(url, json={"sql": "SELECT 1", "files": bad_ref}, headers=worker)).status_code == 422
    foreign = [{"ref": "f1", "file_id": "00000000-0000-0000-0000-000000000000"}]
    assert (await client.post(url, json={"sql": "SELECT 1", "files": foreign}, headers=worker)).status_code == 404
    missing = "/api/internal/queries/00000000-0000-0000-0000-000000000000"
    assert (await client.get(missing, headers=worker)).status_code == 404


async def test_a_sql_result_over_the_ceiling_is_refused(client, storage, monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    worker = {"Authorization": "Bearer secret"}
    run_id, file_id = await _running_run_with_a_ready_file(client, storage)
    body = {"sql": "SELECT 1", "files": [{"ref": "f1", "file_id": file_id}]}
    query = (await client.post(f"/api/internal/runs/{run_id}/queries", json=body, headers=worker)).json()
    base = f"/api/internal/queries/{query['id']}"
    await client.post(f"{base}/start", headers=worker)

    huge = {"columns": [{"name": "n", "type": "BIGINT"}], "rows": [[i] for i in range(501)], "truncated": False}

    assert (await client.post(f"{base}/complete", json=huge, headers=worker)).status_code == 422


async def _run_with_a_successful_query(client, storage):
    """A running run whose query (over its one analysed file) succeeded; returns (run id, query id)."""
    worker = {"Authorization": "Bearer secret"}
    run_id, file_id = await _running_run_with_a_ready_file(client, storage)
    body = {"sql": 'SELECT 1 AS "n"', "files": [{"ref": "f1", "file_id": file_id}]}
    query = (await client.post(f"/api/internal/runs/{run_id}/queries", json=body, headers=worker)).json()
    base = f"/api/internal/queries/{query['id']}"
    await client.post(f"{base}/start", headers=worker)
    result = {"columns": [{"name": "n", "type": "BIGINT"}], "rows": [[1]], "truncated": False}
    await client.post(f"{base}/complete", json=result, headers=worker)
    return run_id, query["id"]


CHART_SPEC = {"type": "bar", "x": "région", "y": ["total"], "title": "Total par région"}


async def test_a_chart_goes_from_the_agent_to_the_worker_to_the_owner_behind_the_backend(
    client, storage, dispatcher, monkeypatch
) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    worker = {"Authorization": "Bearer secret"}
    run_id, query_id = await _run_with_a_successful_query(client, storage)
    url = f"/api/internal/runs/{run_id}/charts"

    assert (await client.post(url, json={"query_id": query_id, "spec": CHART_SPEC})).status_code == 401
    created = await client.post(url, json={"query_id": query_id, "spec": CHART_SPEC}, headers=worker)
    assert created.status_code == 202
    chart = created.json()
    assert chart["status"] == "queued" and dispatcher.charts == [uuid.UUID(chart["id"])]
    image_url = chart["url"]
    assert chart["markdown"] == f"![Total par région]({image_url})"
    assert image_url.startswith("/api/conversations/") and image_url.endswith(f"/charts/{chart['id']}")

    base = f"/api/internal/charts/{chart['id']}"
    context = (await client.get(f"{base}/context", headers=worker)).json()
    assert context["sql"] == 'SELECT 1 AS "n"' and context["spec"]["type"] == "bar"
    assert context["s3_key"].endswith(f"/{chart['id']}.png") and "/conversations/" in context["s3_key"]
    await client.post(f"{base}/start", headers=worker)
    storage.objects[context["s3_key"]] = b"\x89PNG-bytes"
    done = await client.post(
        f"{base}/complete", json={"s3_key": context["s3_key"], "width": 900, "height": 540}, headers=worker
    )
    assert done.json()["status"] == "completed" and done.json()["width"] == 900

    image = await client.get(image_url)
    assert image.status_code == 200 and image.content == b"\x89PNG-bytes"
    assert image.headers["content-type"] == "image/png" and image.headers["x-content-type-options"] == "nosniff"
    assert "private" in image.headers["cache-control"]

    app.dependency_overrides[get_actor] = lambda: Actor(user_id=BOB.user_id, email=BOB.email)
    assert (await client.get(image_url)).status_code == 404  # not Bob's conversation
    prefix, _, rest = image_url.partition("/messages/")
    tail = rest.partition("/charts/")[2]
    del app.dependency_overrides[get_actor]
    other_message = f"{prefix}/messages/{uuid.uuid4()}/charts/{tail}"
    assert (await client.get(other_message)).status_code == 404  # the owner, but not that message


async def test_a_chart_request_is_validated_and_refused_when_it_cannot_be_drawn(client, storage, monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    worker = {"Authorization": "Bearer secret"}
    run_id, query_id = await _run_with_a_successful_query(client, storage)
    url = f"/api/internal/runs/{run_id}/charts"

    bad_spec = {"type": "pie", "x": "a", "y": ["b", "c"], "title": "t"}
    assert (await client.post(url, json={"query_id": query_id, "spec": bad_spec}, headers=worker)).status_code == 422
    unknown = "00000000-0000-0000-0000-000000000000"
    assert (await client.post(url, json={"query_id": unknown, "spec": CHART_SPEC}, headers=worker)).status_code == 404
    assert (await client.get(f"/api/internal/charts/{unknown}", headers=worker)).status_code == 404


async def test_a_failed_chart_is_polled_with_its_error_and_the_columns(client, storage, monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    worker = {"Authorization": "Bearer secret"}
    run_id, query_id = await _run_with_a_successful_query(client, storage)
    chart = (
        await client.post(
            f"/api/internal/runs/{run_id}/charts", json={"query_id": query_id, "spec": CHART_SPEC}, headers=worker
        )
    ).json()
    base = f"/api/internal/charts/{chart['id']}"
    await client.post(f"{base}/start", headers=worker)
    columns = [{"name": "n", "type": "BIGINT"}]

    await client.post(
        f"{base}/fail", json={"error": "Colonne 'région' introuvable", "columns": columns}, headers=worker
    )

    polled = (await client.get(base, headers=worker)).json()
    assert (polled["status"], polled["error"], polled["available_columns"]) == (
        "failed",
        "Colonne 'région' introuvable",
        columns,
    )
    assert (await client.get(chart["url"])).status_code == 404  # nothing was drawn
