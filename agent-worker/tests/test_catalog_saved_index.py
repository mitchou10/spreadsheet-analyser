import gzip
import json

from app.agent.catalog import Catalog
from app.search.docs import build_file_docs, sheet_summary
from app.search.index_file import IndexedFile, SearchIndex, index_key
from app.search.text import TOKENIZER_VERSION
from tests.test_catalog import FakeStorage, build, column, entry, sheet


def sales_sheets():
    return [
        sheet(
            "Ventes",
            [
                column("région", top_values=[{"value": "Île-de-France", "count": 40}]),
                column("Montant_HT", "number", numeric={"min": 1.0, "max": 99.0, "mean": 40.0, "median": 38.0}),
            ],
        )
    ]


def hr_sheets():
    return [sheet("Employés", [column("matricule", "integer"), column("date_naissance", "date")])]


def saved(*entries, version: int = 1) -> bytes:
    """The collection search index the analysis worker would have written for these (meta, report) entries."""
    index = SearchIndex()
    for meta, report in entries:
        if report is None:
            continue
        indexed = IndexedFile(
            meta["file_id"],
            meta["file_name"],
            meta["collection_name"],
            version,
            meta["result_key"],
            sheet_summary(report),
        )
        index.upsert(indexed, build_file_docs(meta["file_id"], meta["file_name"], meta["collection_name"], report))
    return index.dumps()


def reads_of(storage_holder) -> list[str]:
    return storage_holder.reads


def load(entries, blobs=None) -> tuple[Catalog, FakeStorage]:
    reports = {meta["result_key"]: report for meta, report in entries if report is not None}
    storage = FakeStorage(reports, blobs)
    return Catalog.load([meta for meta, _ in entries], storage), storage


def names(result: dict) -> list[str]:
    return [item["name"] for item in result["columns"]]


def test_a_fresh_saved_index_is_the_only_thing_read_to_search() -> None:
    sales = entry("a", "ventes.xlsx", "Commercial", sales_sheets())
    catalog, storage = load([sales], blobs={index_key("col-Commercial"): saved(sales)})

    result = catalog.search("chiffre d'affaires par regions")

    assert names(result)[:2] == ["Montant_HT", "région"]
    assert storage.reads == [index_key("col-Commercial")]  # no analyse.json read, nothing indexed here


def test_saved_and_in_memory_indexes_give_the_same_answers() -> None:
    sales = entry("a", "ventes.xlsx", "Commercial", sales_sheets())
    from_saved, _ = load([sales], blobs={index_key("col-Commercial"): saved(sales)})
    from_scratch = build(sales)

    for query in ("region", "montant", "customer", "ile de france"):
        assert from_saved.search(query) == from_scratch.search(query), query
    assert from_saved.search_values("ile de france") == from_scratch.search_values("ile de france")


def test_describing_reads_the_full_analysis_once_and_only_then() -> None:
    sales = entry("a", "ventes.xlsx", "Commercial", sales_sheets())
    catalog, storage = load([sales], blobs={index_key("col-Commercial"): saved(sales)})
    catalog.search("region")
    catalog.search_values("Île-de-France")
    assert storage.reads == [index_key("col-Commercial")]

    catalog.describe_column("f1", "montant ht")
    catalog.describe_sheet("f1")

    assert storage.reads == [index_key("col-Commercial"), sales[0]["result_key"]]  # fetched once, then cached


def test_an_analysis_newer_than_the_saved_index_is_indexed_in_memory() -> None:
    old = entry("a", "ventes.xlsx", "Commercial", sales_sheets())
    stale_blob = saved(old)  # the index still describes version 1
    new_sheets = [sheet("Ventes", [column("chiffre_affaires", "number"), column("région")])]
    new_meta, new_report = entry("a", "ventes.xlsx", "Commercial", new_sheets)
    new_meta = {**new_meta, "version": 2, "result_key": "col-Commercial/id-a/versions/2/analyse.json"}
    other = entry("b", "rh.ods", "Commercial", hr_sheets())
    blob = saved(old, other)

    catalog, storage = load([(new_meta, new_report), other], blobs={index_key("col-Commercial"): blob})

    assert "chiffre_affaires" in names(catalog.search("chiffre affaires"))
    assert "Montant_HT" not in names(catalog.search("montant"))  # the old version's documents are not served
    assert "matricule" in names(catalog.search("matricule"))  # the up-to-date file still comes from the saved index
    assert storage.reads == [index_key("col-Commercial"), new_meta["result_key"]]  # only the new analysis was read
    assert stale_blob  # (kept for clarity: the stale index is what the worker had written)


