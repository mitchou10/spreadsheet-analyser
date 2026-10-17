import gzip
import json

import pytest

from app.search.docs import FIELD_WEIGHTS, build_file_docs, column_values, sheet_summary
from app.search.engine import Doc, Index
from app.search.index_file import IndexedFile, IndexFormatError, SearchIndex, index_key
from app.search.text import TOKENIZER_VERSION


def column(name, kind="text", **extra):
    base = {
        "index": 0,
        "name": name,
        "type": kind,
        "non_null": 10,
        "null": 0,
        "distinct": 5,
        "distinct_exact": True,
        "sample_values": [],
    }
    return {**base, **extra}


REPORT = {
    "sheets": [
        {
            "index": 0,
            "name": "Ventes",
            "hidden": False,
            "rows": 120,
            "header_detected": True,
            "truncated": False,
            "warnings": [],
            "preview": [],
            "columns": [
                column("région", top_values=[{"value": "Île-de-France", "count": 40}], sample_values=["Nord"]),
                column("Montant_HT", "number", numeric={"min": 1.0, "max": 9.0, "mean": 4.0, "median": 4.0}),
                column("date_commande", "date", dates={"min": "2024-01-02", "max": "2024-12-30"}),
            ],
        }
    ]
}
OTHER = {
    "sheets": [{**REPORT["sheets"][0], "name": "Budget", "columns": [column("poste"), column("objectif", "integer")]}]
}


def indexed(file_id: str, name: str, report: dict, version: int = 1, collection: str = "Commercial"):
    key = f"col/{file_id}/versions/{version}/analyse.json"
    file = IndexedFile(file_id, name, collection, version, key, sheet_summary(report))
    return file, build_file_docs(file_id, name, collection, report)


def make_index() -> SearchIndex:
    index = SearchIndex()
    index.upsert(*indexed("f-sales", "ventes.xlsx", REPORT))
    index.upsert(*indexed("f-budget", "budget.ods", OTHER))
    return index


def search(index: Index, query: str) -> list[tuple[str, float]]:
    return [
        (hit.doc.payload.get("brief", {}).get("name") or hit.doc.payload["sheet"], round(hit.score, 6))
        for hit in index.search(query, limit=10)
    ]


# --- documents ---


def test_documents_carry_everything_a_hit_needs() -> None:
    docs = build_file_docs("f1", "ventes.xlsx", "Commercial", REPORT)

    kinds = [doc.payload["kind"] for doc in docs]
    assert kinds == ["sheet", "column", "column", "column"]
    region = next(d for d in docs if d.payload.get("brief", {}).get("name") == "région").payload
    assert region["file_id"] == "f1" and region["sheet"] == "Ventes"
    assert region["values"] == [{"value": "Île-de-France", "count": 40}, {"value": "Nord", "count": None}]
    assert region["brief"]["top_values"] == ["Île-de-France (40)"]
    sheet = docs[0].payload
    assert (sheet["rows"], sheet["columns"]) == (120, ["région", "Montant_HT", "date_commande"])
    json.dumps([doc.to_state() for doc in docs], allow_nan=False)  # the payloads are plain JSON


def test_column_values_are_deduplicated_and_bounded() -> None:
    col = column("x", top_values=[{"value": "a", "count": 3}], sample_values=["a", "b"] + [str(i) for i in range(50)])

    values = column_values(col)

    assert values[0] == {"value": "a", "count": 3} and values[1] == {"value": "b", "count": None}
    assert len(values) == 20 and len({v["value"] for v in values}) == 20


# --- the BM25 index can be saved and restored ---


def test_restored_index_answers_exactly_like_the_original() -> None:
    original = make_index()
    restored = SearchIndex.loads(original.dumps())

    for query in ("region", "montant", "chiffre d'affaires", "regoin", "objectifs", "date commande", "poste"):
        assert search(restored.index(), query) == search(original.index(), query), query


