import gzip
import json
from contextlib import contextmanager

import pytest

from app.analysis.analyzer import analyze_file
from app.indexing import LOCK_SECONDS, IndexManager, RedisCollectionLocks
from app.search.index_file import SearchIndex, index_key
from app.search.text import TOKENIZER_VERSION

COLLECTION = "col-1"
KEY = index_key(COLLECTION)


@pytest.fixture
def reports(tmp_path):
    """Real analyses (what analyse.json holds) of three small files."""
    contents = {
        "ventes.csv": "région;montant_ht;date_commande\nNord;10,5;01/02/2024\nSud;20;02/03/2024\n",
        "rh.csv": "matricule;date_naissance;service\n1;01/01/1980;Comptabilité\n2;02/02/1990;Logistique\n",
        "budget.csv": "poste;objectif\nSalaires;50000\nLoyer;12000\n",
    }
    out = {}
    for name, text in contents.items():
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        out[name] = analyze_file(path, name)
    return out


def item(file_id: str, name: str, version: int = 1) -> dict:
    return {
        "file_id": file_id,
        "file_name": name,
        "collection_name": "Commercial",
        "version": version,
        "result_key": f"{COLLECTION}/{file_id}/versions/{version}/analyse.json",
    }


def context(file_id: str, name: str, version: int = 1) -> dict:
    return {
        "analysis_id": f"an-{file_id}",
        "file_id": file_id,
        "file_name": name,
        "file_version": version,
        "collection_id": COLLECTION,
        "collection_name": "Commercial",
        "result_key": item(file_id, name, version)["result_key"],
    }


class Locks:
    """Records when a collection's lock is held, so tests can check every storage access is inside it."""

    def __init__(self) -> None:
        self.held: set[str] = set()
        self.history: list[tuple[str, str]] = []

    @contextmanager
    def __call__(self, collection_id: str):
        assert collection_id not in self.held, "lock taken twice"
        self.held.add(collection_id)
        self.history.append(("acquire", collection_id))
        try:
            yield
        finally:
            self.held.discard(collection_id)
            self.history.append(("release", collection_id))


class Storage:
    def __init__(self, locks: Locks, blobs: dict | None = None) -> None:
        self.locks, self.blobs, self.unlocked_access = locks, blobs or {}, []
        self.reports: dict[str, dict] = {}
        self.writes: list[str] = []

    def _check(self, key: str) -> None:
        if COLLECTION not in self.locks.held:
            self.unlocked_access.append(key)

    def get_bytes(self, key):
        self._check(key)
        return self.blobs.get(key)

    def put_bytes(self, key, payload, content_type="application/octet-stream"):
        self._check(key)
        self.blobs[key] = payload
        self.writes.append(key)

    def get_json(self, key):
        if key not in self.reports:
            raise FileNotFoundError(key)
        return self.reports[key]

    def delete(self, key):
        self._check(key)
        self.blobs.pop(key, None)


class Client:
    def __init__(self, items: list[dict]) -> None:
        self.items, self.calls = items, 0

    def collection_analyses(self, collection_id):
        self.calls += 1
        return self.items


def manager(reports, files: list[tuple[str, str]], blobs=None):
    locks = Locks()
    storage = Storage(locks, blobs)
    items = [item(file_id, name) for file_id, name in files]
    for entry in items:
        storage.reports[entry["result_key"]] = reports[entry["file_name"]]
    client = Client(items)
    return IndexManager(client, storage, locks), storage, client, locks


def saved(storage: Storage) -> SearchIndex:
    return SearchIndex.loads(storage.blobs[KEY])


def hits(index: SearchIndex, query: str) -> list[str]:
    return [h.doc.payload.get("brief", {}).get("name", h.doc.payload["sheet"]) for h in index.index().search(query)]


def test_the_first_analysis_of_a_collection_builds_the_whole_index_from_the_backend_list(reports) -> None:
    indexer, storage, client, _ = manager(reports, [("v", "ventes.csv"), ("r", "rh.csv")])

    indexer.on_analysis_ready(context("v", "ventes.csv"), reports["ventes.csv"])

    index = saved(storage)
    assert set(index.files) == {"v", "r"} and client.calls == 1  # the other analysed file is picked up too
    assert "montant_ht" in hits(index, "montant") and "matricule" in hits(index, "matricule")


def test_later_analyses_update_the_saved_index_without_reading_the_others(reports) -> None:
    indexer, storage, client, _ = manager(reports, [("v", "ventes.csv"), ("r", "rh.csv")])
    indexer.on_analysis_ready(context("v", "ventes.csv"), reports["ventes.csv"])
    storage.reports.clear()  # from now on, no other analysis can be read
    client.calls = 0

    indexer.on_analysis_ready(context("b", "budget.csv"), reports["budget.csv"])

    index = saved(storage)
    assert set(index.files) == {"v", "r", "b"} and client.calls == 0
    assert "objectif" in hits(index, "objectif") and "montant_ht" in hits(index, "montant")


