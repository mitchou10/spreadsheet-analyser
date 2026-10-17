"""Text normalisation shared by indexing and querying: accents, case, plurals, snake/camelCase, stop words."""

import re
import unicodedata

# Bump whenever tokenisation changes (stop words, stemming, synonyms, folding): a persisted search index
# built with another version is ignored by the agent, which then falls back to indexing in memory.
TOKENIZER_VERSION = 1

STOPWORDS = frozenset(
    "le la les l de du des d un une et ou the of and a to in en pour par sur dans quel quelle quels quelles est "
    "sont au aux avec ce cette ces qui que quoi where what which is are for with ma mon mes je tu il nous vous "
    "y a-t-il combien donne donnez moi me te se s c j n t qu".split()
)

# Words that mean (nearly) the same thing in spreadsheets, French and English. A query for one finds columns
# named with another. Matched on stems, see _stem().
SYNONYM_GROUPS = [
    "montant amount somme total prix price cout cost tarif valeur value revenue ca chiffre affaire turnover",
    "vente sale",
    "date jour day datetime horodatage timestamp",
    "mois month periode period",
    "annee year millesime",
    "client customer acheteur buyer consommateur",
    "produit product article item reference sku",
    "region zone area secteur territoire",
    "ville city commune localite",
    "pays country nation",
    "nom name libelle label designation intitule titre title",
    "prenom firstname givenname",
    "quantite qte quantity qty nombre nb count volume",
    "salaire salary remuneration paie pay traitement",
    "depense expense charge frais",
    "budget objectif target goal cible",
    "email mail courriel adresse-mail",
    "telephone tel phone mobile portable",
    "adresse address rue street",
    "statut status etat state",
    "id identifiant identifier code numero number num",
    "employe employee salarie agent personnel collaborateur staff",
    "categorie category type famille family",
    "marge margin benefice profit",
    "remise discount reduction promo rabais",
    "taux rate pourcentage percent percentage pct",
]

_TYPE_WORDS = {
    "integer": ["nombre", "entier", "number", "integer", "numerique", "numeric"],
    "number": ["nombre", "decimal", "number", "numerique", "numeric", "float"],
    "text": ["texte", "text", "chaine", "string", "libelle"],
    "boolean": ["booleen", "boolean", "oui", "non", "vrai", "faux"],
    "date": ["date", "jour"],
    "datetime": ["date", "datetime", "heure", "horodatage"],
    "time": ["heure", "time", "duree"],
}


def fold(text: str) -> str:
    """Lower-case without accents: 'Région' -> 'region'."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).lower()


def canon(text: str) -> str:
    """Comparison form for whole values: 'Île-de-France' and 'ile de france' become the same string."""
    return " ".join(re.findall(r"[a-z0-9]+", fold(str(text))))


def _stem(token: str) -> str:
    """Deliberately tiny: only plurals, because the point is consistency between query and index."""
    if len(token) > 3 and token.endswith(("s", "x")):
        return token[:-1]
    return token


def tokenize(text: str, keep_stopwords: bool = False) -> list[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(text))  # camelCase -> camel Case, before folding
    words = re.findall(r"[a-z0-9]+", fold(spaced))
    return [_stem(word) for word in words if keep_stopwords or word not in STOPWORDS]


def _build_synonyms() -> dict[str, frozenset[str]]:
    table: dict[str, set[str]] = {}
    for group in SYNONYM_GROUPS:
        stems = {stem for word in group.split() for stem in tokenize(word.replace("-", " "), keep_stopwords=True)}
        for stem in stems:
            table.setdefault(stem, set()).update(stems - {stem})
    return {stem: frozenset(others) for stem, others in table.items()}


SYNONYMS = _build_synonyms()


def type_tokens(column_type: str) -> list[str]:
    return [stem for word in _TYPE_WORDS.get(column_type, []) for stem in tokenize(word, keep_stopwords=True)]
