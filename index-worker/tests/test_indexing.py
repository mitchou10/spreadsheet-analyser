import gzip
import json
from contextlib import contextmanager

import pytest

from app.indexing import (
    DEBOUNCE_SECONDS,
    LOCK_SECONDS,
    Indexer,
    RedisDebouncer,
    RedisLocks,
    collection_lock_name,
    user_lock_name,
)
from app.search.docs import FIELD_WEIGHTS, build_file_docs
from app.search.engine import Index
from app.search.index_file import SearchIndex, index_key, user_index_key
from app.search.text import TOKENIZER_VERSION

COLLECTION = "col-1"
KEY = index_key(COLLECTION)
USER = "marie@example.fr"


def make_report(columns: list[str], sheet: str = "Feuille") -> dict:
    """The part of an analyse.json that indexing reads."""
    return {
        "sheets": [
            {
                "index": 0,
                "name": sheet,
                "hidden": False,
                "rows": 10,
                "header_detected": True,
                "truncated": False,
                "warnings": [],
                "preview": [],
                "columns": [
                    {
                        "index": i,
                        "name": name,
                        "type": "text",
                        "non_null": 10,
                        "null": 0,
                        "distinct": 3,
                        "distinct_exact": True,
                        "sample_values": ["a"],
                    }
                    for i, name in enumerate(columns)
                ],
            }
        ]
    }


REPORTS = {
    "ventes.csv": make_report(["région", "montant_ht", "date_commande"], "Ventes"),
    "rh.csv": make_report(["matricule", "date_naissance", "service"], "Employés"),
    "budget.csv": make_report(["poste", "objectif"], "Budget"),
}


def result_key(collection: str, file_id: str, version: int = 1) -> str:
    return f"{collection}/{file_id}/versions/{version}/analyse.json"


class Locks:
    """Records when each lock is held, to check every storage access is inside the right one."""

    def __init__(self) -> None:
        self.held: set[str] = set()
        self.history: list[tuple[str, str]] = []

    @contextmanager
    def __call__(self, name: str):
        assert name not in self.held, f"{name} taken twice"
        self.held.add(name)
        self.history.append(("acquire", name))
        try:
            yield
        finally:
            self.held.discard(name)
            self.history.append(("release", name))


class Storage:
    def __init__(self, locks: Locks) -> None:
        self.locks, self.blobs, self.reports = locks, {}, {}
        self.writes: list[str] = []
        self.unlocked: list[str] = []

    def _guard(self, key: str) -> None:
        owner = key.split("/")[0]
        needed = user_lock_name_for(key) if owner == "users" else collection_lock_name(owner)
        if needed not in self.locks.held:
            self.unlocked.append(key)

    def get_bytes(self, key):
        return self.blobs.get(key)

    def put_bytes(self, key, payload, content_type="application/octet-stream"):
        self._guard(key)
        self.blobs[key] = payload
        self.writes.append(key)

    def get_json(self, key):
        if key not in self.reports:
            raise FileNotFoundError(key)
        return self.reports[key]

    def delete(self, key):
        self._guard(key)
        self.blobs.pop(key, None)


def user_lock_name_for(key: str) -> str:
    return "user-index:" + key.split("/")[1]


class Client:
    def __init__(self) -> None:
        self.analyses: dict[str, list[dict]] = {}  # collection -> ready analyses
        self.contexts: dict[str, dict] = {}
        self.audiences: dict[str, dict] = {}
        self.user_collection_ids: dict[str, list[str]] = {}
        self.calls: list[str] = []

    def analysis_context(self, analysis_id):
        return self.contexts[analysis_id]

    def collection_analyses(self, collection_id):
        self.calls.append(f"analyses:{collection_id}")
        return self.analyses.get(collection_id, [])

    def collection_audience(self, collection_id):
        return self.audiences.get(collection_id, {"collection_id": collection_id, "owner_email": None, "emails": []})

    def user_collections(self, email):
        return self.user_collection_ids.get(email, [])


class Debouncer:
    def __init__(self) -> None:
        self.claimed: set[str] = set()

    def claim(self, email, seconds):
        if email in self.claimed:
            return False
        self.claimed.add(email)
        return True

    def release(self, email):
        self.claimed.discard(email)


