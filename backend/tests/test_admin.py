import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security.factory import RequestContext, get_current_user
from app.db import get_session
from app.dependencies import get_dispatcher, get_model_catalog, get_storage
from app.main import app
from app.services import (
    Actor,
    AdminService,
    CollectionService,
    ConflictError,
    FileService,
    NotFoundError,
    RunService,
)
from tests.actors import ALICE, BOB

# --- service ---


@pytest.fixture
async def world(session, storage):
    """Alice owns Sales (shared with Bob and Carol) and HR (private); Bob owns Notes shared with Alice."""
    collections = CollectionService(session, storage)
    sales = await collections.create(ALICE, "Sales")
    hr = await collections.create(ALICE, "HR")
    notes = await collections.create(BOB, "Notes")
    await FileService(session, storage).upload(ALICE, sales.id, "a.csv", b"1")
    await collections.share(ALICE, sales.id, BOB.email)
    await collections.share(ALICE, sales.id, "carol@example.com")
    await collections.share(BOB, notes.id, ALICE.email)
    return sales, hr, notes


async def test_collection_access_lists_every_collection_with_owner_and_shares(session, world) -> None:
    sales, hr, notes = world

    overview = {item.name: item for item in await AdminService(session).collection_access()}

    assert {"Sales", "HR", "Notes"} <= overview.keys()
    assert (overview["Sales"].owner_email, overview["Sales"].owner_id) == (ALICE.email, ALICE.user_id)
    assert overview["Sales"].file_count == 1
    assert [a.email for a in overview["Sales"].shared_with] == [BOB.email, "carol@example.com"]
    assert overview["HR"].shared_with == [] and overview["HR"].file_count == 0
    assert [a.email for a in overview["Notes"].shared_with] == [ALICE.email]


async def test_people_access_groups_by_email_with_roles(session, world) -> None:
    people = {p.email: p for p in await AdminService(session).people_access() if p.email}

    roles = {email: sorted((c.name, c.role) for c in person.collections) for email, person in people.items()}
    assert roles[ALICE.email] == [("HR", "owner"), ("Notes", "viewer"), ("Sales", "owner")]
    assert roles[BOB.email] == [("Notes", "owner"), ("Sales", "viewer")]
    assert roles["carol@example.com"] == [("Sales", "viewer")]


async def test_owners_without_a_recorded_email_are_listed_by_user_id(session, storage) -> None:
    legacy = await CollectionService(session, storage).create(Actor(user_id="old-user"), "Legacy")

    people = await AdminService(session).people_access()

    entry = next(p for p in people if p.user_id == "old-user")
    assert entry.email is None and [c.collection_id for c in entry.collections] == [legacy.id]


async def test_grant_is_idempotent_normalized_and_records_who_granted(session, world) -> None:
    _, hr, _ = world
    admin = AdminService(session)

    first = await admin.grant(BOB, hr.id, " Dave@Example.com ")
    again = await admin.grant(BOB, hr.id, "dave@example.com")

    assert (first.email, first.granted_by) == ("dave@example.com", BOB.user_id)
    assert again.id == first.id


async def test_grant_works_on_collections_the_admin_does_not_own(session, world) -> None:
    sales, _, _ = world
    access = await AdminService(session).grant(Actor(user_id="admin", email="root@example.com"), sales.id, "new@x.org")

    assert access.collection_id == sales.id


async def test_grant_rejects_unknown_collections_blank_emails_and_the_owner(session, world) -> None:
    sales, _, _ = world
    admin = AdminService(session)

    with pytest.raises(NotFoundError):
        await admin.grant(ALICE, uuid.uuid4(), "x@y.z")
    with pytest.raises(ValueError):
        await admin.grant(ALICE, sales.id, "  ")
    with pytest.raises(ConflictError, match="already owns"):
        await admin.grant(BOB, sales.id, ALICE.email)


async def test_revoke_removes_access_and_the_person_loses_the_collection(session, storage, world) -> None:
    sales, _, _ = world
    admin = AdminService(session)

    await admin.revoke(sales.id, "CAROL@example.com")

    assert "carol@example.com" not in [a.email for item in await admin.collection_access() for a in item.shared_with]
    with pytest.raises(NotFoundError):
        await admin.revoke(sales.id, "carol@example.com")
    carol = Actor(user_id="carol", email="carol@example.com")
    assert await CollectionService(session, storage).list_for_user(carol) == []


async def test_created_collections_record_the_owner_email(session, storage) -> None:
    collection = await CollectionService(session, storage).create(Actor("u", " Mixed@Case.com "), "X")

    assert collection.created_by_email == "mixed@case.com"


# --- routes ---


def identity(*, admin: bool, user_id: str = "dev-user", email: str = "dev@example.com") -> RequestContext:
    return RequestContext(user_id=user_id, email=email, roles=["admin"] if admin else ["user"], is_admin=admin)


@pytest.fixture
async def api(session, storage, dispatcher, catalog):
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_dispatcher] = lambda: dispatcher
    app.dependency_overrides[get_model_catalog] = lambda: catalog
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


def login_as(**kwargs) -> None:
    app.dependency_overrides[get_current_user] = lambda: identity(**kwargs)


async def test_admin_routes_are_forbidden_to_non_admins(api) -> None:
    login_as(admin=False)
    some_id = "00000000-0000-0000-0000-000000000000"

    assert (await api.get("/api/admin/collections")).status_code == 403
    assert (await api.get("/api/admin/people")).status_code == 403
    assert (await api.get("/api/admin/feedback")).status_code == 403
    assert (await api.post(f"/api/admin/collections/{some_id}/access", json={"email": "a@b.c"})).status_code == 403
    assert (await api.delete(f"/api/admin/collections/{some_id}/access/a@b.c")).status_code == 403