def test_a_new_version_replaces_the_old_documents_of_the_file(reports) -> None:
    indexer, storage, _, _ = manager(reports, [("v", "ventes.csv")])
    indexer.on_analysis_ready(context("v", "ventes.csv"), reports["ventes.csv"])

    indexer.on_analysis_ready(context("v", "ventes.csv", version=2), reports["budget.csv"])  # v2 is another table

    index = saved(storage)
    assert index.is_fresh("v", item("v", "ventes.csv", 2)["result_key"])
    assert not index.is_fresh("v", item("v", "ventes.csv", 1)["result_key"])
    assert hits(index, "montant") == [] and "objectif" in hits(index, "objectif")


def test_storage_is_only_touched_while_the_collection_lock_is_held(reports) -> None:
    indexer, storage, _, locks = manager(reports, [("v", "ventes.csv")])

    indexer.on_analysis_ready(context("v", "ventes.csv"), reports["ventes.csv"])
    indexer.on_analysis_ready(context("r", "rh.csv"), reports["rh.csv"])
    indexer.forget_file(COLLECTION, "r")
    indexer.rebuild(COLLECTION)

    assert storage.unlocked_access == []
    assert locks.history[0] == ("acquire", COLLECTION) and locks.history[-1] == ("release", COLLECTION)
    assert [kind for kind, _ in locks.history] == ["acquire", "release"] * 4  # one critical section per call


@pytest.mark.parametrize("blob", ["garbage", "wrong-tokenizer"])
def test_an_unusable_saved_index_is_rebuilt_rather_than_patched(reports, blob) -> None:
    indexer, storage, client, _ = manager(reports, [("v", "ventes.csv"), ("r", "rh.csv")])
    indexer.on_analysis_ready(context("v", "ventes.csv"), reports["ventes.csv"])
    if blob == "garbage":
        storage.blobs[KEY] = b"not gzip"
    else:
        state = json.loads(gzip.decompress(storage.blobs[KEY]))
        state["tokenizer_version"] = TOKENIZER_VERSION + 1
        storage.blobs[KEY] = gzip.compress(json.dumps(state).encode())
    client.calls = 0

    indexer.on_analysis_ready(context("r", "rh.csv"), reports["rh.csv"])

    assert client.calls == 1 and set(saved(storage).files) == {"v", "r"}


def test_forgetting_a_file_removes_its_documents_and_the_last_one_removes_the_index(reports) -> None:
    indexer, storage, _, _ = manager(reports, [("v", "ventes.csv"), ("r", "rh.csv")])
    indexer.rebuild(COLLECTION)

    assert indexer.forget_file(COLLECTION, "v") is True
    assert set(saved(storage).files) == {"r"} and hits(saved(storage), "montant") == []
    assert indexer.forget_file(COLLECTION, "v") is False  # already gone: nothing written
    writes = len(storage.writes)
    assert indexer.forget_file(COLLECTION, "r") is True
    assert KEY not in storage.blobs and len(storage.writes) == writes  # deleted, not rewritten empty


def test_forgetting_in_a_collection_without_index_does_nothing(reports) -> None:
    indexer, storage, _, _ = manager(reports, [])

    assert indexer.forget_file(COLLECTION, "x") is False and storage.writes == []


def test_rebuild_skips_unreadable_analyses_and_counts_what_it_indexed(reports) -> None:
    indexer, storage, _, _ = manager(reports, [("v", "ventes.csv"), ("r", "rh.csv")])
    del storage.reports[item("r", "rh.csv")["result_key"]]  # the analysis of rh.csv cannot be read

    assert indexer.rebuild(COLLECTION) == 1
    assert set(saved(storage).files) == {"v"}


def test_rebuilding_a_collection_with_nothing_analysed_removes_a_stale_index(reports) -> None:
    indexer, storage, client, _ = manager(reports, [("v", "ventes.csv")])
    indexer.rebuild(COLLECTION)
    client.items = []

    assert indexer.rebuild(COLLECTION) == 0 and KEY not in storage.blobs


def test_the_saved_index_serves_the_same_answers_as_one_built_in_memory(reports) -> None:
    from app.search.docs import FIELD_WEIGHTS, build_file_docs
    from app.search.engine import Index

    indexer, storage, _, _ = manager(reports, [("v", "ventes.csv"), ("r", "rh.csv"), ("b", "budget.csv")])
    indexer.rebuild(COLLECTION)
    docs = []
    for file_id, name in (("v", "ventes.csv"), ("r", "rh.csv"), ("b", "budget.csv")):
        docs += build_file_docs(file_id, name, "Commercial", reports[name])
    scratch = Index(docs, FIELD_WEIGHTS)

    for query in ("montant", "date", "service", "objectif", "customer", "regoin"):
        got = [(h.doc.payload["file_id"], round(h.score, 6)) for h in saved(storage).index().search(query)]
        want = [(h.doc.payload["file_id"], round(h.score, 6)) for h in scratch.search(query)]
        assert sorted(got) == sorted(want), query


# --- the Redis lock ---


def test_the_lock_is_per_collection_and_bounded_in_time() -> None:
    calls = []

    class FakeRedis:
        def lock(self, name, timeout, blocking_timeout):
            calls.append((name, timeout, blocking_timeout))
            return "a-lock"

    locks = RedisCollectionLocks(FakeRedis())

    assert locks("c1") == "a-lock" and locks("c2") == "a-lock"
    assert calls == [("search-index:c1", LOCK_SECONDS, LOCK_SECONDS), ("search-index:c2", LOCK_SECONDS, LOCK_SECONDS)]