class World:
    def __init__(self) -> None:
        self.locks = Locks()
        self.storage = Storage(self.locks)
        self.client = Client()
        self.debouncer = Debouncer()
        self.scheduled: list[tuple[str, int]] = []
        self.indexer = Indexer(
            self.client,
            self.storage,
            self.locks,
            self.debouncer,
            lambda email, countdown: self.scheduled.append((email, countdown)),
        )

    def analysed(self, collection: str, file_id: str, name: str, version: int = 1, report: dict | None = None) -> str:
        """The backend has a ready analysis for this file: returns the analysis id to hand to the worker."""
        key = result_key(collection, file_id, version)
        self.storage.reports[key] = report or REPORTS[name]
        item = {
            "file_id": file_id,
            "file_name": name,
            "collection_name": "Commercial",
            "version": version,
            "result_key": key,
        }
        self.client.analyses[collection] = [
            i for i in self.client.analyses.get(collection, []) if i["file_id"] != file_id
        ] + [item]
        analysis_id = f"an-{file_id}-{version}"
        self.client.contexts[analysis_id] = {
            "analysis_id": analysis_id,
            "file_id": file_id,
            "file_name": name,
            "collection_id": collection,
            "collection_name": "Commercial",
            "file_version": version,
            "result_key": key,
        }
        return analysis_id

    def collection_index(self, collection: str = COLLECTION) -> SearchIndex:
        return SearchIndex.loads(self.storage.blobs[index_key(collection)])

    def user_index(self, email: str = USER) -> SearchIndex:
        return SearchIndex.loads(self.storage.blobs[user_index_key(email)])


@pytest.fixture
def world() -> World:
    return World()


def hits(index: SearchIndex, query: str) -> list[str]:
    return [h.doc.payload.get("brief", {}).get("name", h.doc.payload["sheet"]) for h in index.index().search(query)]


# --- collection index ---


def test_the_first_analysis_of_a_collection_builds_its_whole_index_from_the_backend_list(world) -> None:
    world.analysed(COLLECTION, "r", "rh.csv")  # already analysed, never indexed
    analysis = world.analysed(COLLECTION, "v", "ventes.csv")

    world.indexer.file_analysed(analysis)

    index = world.collection_index()
    assert set(index.files) == {"v", "r"} and world.client.calls == [f"analyses:{COLLECTION}"]
    assert "montant_ht" in hits(index, "montant") and "matricule" in hits(index, "matricule")


def test_later_analyses_update_the_index_without_reading_the_others(world) -> None:
    world.indexer.file_analysed(world.analysed(COLLECTION, "v", "ventes.csv"))
    world.client.calls.clear()
    del world.storage.reports[result_key(COLLECTION, "v")]  # no other analysis can be read any more

    world.indexer.file_analysed(world.analysed(COLLECTION, "b", "budget.csv"))

    index = world.collection_index()
    assert set(index.files) == {"v", "b"} and world.client.calls == []
    assert "objectif" in hits(index, "objectif") and "montant_ht" in hits(index, "montant")


def test_a_new_version_replaces_the_old_documents_of_the_file(world) -> None:
    world.indexer.file_analysed(world.analysed(COLLECTION, "v", "ventes.csv"))

    world.indexer.file_analysed(world.analysed(COLLECTION, "v", "ventes.csv", version=2, report=REPORTS["budget.csv"]))

    index = world.collection_index()
    assert index.is_fresh("v", result_key(COLLECTION, "v", 2)) and not index.is_fresh(
        "v", result_key(COLLECTION, "v", 1)
    )
    assert hits(index, "montant") == [] and "objectif" in hits(index, "objectif")


def test_an_older_analysis_arriving_late_does_not_overwrite_a_newer_version(world) -> None:
    old = world.analysed(COLLECTION, "v", "ventes.csv", version=1)
    world.indexer.file_analysed(world.analysed(COLLECTION, "v", "ventes.csv", version=2, report=REPORTS["budget.csv"]))

    world.indexer.file_analysed(old)  # the event of version 1 is handled after version 2

    assert world.collection_index().files["v"].version == 2


@pytest.mark.parametrize("blob", ["garbage", "wrong-tokenizer"])
def test_an_unusable_collection_index_is_rebuilt_rather_than_patched(world, blob) -> None:
    world.indexer.file_analysed(world.analysed(COLLECTION, "v", "ventes.csv"))
    if blob == "garbage":
        world.storage.blobs[KEY] = b"not gzip"
    else:
        state = json.loads(gzip.decompress(world.storage.blobs[KEY]))
        state["tokenizer_version"] = TOKENIZER_VERSION + 1
        world.storage.blobs[KEY] = gzip.compress(json.dumps(state).encode())
    world.client.calls.clear()

    world.indexer.file_analysed(world.analysed(COLLECTION, "r", "rh.csv"))

    assert world.client.calls == [f"analyses:{COLLECTION}"] and set(world.collection_index().files) == {"v", "r"}