def test_restoring_reuses_the_saved_statistics_instead_of_recounting(monkeypatch) -> None:
    data = make_index().dumps()
    computed = []
    monkeypatch.setattr(Index, "_compute_state", staticmethod(lambda *a, **k: computed.append(1)))

    restored = SearchIndex.loads(data)
    restored.index().search("region")

    assert computed == []


def test_upsert_replaces_a_file_and_remove_forgets_it() -> None:
    index = make_index()

    index.upsert(*indexed("f-sales", "ventes.xlsx", OTHER, version=2))  # a new version of the same file

    assert index.files["f-sales"].version == 2 and index.is_fresh("f-sales", "col/f-sales/versions/2/analyse.json")
    assert not index.is_fresh("f-sales", "col/f-sales/versions/1/analyse.json")
    assert {d.payload["sheet"] for d in index.docs if d.payload["file_id"] == "f-sales"} == {"Budget"}

    assert index.remove("f-budget") is True and index.remove("f-budget") is False
    assert all(d.payload["file_id"] != "f-budget" for d in index.docs)
    restored = SearchIndex.loads(index.dumps())
    assert set(restored.files) == {"f-sales"} and len(restored.docs) == len(index.docs)


def test_statistics_follow_the_content_after_a_change() -> None:
    index = SearchIndex()
    index.upsert(*indexed("a", "a.csv", REPORT))
    alone = Index(index.docs, FIELD_WEIGHTS).idf["region"]
    index.upsert(*indexed("b", "b.csv", OTHER))  # more documents, none of them about "region"

    assert index.index().idf["region"] > alone  # rarer now: recomputed over both files, not the stale value


def test_the_file_is_compressed_json_with_a_version() -> None:
    state = json.loads(gzip.decompress(make_index().dumps()))

    assert state["schema_version"] == 1 and state["tokenizer_version"] == TOKENIZER_VERSION
    assert set(state["files"]) == {"f-sales", "f-budget"} and set(state["stats"]) == {
        "doc_count",
        "avg_length",
        "postings",
    }
    assert state["stats"]["doc_count"] == len(state["docs"])


def test_the_same_content_gives_the_same_bytes_apart_from_the_timestamp() -> None:
    a, b = json.loads(gzip.decompress(make_index().dumps())), json.loads(gzip.decompress(make_index().dumps()))
    a.pop("built_at"), b.pop("built_at")

    assert a == b


def test_index_key_lives_next_to_the_collection_files() -> None:
    assert index_key("c1") == "c1/search-index.json.gz"


# --- an unusable saved index is refused, never half-used ---


def corrupt(mutate) -> bytes:
    state = json.loads(gzip.decompress(make_index().dumps()))
    mutate(state)
    return gzip.compress(json.dumps(state).encode())


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"not gzip at all", "Unreadable"),
        (gzip.compress(b"{not json"), "Unreadable"),
        (corrupt(lambda s: s.update(schema_version=99)), "schema"),
        (corrupt(lambda s: s.update(tokenizer_version=TOKENIZER_VERSION + 1)), "another tokenizer"),
        (corrupt(lambda s: s["stats"].update(doc_count=1)), "Inconsistent"),
        (corrupt(lambda s: s.pop("docs")), "Inconsistent"),
        (corrupt(lambda s: s["files"]["f-sales"].pop("result_key")), "Inconsistent"),
    ],
)
def test_unusable_saved_indexes_raise_index_format_error(data, message) -> None:
    with pytest.raises(IndexFormatError, match=message):
        SearchIndex.loads(data)


def test_a_decompression_bomb_is_refused() -> None:
    bomb = gzip.compress(b"0" * 5_000_000)

    with pytest.raises(IndexFormatError, match="expands"):
        SearchIndex.loads(bomb, max_bytes=1_000_000)


def test_doc_state_round_trip() -> None:
    doc = Doc(payload={"kind": "column", "file_id": "x"}, fields={"name": ["a", "b"]})

    assert Doc.from_state(doc.to_state()).counts == doc.counts
