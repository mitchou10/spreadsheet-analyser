import json

import pytest

from app.agent.catalog import Catalog, CatalogError
from app.agent.tools import MAX_TOOL_OUTPUT_CHARS, build_tools
from app.search.text import canon, tokenize


def column(name, kind="text", **extra):
    base = {
        "index": 0,
        "name": name,
        "type": kind,
        "non_null": 10,
        "null": 0,
        "type_counts": {},
        "distinct": 5,
        "distinct_exact": True,
        "sample_values": [],
    }
    return {**base, **extra}


def sheet(name, columns, rows=100):
    return {
        "index": 0,
        "name": name,
        "hidden": False,
        "rows": rows,
        "header_detected": True,
        "truncated": False,
        "warnings": [],
        "preview": [["a", 1]],
        "columns": columns,
    }


class FakeStorage:
    """In-memory S3: analyse.json reports and (optionally) saved search indexes."""

    def __init__(self, reports: dict[str, dict], blobs: dict[str, bytes] | None = None) -> None:
        self.reports, self.blobs = reports, blobs or {}
        self.reads: list[str] = []

    def get_json(self, key: str, max_bytes: int | None = None):
        self.reads.append(key)
        return self.reports[key]

    def get_bytes(self, key: str, max_bytes: int | None = None) -> bytes | None:
        self.reads.append(key)
        return self.blobs.get(key)


def entry(ref, file_name, collection, sheets, status="ready"):
    """(backend description of the file, its analyse.json or None) - the order of the entries gives f1, f2..."""
    meta = {
        "file_id": f"id-{ref}",
        "file_name": file_name,
        "collection_id": f"col-{collection}",
        "collection_name": collection,
        "version": 1,
        "analysis_status": status,
        "result_key": f"col-{collection}/id-{ref}/versions/1/analyse.json" if sheets is not None else None,
    }
    return meta, ({"sheets": sheets} if sheets is not None else None)


def build(*entries, blobs: dict[str, bytes] | None = None) -> Catalog:
    reports = {meta["result_key"]: report for meta, report in entries if report is not None}
    return Catalog.load([meta for meta, _ in entries], FakeStorage(reports, blobs))


@pytest.fixture
def catalog() -> Catalog:
    sales = entry(
        "f1",
        "ventes_2024.xlsx",
        "Commercial",
        [
            sheet(
                "Ventes",
                [
                    column(
                        "région",
                        top_values=[{"value": "Île-de-France", "count": 40}, {"value": "Bretagne", "count": 9}],
                    ),
                    column("Montant_HT", "number", numeric={"min": 1.0, "max": 99.0, "mean": 40.0, "median": 38.0}),
                    column("date_commande", "date", dates={"min": "2024-01-02", "max": "2024-12-30"}),
                    column(
                        "nom_client", top_values=[{"value": "Dupont", "count": 4}], sample_values=["Dupont", "Martin"]
                    ),
                ],
            ),
            sheet("Objectifs", [column("région"), column("objectif", "integer")], rows=12),
        ],
    )
    hr = entry(
        "f2",
        "personnel.ods",
        "RH",
        [
            sheet(
                "Employés",
                [
                    column("matricule", "integer"),
                    column("date_naissance", "date", dates={"min": "1960-05-01", "max": "2001-09-30"}),
                    column(
                        "salaireBrut",
                        "number",
                        numeric={"min": 1800.0, "max": 7000.0, "mean": 3100.0, "median": 2900.0},
                    ),
                    column("service", top_values=[{"value": "Comptabilité", "count": 8}]),
                ],
            )
        ],
    )
    pending = entry("f3", "brouillon.csv", "RH", None, status="pending")
    return build(sales, hr, pending)


def names(result: dict, kind: str = "columns") -> list[str]:
    return [item["name"] if kind == "columns" else item["sheet"] for item in result[kind]]


# --- text normalisation ---