def test_forgetting_a_file_drops_its_documents_and_the_last_one_drops_the_index(world) -> None:
    world.analysed(COLLECTION, "v", "ventes.csv")
    world.analysed(COLLECTION, "r", "rh.csv")
    world.indexer.rebuild_collection(COLLECTION)

    assert world.indexer.forget_file(COLLECTION, "v") is True
    assert set(world.collection_index().files) == {"r"} and hits(world.collection_index(), "montant") == []
    writes = len(world.storage.writes)
    assert world.indexer.forget_file(COLLECTION, "v") is False and len(world.storage.writes) == writes
    assert world.indexer.forget_file(COLLECTION, "r") is True and KEY not in world.storage.blobs


def test_forgetting_in_a_collection_without_an_index_does_nothing(world) -> None:
    assert world.indexer.forget_file(COLLECTION, "x") is False and world.storage.writes == []


def test_a_rebuild_skips_unreadable_analyses_and_removes_an_index_with_nothing_left(world) -> None:
    world.analysed(COLLECTION, "v", "ventes.csv")
    world.analysed(COLLECTION, "r", "rh.csv")
    del world.storage.reports[result_key(COLLECTION, "r")]

    assert world.indexer.rebuild_collection(COLLECTION) == 1 and set(world.collection_index().files) == {"v"}
    world.client.analyses[COLLECTION] = []
    assert world.indexer.rebuild_collection(COLLECTION) == 0 and KEY not in world.storage.blobs


def test_the_saved_collection_index_answers_like_one_built_in_memory(world) -> None:
    for file_id, name in (("v", "ventes.csv"), ("r", "rh.csv"), ("b", "budget.csv")):
        world.analysed(COLLECTION, file_id, name)
    world.indexer.rebuild_collection(COLLECTION)
    docs = [
        d
        for f, n in (("v", "ventes.csv"), ("r", "rh.csv"), ("b", "budget.csv"))
        for d in build_file_docs(f, n, "Commercial", REPORTS[n])
    ]
    scratch = Index(docs, FIELD_WEIGHTS)

    for query in ("montant", "date", "service", "objectif", "customer", "regoin"):
        got = sorted(
            (h.doc.payload["file_id"], round(h.score, 6)) for h in world.collection_index().index().search(query)
        )
        want = sorted((h.doc.payload["file_id"], round(h.score, 6)) for h in scratch.search(query))
        assert got == want, query


# --- user index ---


def test_a_user_index_merges_the_collection_indexes_of_everything_the_person_can_read(world) -> None:
    for collection, file_id, name in (
        ("col-1", "v", "ventes.csv"),
        ("col-2", "r", "rh.csv"),
        ("col-3", "b", "budget.csv"),
    ):
        world.analysed(collection, file_id, name)
        world.indexer.rebuild_collection(collection)
    world.client.user_collection_ids[USER] = ["col-1", "col-2"]  # col-3 is not theirs

    count = world.indexer.rebuild_user(USER)

    index = world.user_index()
    assert count == 2 and set(index.files) == {"v", "r"}
    assert (
        "montant_ht" in hits(index, "montant")
        and "matricule" in hits(index, "matricule")
        and hits(index, "objectif") == []
    )


def test_building_a_user_index_reads_no_analysis(world) -> None:
    world.analysed("col-1", "v", "ventes.csv")
    world.indexer.rebuild_collection("col-1")
    world.client.user_collection_ids[USER] = ["col-1"]
    world.storage.reports.clear()  # analyses can no longer be read: only the collection indexes are used

    assert world.indexer.rebuild_user(USER) == 1


def test_a_collection_without_usable_index_is_skipped_in_the_user_index(world) -> None:
    world.analysed("col-1", "v", "ventes.csv")
    world.indexer.rebuild_collection("col-1")
    world.storage.blobs[index_key("col-2")] = b"garbage"
    world.client.user_collection_ids[USER] = ["col-1", "col-2", "col-never-indexed"]

    assert world.indexer.rebuild_user(USER) == 1 and set(world.user_index().files) == {"v"}


def test_a_person_who_can_read_nothing_has_no_index(world) -> None:
    world.analysed("col-1", "v", "ventes.csv")
    world.indexer.rebuild_collection("col-1")
    world.client.user_collection_ids[USER] = ["col-1"]
    world.indexer.rebuild_user(USER)

    world.client.user_collection_ids[USER] = []  # access revoked
    assert world.indexer.rebuild_user(USER) == 0 and user_index_key(USER) not in world.storage.blobs


def test_user_emails_are_normalised(world) -> None:
    world.analysed("col-1", "v", "ventes.csv")
    world.indexer.rebuild_collection("col-1")
    world.client.user_collection_ids[USER] = ["col-1"]

    world.indexer.rebuild_user("  Marie@Example.FR ")

    assert user_index_key("  Marie@Example.FR ") == user_index_key(USER) and set(world.user_index().files) == {"v"}