async def test_admin_manages_access_over_http(api) -> None:
    login_as(admin=False, user_id="alice", email=ALICE.email)
    collection = (await api.post("/api/collections", json={"name": "Finance"})).json()

    login_as(admin=True)
    listed = {c["name"]: c for c in (await api.get("/api/admin/collections")).json()}
    assert listed["Finance"]["owner_email"] == ALICE.email and listed["Finance"]["shared_with"] == []

    granted = await api.post(f"/api/admin/collections/{collection['id']}/access", json={"email": " Eve@Example.com "})
    assert granted.status_code == 201 and granted.json()["email"] == "eve@example.com"
    assert granted.json()["granted_by"] == "dev-user"
    assert (
        await api.post(f"/api/admin/collections/{collection['id']}/access", json={"email": "no-at"})
    ).status_code == 422
    assert (
        await api.post(f"/api/admin/collections/{collection['id']}/access", json={"email": ALICE.email})
    ).status_code == 409

    eve = next(p for p in (await api.get("/api/admin/people")).json() if p["email"] == "eve@example.com")
    assert eve["collections"] == [{"collection_id": collection["id"], "name": "Finance", "role": "viewer"}]

    # the person now sees the collection, read-only
    login_as(admin=False, user_id="eve", email="eve@example.com")
    visible = (await api.get("/api/collections")).json()
    assert [(c["name"], c["is_owner"]) for c in visible] == [("Finance", False)]

    login_as(admin=True)
    assert (await api.delete(f"/api/admin/collections/{collection['id']}/access/eve@example.com")).status_code == 204
    assert (await api.delete(f"/api/admin/collections/{collection['id']}/access/eve@example.com")).status_code == 404
    login_as(admin=False, user_id="eve", email="eve@example.com")
    assert (await api.get("/api/collections")).json() == []


async def test_admin_cannot_reach_unknown_collections(api) -> None:
    login_as(admin=True)
    missing = "00000000-0000-0000-0000-000000000000"

    assert (await api.post(f"/api/admin/collections/{missing}/access", json={"email": "a@b.c"})).status_code == 404


async def test_admin_can_ask_for_a_search_index_rebuild(api, dispatcher) -> None:
    login_as(admin=False, user_id="alice", email=ALICE.email)
    collection = (await api.post("/api/collections", json={"name": "Finance"})).json()
    url = f"/api/admin/collections/{collection['id']}/search-index"

    assert (await api.post(url)).status_code == 403  # the owner is not an administrator

    login_as(admin=True)
    assert (await api.post(url)).status_code == 202
    assert dispatcher.rebuilt == [uuid.UUID(collection["id"])]
    assert (
        await api.post("/api/admin/collections/00000000-0000-0000-0000-000000000000/search-index")
    ).status_code == 404

    dispatcher.fail = True
    assert (await api.post(url)).status_code == 503


async def test_admin_grants_and_revocations_refresh_the_index_of_that_person(session, dispatcher, world) -> None:
    sales, _, _ = world
    admin = AdminService(session, dispatcher)

    await admin.grant(BOB, sales.id, " New@Example.org ")
    await admin.revoke(sales.id, "NEW@example.org")

    assert dispatcher.user_rebuilds == ["new@example.org", "new@example.org"]


async def test_admin_can_ask_for_a_person_s_index_to_be_rebuilt(api, dispatcher) -> None:
    login_as(admin=False)
    assert (await api.post("/api/admin/users/search-index", json={"email": "marie@example.fr"})).status_code == 403

    login_as(admin=True)
    assert (await api.post("/api/admin/users/search-index", json={"email": " Marie@Example.fr "})).status_code == 202
    assert dispatcher.user_rebuilds == ["marie@example.fr"]
    assert (await api.post("/api/admin/users/search-index", json={"email": "not-an-email"})).status_code == 422

    dispatcher.fail = True
    assert (await api.post("/api/admin/users/search-index", json={"email": "marie@example.fr"})).status_code == 503


async def test_admin_reads_the_feedback_with_the_exchange(api, session, dispatcher) -> None:
    login_as(admin=False, user_id="alice", email=ALICE.email)
    conversation = (await api.post("/api/conversations", json={})).json()
    sent = (await api.post(f"/api/conversations/{conversation['id']}/messages", json={"content": "Résume"})).json()
    runs = RunService(session, dispatcher)
    await runs.start(uuid.UUID(sent["run"]["id"]))
    answer = (await runs.complete(uuid.UUID(sent["run"]["id"]), "Voici.")).result_message_id
    await api.put(
        f"/api/conversations/{conversation['id']}/messages/{answer}/feedback",
        json={"rating": "down", "reason": "unclear", "comment": "peu clair"},
    )

    login_as(admin=True)
    [item] = (await api.get("/api/admin/feedback", params={"rating": "down"})).json()
    assert (item["question"], item["answer"], item["reason"], item["comment"], item["user_id"]) == (
        "Résume",
        "Voici.",
        "unclear",
        "peu clair",
        "alice",
    )
    assert (await api.get("/api/admin/feedback", params={"rating": "up"})).json() == []
    assert (await api.get("/api/admin/feedback", params={"limit": 0})).status_code == 422
