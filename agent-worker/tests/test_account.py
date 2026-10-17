import pytest

from app.agent.account import Account
from app.agent.catalog import CatalogError


def file(name, size=100, status="ready", uploaded="2026-10-01T10:00:00+00:00", version=1):
    return {
        "file_id": f"id-{name}",
        "name": name,
        "version": version,
        "size_bytes": size,
        "uploaded_at": uploaded,
        "analysis_status": status,
    }


def collection(name, files, owner=True, shared_with=0, description=None):
    return {
        "collection_id": f"col-{name}",
        "name": name,
        "description": description,
        "created_at": "2026-09-01T10:00:00+00:00",
        "is_owner": owner,
        "shared_with": shared_with if owner else None,
        "files": files,
    }


@pytest.fixture
def account():
    return Account(
        {
            "truncated": False,
            "collections": [
                collection(
                    "Ventes",
                    [
                        file("a.csv", 100, "ready", "2026-10-03T10:00:00+00:00"),
                        file("b.csv", 50, "error", "2026-10-02T10:00:00+00:00"),
                        file("c.csv", 25, None, "2026-10-01T10:00:00+00:00"),
                    ],
                    shared_with=2,
                ),
                collection("Ressources humaines", [file("rh.xlsx", 400, "processing", "2026-10-04T10:00:00+00:00")]),
                collection("Chez Bob", [file("d.csv", 10, "pending")], owner=False),
            ],
        }
    )


def test_overview_counts_owned_shared_files_and_states(account) -> None:
    overview = account.overview()

    assert overview["owned_collections"] == 2
    assert overview["shared_with_me_collections"] == 1
    assert overview["files"] == 5
    assert overview["total_size_bytes"] == 585
    assert overview["files_by_analysis_status"] == {"ready": 1, "error": 1, "none": 1, "processing": 1, "pending": 1}


def test_overview_describes_each_collection(account) -> None:
    by_name = {c["name"]: c for c in account.overview()["collections"]}

    assert by_name["Ventes"]["owner"] == "me" and by_name["Ventes"]["shared_with_people"] == 2
    assert by_name["Ventes"]["files"] == 3 and by_name["Ventes"]["size_bytes"] == 175
    assert by_name["Ventes"]["last_upload"] == "2026-10-03T10:00:00+00:00"
    assert by_name["Chez Bob"]["owner"] == "shared with me"
    assert "shared_with_people" not in by_name["Chez Bob"]  # not known, and not theirs to know


def test_overview_of_an_empty_account() -> None:
    overview = Account({"collections": [], "truncated": False}).overview()

    assert (overview["owned_collections"], overview["files"], overview["collections"]) == (0, 0, [])


def test_a_collection_without_files_has_no_last_upload() -> None:
    overview = Account({"collections": [collection("Vide", [])], "truncated": False}).overview()

    assert overview["collections"][0]["last_upload"] is None


def test_files_are_listed_newest_first_across_the_account(account) -> None:
    listing = account.files()

    assert [f["file"] for f in listing["files"]] == ["rh.xlsx", "a.csv", "b.csv", "c.csv", "d.csv"]
    assert listing["total_matching"] == 5 and listing["shown"] == 5


def test_files_can_be_limited_to_a_collection_by_name_or_id_ignoring_accents_and_case(account) -> None:
    assert [f["file"] for f in account.files(collection="ressources HUMAINES")["files"]] == ["rh.xlsx"]
    assert [f["file"] for f in account.files(collection="col-Ventes")["files"]][:1] == ["a.csv"]
    assert [f["file"] for f in account.files(collection="ress")["files"]] == ["rh.xlsx"]  # unique prefix


def test_files_can_be_filtered_by_analysis_state_including_never_analysed(account) -> None:
    assert [f["file"] for f in account.files(status="error")["files"]] == ["b.csv"]
    assert [f["file"] for f in account.files(status="none")["files"]] == ["c.csv"]
    assert [f["file"] for f in account.files(status="READY")["files"]] == ["a.csv"]


def test_the_limit_cuts_the_list_but_the_total_stays_known(account) -> None:
    listing = account.files(limit=2)

    assert (listing["total_matching"], listing["shown"]) == (5, 2)


def test_unknown_collection_or_state_is_an_error_that_says_what_exists(account) -> None:
    with pytest.raises(CatalogError, match="Ventes"):
        account.files(collection="inconnue")
    with pytest.raises(CatalogError, match="ready, pending"):
        account.files(status="cassé")


def test_a_cut_account_says_so() -> None:
    cut = Account({"collections": [collection("A", [file("a.csv")])], "truncated": True})

    assert "note" in cut.overview() and "note" in cut.files()
