import json
from collections.abc import Callable
from typing import Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.agent.account import Account
from app.agent.catalog import Catalog, CatalogError
from app.agent.chart import ChartRunner
from app.agent.sql import SqlRunner
from app.backend_client import BackendError

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


class AccountFilesArgs(BaseModel):
    collection: str | None = Field(default=None, description="Limiter à une collection (son nom ou son id).")
    status: str | None = Field(
        default=None,
        description="Limiter à un état d'analyse : ready, pending, processing, error, stopped ou none (jamais analysé)",
    )
    limit: int = Field(default=50, ge=1, le=100, description="Nombre maximum de fichiers retournés.")


class QueryDataArgs(BaseModel):
    sql: str = Field(
        description='Une requête SQL DuckDB en lecture (SELECT, WITH). Nomme chaque table f1."Feuille" : le schéma est '
        "la référence du fichier, la table est le nom exact de la feuille, entre guillemets doubles (colonnes aussi "
        'si elles ont des espaces ou des accents). Plusieurs fichiers : jointure entre f1."A" et f2."B".'
    )
    files: list[str] | None = Field(
        default=None, description="Fichiers à ouvrir (réf. f1, id ou nom). Inutile si le SQL utilise f1., f2.…"
    )


class CreateChartArgs(BaseModel):
    query_id: str = Field(
        description="Le `query_id` rendu par query_data : le graphique représente le résultat de cette requête."
    )
    type: Literal["bar", "barh", "line", "area", "pie", "scatter", "histogram"] = Field(
        description="bar (barres), barh (barres horizontales : noms longs, classements), line (évolution), area, "
        "pie (parts d'un tout, peu de parts), scatter (deux nombres), histogram (répartition d'une colonne numérique)."
    )
    x: str = Field(
        description="Colonne du résultat : catégories (bar, pie), axe horizontal (line, area, scatter) ou valeurs."
    )
    y: list[str] | None = Field(
        default=None,
        description="Colonne(s) numérique(s) à tracer (jusqu'à 6). Inutile pour un histogram ; un seul pour pie.",
    )
    color: str | None = Field(
        default=None,
        description="Colonne dont chaque valeur fait une série (avec un seul `y`), au lieu de plusieurs `y`.",
    )
    title: str = Field(
        description="Titre du graphique, en français, qui dit ce qu'on voit (ex : « Ventes par région en 2024 »)."
    )
    x_label: str | None = Field(default=None, description="Légende de l'axe horizontal (défaut : nom de la colonne).")
    y_label: str | None = Field(
        default=None, description="Légende de l'axe vertical (ex : « Chiffre d'affaires (€) »)."
    )
    stacked: bool = Field(default=False, description="Empiler les séries (bar, area).")
    sort: Literal["none", "x", "y_desc", "y_asc"] = Field(
        default="none",
        description="Ordre des catégories : tel que rendu, par x, ou par valeur décroissante/croissante.",
    )


class NoArgs(BaseModel):
    pass


def _draw_chart(
    runner: ChartRunner,
    query_id: str,
    type: str,
    x: str,
    title: str,
    y=None,
    color=None,
    x_label=None,
    y_label=None,
    stacked=False,
    sort="none",
) -> dict:  # noqa: A002
    """The description of the chart (kind, columns, title...) for the backend: only what was given."""
    given = {
        "type": type,
        "x": x,
        "y": y or [],
        "color": color,
        "title": title,
        "x_label": x_label,
        "y_label": y_label,
        "stacked": stacked,
        "sort": sort,
    }
    return runner.run(query_id, {key: value for key, value in given.items() if value not in (None, [])})


def _render(payload) -> str:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(text) > MAX_TOOL_OUTPUT_CHARS:
        text = (
            text[:MAX_TOOL_OUTPUT_CHARS]
            + "…[tronqué : restreignez la recherche (file, sheet) ou demandez moins de colonnes]"
        )
    return text