def test_tokenize_folds_accents_case_plurals_and_identifier_styles() -> None:
    assert tokenize("Montant_HT") == ["montant", "ht"]
    assert tokenize("salaireBrut") == ["salaire", "brut"]
    assert tokenize("Les RÉGIONS de l'Île-de-France") == ["region", "ile", "france"]
    assert canon("Île-de-France") == canon("ile de france") == "ile de france"


# --- column search ---


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("region", "région"),  # accents
        ("REGIONS", "région"),  # case + plural
        ("regoin", "région"),  # typo
        ("date commande", "date_commande"),  # snake_case
        ("montant ht", "Montant_HT"),
        ("salaire brut", "salaireBrut"),  # camelCase
        ("customer", "nom_client"),  # English synonym
        ("revenue", "Montant_HT"),
        ("chiffre d'affaires", "Montant_HT"),  # multi-word synonym
        ("wages", None),  # no synonym/typo link: nothing invented
        ("matric", "matricule"),  # prefix
        ("Dupont", "nom_client"),  # a value found in the column
        ("dupond", "nom_client"),  # a value, with a typo
        ("comptabilite", "service"),  # accent-insensitive value
    ],
)
def test_search_finds_the_right_column(catalog, query, expected) -> None:
    columns = names(catalog.search(query))

    if expected is None:
        assert columns == []
    else:
        assert columns[0] == expected


def test_matching_every_word_beats_matching_one(catalog) -> None:
    assert names(catalog.search("date de naissance"))[0] == "date_naissance"  # not date_commande
    assert names(catalog.search("date commande"))[0] == "date_commande"


def test_search_explains_why_a_column_matched(catalog) -> None:
    top = catalog.search("customer")["columns"][0]

    assert top["why"] == ["nom"]  # matched through the synonym of "customer"
    assert top["file"] == "f1 (ventes_2024.xlsx)" and top["sheet"] == "Ventes"
    assert {"type", "non_null", "distinct"} <= top.keys()


def test_file_and_sheet_names_are_searchable(catalog) -> None:
    assert names(catalog.search("objectifs"), "sheets")[0] == "Objectifs"
    by_file = catalog.search("RH")
    assert {item["file"].split()[0] for item in by_file["columns"]} == {"f2"}  # the RH collection's analysed file
    assert names(catalog.search("vent"), "sheets")[0] == "Ventes"  # prefix of "ventes"


def test_search_can_be_restricted_to_one_file(catalog) -> None:
    unrestricted = {item["file"].split()[0] for item in catalog.search("date")["columns"]}
    restricted = {item["file"].split()[0] for item in catalog.search("date", file="personnel.ods")["columns"]}

    assert unrestricted == {"f1", "f2"} and restricted == {"f2"}


def test_unanalysed_files_are_reported_not_silently_skipped(catalog) -> None:
    result = catalog.search("quoi que ce soit")

    assert "brouillon.csv" in result["not_searchable"]
    assert "Aucun résultat" in result["note"]


# --- value search ---


def test_search_values_ignores_accents_and_punctuation(catalog) -> None:
    [match, *_] = catalog.search_values("ile de france")["matches"]

    assert (match["column"], match["value"], match["occurrences"], match["match"]) == (
        "région",
        "Île-de-France",
        40,
        "exacte",
    )


def test_search_values_is_typo_tolerant_and_ranks_exact_first(catalog) -> None:
    close = catalog.search_values("bretgne")["matches"]
    assert [(m["value"], m["match"]) for m in close] == [("Bretagne", "proche")]

    mixed = catalog.search_values("dupont")
    assert mixed["matches"][0]["match"] == "exacte"
    assert "uniquement" in mixed["coverage"]  # the agent is told a miss proves nothing


def test_search_values_reports_nothing_found(catalog) -> None:
    assert catalog.search_values("zzzzzz")["matches"] == []
    with pytest.raises(CatalogError):
        catalog.search_values("   ")


