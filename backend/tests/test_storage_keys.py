import uuid

from app.services.storage import analysis_key, file_key, sanitize_file_name

COLLECTION_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
FILE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


def test_file_key_layout() -> None:
    assert file_key(COLLECTION_ID, FILE_ID, 3, "sales.xlsx") == f"{COLLECTION_ID}/{FILE_ID}/versions/3/sales.xlsx"


def test_analysis_key_layout() -> None:
    assert analysis_key(COLLECTION_ID, FILE_ID, 3) == f"{COLLECTION_ID}/{FILE_ID}/versions/3/analyse.json"


def test_sanitize_file_name_strips_path_segments() -> None:
    assert sanitize_file_name("../../etc/passwd") == "passwd"
    assert sanitize_file_name("C:\\docs\\report.csv") == "report.csv"
    assert sanitize_file_name("") == "file"
