import uuid

import pytest

from app.services.storage import (
    analysis_key,
    base_of,
    collection_prefix,
    file_key,
    legacy_collection_prefix,
    sanitize_file_name,
    version_key,
)

COLLECTION_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
FILE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
PROJECT = "spreadsheet-analyser"


def test_every_key_starts_with_the_project_level() -> None:
    assert (
        file_key(COLLECTION_ID, FILE_ID, 3, "sales.xlsx")
        == f"{PROJECT}/{COLLECTION_ID}/{FILE_ID}/versions/3/sales.xlsx"
    )
    assert analysis_key(COLLECTION_ID, FILE_ID, 3) == f"{PROJECT}/{COLLECTION_ID}/{FILE_ID}/versions/3/analyse.json"
    assert collection_prefix(COLLECTION_ID) == f"{PROJECT}/{COLLECTION_ID}/"


def test_the_project_level_is_configurable_and_slashes_are_ignored(monkeypatch) -> None:
    monkeypatch.setenv("S3_KEY_PREFIX", "/other-project/")

    assert file_key(COLLECTION_ID, FILE_ID, 1, "a.csv") == f"other-project/{COLLECTION_ID}/{FILE_ID}/versions/1/a.csv"
    assert collection_prefix(COLLECTION_ID) == f"other-project/{COLLECTION_ID}/"


def test_an_empty_prefix_gives_the_original_layout(monkeypatch) -> None:
    monkeypatch.setenv("S3_KEY_PREFIX", "")

    assert file_key(COLLECTION_ID, FILE_ID, 3, "sales.xlsx") == f"{COLLECTION_ID}/{FILE_ID}/versions/3/sales.xlsx"
    assert collection_prefix(COLLECTION_ID) == legacy_collection_prefix(COLLECTION_ID) == f"{COLLECTION_ID}/"


def test_a_stored_key_gives_back_its_own_layout_whatever_the_current_prefix() -> None:
    legacy = f"{COLLECTION_ID}/{FILE_ID}/versions/1/sales.xlsx"  # written before the project level existed
    current = f"{PROJECT}/{COLLECTION_ID}/{FILE_ID}/versions/4/sales.xlsx"

    assert (
        base_of(legacy) == f"{COLLECTION_ID}/{FILE_ID}" and base_of(current) == f"{PROJECT}/{COLLECTION_ID}/{FILE_ID}"
    )
    assert version_key(legacy, 2, "analyse.json") == f"{COLLECTION_ID}/{FILE_ID}/versions/2/analyse.json"
    assert version_key(current, 2, "sales.xlsx") == f"{PROJECT}/{COLLECTION_ID}/{FILE_ID}/versions/2/sales.xlsx"


def test_a_file_name_cannot_add_key_segments() -> None:
    assert sanitize_file_name("../../etc/passwd") == "passwd"
    assert sanitize_file_name("C:\\docs\\report.csv") == "report.csv"
    assert sanitize_file_name("") == "file"
    assert file_key(COLLECTION_ID, FILE_ID, 1, "../../x.csv").endswith("/versions/1/x.csv")


@pytest.mark.parametrize("prefix", ["spreadsheet-analyser", "a/b", ""])
def test_keys_never_contain_double_slashes(monkeypatch, prefix) -> None:
    monkeypatch.setenv("S3_KEY_PREFIX", prefix)

    assert "//" not in file_key(COLLECTION_ID, FILE_ID, 1, "a.csv") and not file_key(
        COLLECTION_ID, FILE_ID, 1, "a.csv"
    ).startswith("/")