# --- resolving references ---


def test_files_resolve_by_ref_id_name_or_unique_prefix(catalog) -> None:
    assert catalog.resolve_file("f2").name == "personnel.ods"
    assert catalog.resolve_file("id-f1").name == "ventes_2024.xlsx"
    assert catalog.resolve_file("Ventes_2024.XLSX").ref == "f1"
    assert catalog.resolve_file("perso").ref == "f2"
    with pytest.raises(CatalogError, match="Fichiers disponibles"):
        catalog.resolve_file("nope")


def test_describe_column_and_sheet(catalog) -> None:
    full = catalog.describe_column("f1", "montant ht")
    assert (full["name"], full["sheet"], full["numeric"]["max"]) == ("Montant_HT", "Ventes", 99.0)

    assert catalog.describe_column("f1", "objectif")["sheet"] == "Objectifs"  # found without naming the sheet
    assert catalog.describe_column("f1", "region", sheet="objectifs")["sheet"] == "Objectifs"

    described = catalog.describe_sheet("f1", "Ventes")
    assert [c["name"] for c in described["columns"]][:2] == ["région", "Montant_HT"]
    assert described["preview_first_rows"] == [["a", 1]]
    assert catalog.describe_sheet("f2")["sheet"] == "Employés"  # single sheet: no need to name it


def test_ambiguous_or_missing_targets_explain_what_exists(catalog) -> None:
    with pytest.raises(CatalogError, match="plusieurs feuilles"):
        catalog.describe_sheet("f1")
    with pytest.raises(CatalogError, match="Feuille 'zzz' introuvable"):
        catalog.describe_sheet("f1", "zzz")
    with pytest.raises(CatalogError, match="Colonnes : "):
        catalog.describe_column("f2", "inconnue")
    with pytest.raises(CatalogError, match="analyse en attente"):
        catalog.describe_sheet("f3")


def test_overview_and_listing(catalog) -> None:
    overview = catalog.overview().splitlines()

    assert overview[0] == (
        "f1 · ventes_2024.xlsx (collection Commercial) — "
        "Ventes [100 lignes, 4 colonnes], Objectifs [12 lignes, 2 colonnes]"
    )
    assert overview[2] == "f3 · brouillon.csv (collection RH) — analyse en attente"
    listing = {item["file"]: item for item in catalog.list_files()}
    assert listing["personnel.ods"]["sheets"] == [{"name": "Employés", "rows": 100, "columns": 4}]
    assert "sheets" not in listing["brouillon.csv"]


def test_overview_is_capped_for_big_libraries() -> None:
    many = build(*[entry(f"f{i}", f"file{i}.csv", "C", [sheet("S", [column("a")])]) for i in range(1, 61)])

    lines = many.overview().splitlines()

    assert len(lines) == 41 and "20 autres fichiers" in lines[-1]


# --- as tools ---


def test_tools_return_json_and_turn_errors_into_text(catalog) -> None:
    tools = {tool.name: tool for tool in build_tools(lambda: catalog, lambda: None)}

    found = json.loads(tools["search"].invoke({"query": "customer"}))
    assert found["columns"][0]["name"] == "nom_client"
    assert (
        tools["describe_column"].invoke({"file": "zzz", "column": "x"}).startswith("Erreur : Fichier 'zzz' introuvable")
    )
    assert json.loads(tools["list_files"].invoke({}))[0]["ref"] == "f1"


def test_huge_tool_output_is_clipped() -> None:
    many = build(*[entry(f"f{i}", f"file_number_{i}.csv", "C", [sheet("S", [column("a")])]) for i in range(1, 151)])
    tool = next(t for t in build_tools(lambda: many, lambda: None) if t.name == "list_files")

    output = tool.invoke({})

    assert len(output) < MAX_TOOL_OUTPUT_CHARS + 200 and "tronqué" in output