def test_a_file_missing_from_the_saved_index_is_still_found() -> None:
    indexed = entry("a", "ventes.xlsx", "Commercial", sales_sheets())
    fresh_upload = entry("b", "rh.ods", "Commercial", hr_sheets())

    catalog, storage = load([indexed, fresh_upload], blobs={index_key("col-Commercial"): saved(indexed)})

    assert "matricule" in names(catalog.search("matricule"))
    assert "Montant_HT" in names(catalog.search("montant"))
    assert fresh_upload[0]["result_key"] in storage.reads


def test_an_unusable_saved_index_falls_back_to_indexing_in_memory() -> None:
    sales = entry("a", "ventes.xlsx", "Commercial", sales_sheets())
    wrong_tokenizer = json.loads(gzip.decompress(saved(sales)))
    wrong_tokenizer["tokenizer_version"] = TOKENIZER_VERSION + 1

    for blob in (b"garbage", gzip.compress(json.dumps(wrong_tokenizer).encode())):
        catalog, storage = load([sales], blobs={index_key("col-Commercial"): blob})

        assert "Montant_HT" in names(catalog.search("montant"))
        assert sales[0]["result_key"] in storage.reads


def test_a_storage_error_on_the_saved_index_does_not_break_the_search() -> None:
    sales = entry("a", "ventes.xlsx", "Commercial", sales_sheets())

    class Flaky(FakeStorage):
        def get_bytes(self, key, max_bytes=None):
            raise ConnectionError("s3 down")

    storage = Flaky({sales[0]["result_key"]: sales[1]})
    catalog = Catalog.load([sales[0]], storage)

    assert "Montant_HT" in names(catalog.search("montant"))


def test_several_collections_are_searched_together() -> None:
    sales = entry("a", "ventes.xlsx", "Commercial", sales_sheets())
    hr = entry("b", "rh.ods", "RH", hr_sheets())
    blobs = {index_key("col-Commercial"): saved(sales), index_key("col-RH"): saved(hr)}

    catalog, storage = load([sales, hr], blobs=blobs)

    assert names(catalog.search("montant"))[0] == "Montant_HT" and "matricule" in names(catalog.search("matricule"))
    assert storage.reads == [index_key("col-Commercial"), index_key("col-RH")]  # one read per collection, no report


def test_files_outside_the_scope_are_never_returned() -> None:
    sales = entry("a", "ventes.xlsx", "Commercial", sales_sheets())
    hr = entry("b", "rh.ods", "Commercial", hr_sheets())
    deleted = entry("gone", "supprime.csv", "Commercial", [sheet("S", [column("secret_column")])])
    blob = saved(sales, hr, deleted)  # the saved index still knows a file that was deleted, and one not in scope

    catalog, _ = load([sales], blobs={index_key("col-Commercial"): blob})

    assert names(catalog.search("matricule")) == []
    assert names(catalog.search("secret column")) == []
    assert names(catalog.search("montant")) == ["Montant_HT"]
    assert catalog.search_values("Île-de-France")["matches"]


def test_a_file_whose_analysis_is_not_ready_is_reported_not_served_from_old_documents() -> None:
    sales = entry("a", "ventes.xlsx", "Commercial", sales_sheets())
    blob = saved(sales)
    meta = {**sales[0], "analysis_status": "error", "result_key": None}  # the new version failed to analyse

    catalog, _ = load([(meta, None)], blobs={index_key("col-Commercial"): blob})

    result = catalog.search("montant")
    assert result["columns"] == [] and "ventes.xlsx" in result["not_searchable"]