def build_tools(
    get_catalog: Callable[[], Catalog],
    get_account: Callable[[], Account],
    get_sql: Callable[[], SqlRunner],
    get_chart: Callable[[], ChartRunner],
) -> list[StructuredTool]:
    """The agent's tools. `get_catalog` and `get_account` are called at use time: the analyses are loaded once the
    run has started, and the account (a call to the backend) only if the agent asks about it.

    Errors (unknown file, column...) come back as text the model can act on instead of raising."""

    def guarded(function: Callable, source: Callable) -> Callable:
        def run(**kwargs) -> str:
            try:
                return _render(function(source(), **kwargs))
            except CatalogError as error:
                return f"Erreur : {error}"
            except BackendError as error:  # e.g. the account could not be read: say so rather than guess
                return f"Erreur : information indisponible pour le moment ({error}). Ne l'invente pas."

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
    sql_specs = [
        (
            "query_data",
            "Interroge les VRAIES DONNÉES des fichiers avec du SQL (DuckDB) : sommes, moyennes, comptages, filtres, "
            "regroupements, classements, jointures entre plusieurs fichiers. À utiliser dès qu'il faut calculer sur "
            "les lignes (total par région, nombre de lignes où..., top 5, évolution par mois...), ce que les "
            "analyses seules ne permettent pas. Lecture seule ; le résultat est limité à quelques centaines de "
            "lignes : agrège plutôt que de lister. Les cellules qui ne correspondent pas au type d'une colonne "
            "(ex. du texte dans une colonne de nombres) rendent toute la colonne VARCHAR : utilise TRY_CAST. "
            "En cas d'erreur, le message liste les tables et colonnes disponibles.",
            QueryDataArgs,
            lambda runner, sql, files=None: runner.run(sql, files),
        ),
    ]
    chart_specs = [
        (
            "create_chart",
            "Dessine un GRAPHIQUE à partir du résultat d'une requête déjà faite avec query_data (barres, barres "
            "horizontales, courbe, aires, camembert, nuage de points, histogramme). D'abord la requête, qui prépare "
            "les données (agrégées, triées, 40 catégories au plus), ensuite le graphique : passe son `query_id` et "
            "nomme les colonnes du résultat. Plusieurs graphiques sont possibles dans une réponse (6 au plus). "
            "Rend le markdown de l'image : insère-le tel quel dans ta réponse. Les graphiques servent à montrer, "
            "pas à décorer : n'en fais que si la question s'y prête ou si on te le demande.",
            CreateChartArgs,
            _draw_chart,
        ),
    ]
    account_specs = [
        (
            "account_overview",
            "Vue d'ensemble du COMPTE de l'utilisateur, quel que soit le périmètre de la question : combien de "
            "collections il possède et combien sont partagées avec lui, combien de fichiers, leur taille, combien "
            "sont analysés, en cours ou en erreur, et une ligne par collection (propriétaire, partage, dernier "
            "import). À utiliser pour « combien de collections / fichiers ai-je ? », « qu'est-ce que j'ai ? ».",
            NoArgs,
            lambda account: account.overview(),
        ),
        (
            "account_files",
            "Liste les fichiers du COMPTE de l'utilisateur (nom, collection, taille, date d'import, état d'analyse), "
            "du plus récent au plus ancien, même ceux qui ne sont pas dans le périmètre de la question. Filtrable "
            "par collection et par état d'analyse (ex : les fichiers en erreur). Pour le contenu d'un fichier, "
            "utilise plutôt les outils de recherche dans les analyses.",
            AccountFilesArgs,
            lambda account, collection=None, status=None, limit=50: account.files(collection, status, limit),
        ),
    ]
    return [
        StructuredTool.from_function(
            func=guarded(function, source), name=name, description=description, args_schema=schema
        )
        for specs_, source in (
            (specs, get_catalog),
            (sql_specs, get_sql),
            (chart_specs, get_chart),
            (account_specs, get_account),
        )
        for name, description, schema, function in specs_
    ]
