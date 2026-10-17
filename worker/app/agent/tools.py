import json
from collections.abc import Callable

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.agent.catalog import Catalog, CatalogError

MAX_TOOL_OUTPUT_CHARS = 6000


class SearchArgs(BaseModel):
    query: str = Field(
        description="Ce que vous cherchez, en quelques mots (ex: 'ventes par région', 'date de naissance')."
    )
    file: str | None = Field(default=None, description="Limiter à un fichier (réf. f1, id ou nom). Défaut : tous.")
    limit: int = Field(default=8, ge=1, le=20, description="Nombre maximum de colonnes retournées.")


class SearchValuesArgs(BaseModel):
    value: str = Field(description="Une valeur à retrouver (ex: 'Paris', 'Dupont', '2024-03').")
    file: str | None = Field(default=None, description="Limiter à un fichier (réf. f1, id ou nom).")


class DescribeSheetArgs(BaseModel):
    file: str = Field(description="Réf. du fichier (f1), son id ou son nom.")
    sheet: str | None = Field(default=None, description="Nom de la feuille (inutile s'il n'y en a qu'une).")


class DescribeColumnArgs(BaseModel):
    file: str = Field(description="Réf. du fichier (f1), son id ou son nom.")
    column: str = Field(description="Nom de la colonne (accents et majuscules ignorés).")
    sheet: str | None = Field(default=None, description="Nom de la feuille si le fichier en a plusieurs.")


class NoArgs(BaseModel):
    pass


def _render(payload) -> str:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(text) > MAX_TOOL_OUTPUT_CHARS:
        text = (
            text[:MAX_TOOL_OUTPUT_CHARS]
            + "…[tronqué : restreignez la recherche (file, sheet) ou demandez moins de colonnes]"
        )
    return text


def build_tools(get_catalog: Callable[[], Catalog]) -> list[StructuredTool]:
    """The agent's tools over the analyses. `get_catalog` is called at use time, once the catalog is loaded.

    Errors (unknown file, column...) come back as text the model can act on instead of raising."""

    def guarded(function: Callable) -> Callable:
        def run(**kwargs) -> str:
            try:
                return _render(function(get_catalog(), **kwargs))
            except CatalogError as error:
                return f"Erreur : {error}"

        return run

    specs = [
        (
            "list_files",
            "Liste les fichiers à ta portée avec leur état d'analyse et leurs feuilles "
            "(nombre de lignes et de colonnes). À utiliser pour voir ce qui existe ou quand la question "
            "porte sur l'ensemble des fichiers.",
            NoArgs,
            lambda catalog: catalog.list_files(),
        ),
        (
            "search",
            "Recherche intelligente dans les analyses : trouve les colonnes et feuilles pertinentes pour une question "
            "(noms de colonnes, valeurs fréquentes, noms de fichiers/feuilles ; tolère accents, pluriels, fautes, "
            "synonymes français/anglais). Commence presque toujours par là.",
            SearchArgs,
            lambda catalog, query, file=None, limit=8: catalog.search(query, file, limit),
        ),
        (
            "search_values",
            "Trouve dans quelles colonnes apparaît une valeur précise (nom, ville, produit, année...). "
            "Ne regarde que les valeurs les plus fréquentes et les exemples de chaque colonne : un résultat vide "
            "ne prouve pas que la valeur est absente du fichier.",
            SearchValuesArgs,
            lambda catalog, value, file=None: catalog.search_values(value, file),
        ),
        (
            "describe_sheet",
            "Décrit une feuille : toutes ses colonnes (type, vides, distincts, min/max/moyenne, valeurs fréquentes) "
            "et un aperçu de ses 10 premières lignes.",
            DescribeSheetArgs,
            lambda catalog, file, sheet=None: catalog.describe_sheet(file, sheet),
        ),
        (
            "describe_column",
            "Profil complet d'une colonne : type, vides, distincts, statistiques (min, max, somme, moyenne, "
            "écart-type, médiane, quartiles), dates min/max, longueurs, valeurs les plus fréquentes, exemples.",
            DescribeColumnArgs,
            lambda catalog, file, column, sheet=None: catalog.describe_column(file, column, sheet),
        ),
    ]
    return [
        StructuredTool.from_function(func=guarded(function), name=name, description=description, args_schema=schema)
        for name, description, schema, function in specs
    ]