def test_the_user_index_key_hides_the_address() -> None:
    key = user_index_key("marie@example.fr")

    assert key.startswith("users/") and key.endswith("/search-index.json.gz") and "marie" not in key


# --- fan-out to the readers of a collection ---


def test_a_changed_collection_schedules_the_rebuild_of_each_reader_once(world) -> None:
    world.client.audiences["col-1"] = {
        "collection_id": "col-1",
        "owner_email": "Owner@Example.fr",
        "emails": [USER, "owner@example.fr"],
    }

    world.indexer.file_analysed(world.analysed("col-1", "v", "ventes.csv"))
    world.indexer.file_analysed(world.analysed("col-1", "r", "rh.csv"))  # a second file right after

    assert world.scheduled == [(USER, DEBOUNCE_SECONDS), ("owner@example.fr", DEBOUNCE_SECONDS)]  # sorted, deduplicated


def test_a_collection_change_after_a_user_rebuild_schedules_another_one(world) -> None:
    world.client.audiences["col-1"] = {"collection_id": "col-1", "owner_email": None, "emails": [USER]}
    world.indexer.file_analysed(world.analysed("col-1", "v", "ventes.csv"))
    world.client.user_collection_ids[USER] = ["col-1"]
    world.indexer.rebuild_user(USER)  # runs, and clears its "already scheduled" flag first

    world.indexer.file_analysed(world.analysed("col-1", "r", "rh.csv"))

    assert world.scheduled == [(USER, DEBOUNCE_SECONDS), (USER, DEBOUNCE_SECONDS)]


def test_deleting_a_file_also_refreshes_its_readers(world) -> None:
    world.client.audiences["col-1"] = {"collection_id": "col-1", "owner_email": None, "emails": [USER]}
    world.analysed("col-1", "v", "ventes.csv")
    world.indexer.rebuild_collection("col-1")
    world.scheduled.clear()
    world.debouncer.claimed.clear()

    world.indexer.forget_file("col-1", "v")

    assert world.scheduled == [(USER, DEBOUNCE_SECONDS)]


def test_an_audience_lookup_failure_does_not_fail_the_collection_update(world) -> None:
    def broken(collection_id):
        raise ConnectionError("backend down")

    world.client.collection_audience = broken

    world.indexer.file_analysed(world.analysed("col-1", "v", "ventes.csv"))

    assert set(world.collection_index("col-1").files) == {"v"} and world.scheduled == []


# --- locking ---


def test_every_write_happens_under_the_lock_of_the_index_it_changes(world) -> None:
    world.client.audiences["col-1"] = {"collection_id": "col-1", "owner_email": None, "emails": [USER]}
    world.indexer.file_analysed(world.analysed("col-1", "v", "ventes.csv"))
    world.indexer.file_analysed(world.analysed("col-1", "r", "rh.csv"))
    world.indexer.forget_file("col-1", "r")
    world.client.user_collection_ids[USER] = ["col-1"]
    world.indexer.rebuild_user(USER)
    world.indexer.rebuild_collection("col-1")

    assert world.storage.unlocked == []
    assert ("acquire", user_lock_name(USER)) in world.locks.history
    assert all(kind in ("acquire", "release") for kind, _ in world.locks.history)


def test_the_locks_are_per_collection_and_per_user_and_bounded_in_time() -> None:
    calls = []

    class FakeRedis:
        def lock(self, name, timeout, blocking_timeout):
            calls.append((name, timeout, blocking_timeout))
            return "a-lock"

    locks = RedisLocks(FakeRedis())

    assert locks(collection_lock_name("c1")) == "a-lock" and locks(user_lock_name(USER)) == "a-lock"
    assert calls[0] == ("search-index:c1", LOCK_SECONDS, LOCK_SECONDS)
    assert calls[1][0].startswith("user-index:") and "marie" not in calls[1][0]


def test_the_debouncer_claims_once_per_window_and_normalises_emails() -> None:
    store: dict[str, int] = {}

    class FakeRedis:
        def set(self, key, value, nx, ex):
            if nx and key in store:
                return None
            store[key] = ex
            return True

        def delete(self, key):
            store.pop(key, None)

    debouncer = RedisDebouncer(FakeRedis())

    assert debouncer.claim("Marie@Example.fr", 15) is True
    assert debouncer.claim("marie@example.fr", 15) is False  # same person, still scheduled
    debouncer.release(" MARIE@example.fr ")
    assert debouncer.claim("marie@example.fr", 15) is True
    assert (
        list(store) == ["index:user-scheduled:marie@example.fr"] and store["index:user-scheduled:marie@example.fr"] > 15
    )
