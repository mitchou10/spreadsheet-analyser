# Analyse d'un fichier : le contenu de `analyse.json`

Pour chaque version d'un fichier, l'`analysis-worker` produit un profil statistique du contenu et l'enregistre
dans S3 (RustFS en local). Ce document décrit ce profil.

Code : `worker/app/analysis/` (`readers.py` lit les fichiers, `profile.py` calcule les statistiques,
`analyzer.py` assemble le résultat).

## Où il est enregistré

```
<collection_id>/<file_id>/versions/<version>/<nom-du-fichier>   le fichier brut importé
<collection_id>/<file_id>/versions/<version>/analyse.json       le profil décrit ici
```

- Une analyse porte sur **une version** du fichier. Importer une nouvelle version crée une nouvelle analyse,
  l'`analyse.json` des versions précédentes reste en place.
- Le worker écrit l'objet, puis prévient le backend, qui ne l'accepte que s'il est exactement à la clé attendue.
  La clé est aussi enregistrée dans `analyses.s3_key`.
- Le résultat se lit via l'API : `GET /api/files/{file_id}/analysis` renvoie le statut (`pending`, `processing`,
  `ready`, `error`, `stopped`), l'erreur éventuelle et le contenu d'`analyse.json` dans `result` (null tant que
  l'analyse n'est pas `ready`).

## Structure

```
analyse.json
├── schema_version        1
├── file                  nom, format, taille
├── analyzed_at           date de l'analyse (ISO 8601, UTC)
├── summary               totaux
├── warnings[]            avertissements au niveau du fichier
└── sheets[]              une entrée par feuille (un CSV a une seule feuille)
    ├── …                 métadonnées de la feuille
    ├── columns[]         une entrée par colonne : le profil statistique
    └── preview[][]       les 10 premières lignes de données
```

### Fichier

| Champ | Contenu |
|---|---|
| `schema_version` | Version du format de ce document (`1`). |
| `file.name` | Nom du fichier importé. |
| `file.format` | `csv`, `xlsx`, `xls` ou `ods` (`.xlsm` est compté comme `xlsx`). |
| `file.size_bytes` | Taille en octets. |
| `analyzed_at` | Date et heure de l'analyse. |
| `summary.sheets` | Nombre de feuilles analysées. |
| `summary.rows` | Nombre total de lignes de données, toutes feuilles confondues. |
| `summary.truncated` | `true` si au moins une feuille a été tronquée. |
| `warnings` | Par exemple `"The file contains no data"` ou `"Only the first 100 sheets were analyzed"`. |

### Feuille

| Champ | Contenu |
|---|---|
| `index`, `name` | Position et nom de la feuille. Pour un CSV, le nom est celui du fichier sans extension. |
| `hidden` | `true` si la feuille est masquée (xlsx, xls). |
| `rows` | Nombre de lignes de données. L'en-tête n'est pas comptée et les lignes entièrement vides sont ignorées. |
| `header_detected` | `true` si la première ligne a été reconnue comme un en-tête. |
| `truncated` | `true` si la feuille dépasse la limite de lignes : seules les premières ont été analysées. |
| `columns` | Profil de chaque colonne, voir ci-dessous. |
| `preview` | Les 10 premières lignes de données (valeurs vides = `null`, dates en ISO 8601). |
| `warnings` | Par exemple `"Only the first 500 columns were analyzed"`. |

**Détection de l'en-tête.** La première ligne est un en-tête si elle ne contient que du texte (≤ 100 caractères),
remplit au moins la moitié de la largeur, et soit la ligne suivante contient autre chose que du texte (nombres,
dates…), soit tous les libellés sont distincts. Sinon les colonnes s'appellent `col_1`, `col_2`… Les noms vides
reçoivent aussi ce nom, et les doublons sont suffixés (`a`, `a_2`).

### Colonne

Champs présents pour toutes les colonnes :

| Champ | Contenu |
|---|---|
| `index`, `name` | Position (à partir de 0) et nom. |
| `type` | Type détecté, voir le tableau suivant. |
| `non_null` | Nombre de cellules renseignées. |
| `null` | Nombre de cellules vides (lignes plus courtes comprises). |
| `type_counts` | Nombre de cellules par nature, par exemple `{"number": 3, "text": 1}`. |
| `distinct` | Nombre de valeurs distinctes. Les cellules en erreur ne sont pas comptées. |
| `distinct_exact` | `false` si plus de 1 000 valeurs distinctes ont été vues : `distinct` est alors un minimum. |
| `sample_values` | Les 5 premières valeurs renseignées. |

Champs présents selon le contenu :

| Champ | Présent quand | Contenu |
|---|---|---|
| `numeric` | la colonne contient des nombres | `count`, `min`, `max`, `sum`, `mean`, `std` (écart-type d'échantillon), `median`, `p25`, `p75`, `quantiles_exact`. |
| `text` | la colonne contient du texte | `min_length`, `max_length` (en caractères, texte tronqué à 200). |
| `dates` | la colonne contient des dates | `min` et `max` (ISO 8601). |
| `top_values` | colonne `text`, `boolean`, `mixed` ou `integer` | Jusqu'à 10 valeurs les plus fréquentes : `[{"value": "Stylo", "count": 2}]`. Les valeurs sont toujours des chaînes (`"True"`, `"10"`). |
| `error_cells` | des cellules sont en erreur | Nombre de cellules `#DIV/0!`, `#N/A`, `#NAME?`, `#NULL!`, `#NUM!`, `#REF!`, `#VALUE!`. |

**Types (`type`)**

| Valeur | Signification |
|---|---|
| `integer` | Que des entiers. |
| `number` | Des nombres, au moins un à virgule. |
| `text` | Du texte. |
| `boolean` | Des booléens. |
| `date`, `datetime`, `time` | Dates, dates avec heure, heures. |
| `mixed` | Aucune nature ne représente au moins 95 % des valeurs renseignées. |
| `empty` | Aucune valeur renseignée. |
| `error` | Que des cellules en erreur. |

Les cellules en erreur ne comptent pas dans ce calcul : une colonne de nombres avec un `#DIV/0!` reste `number`.

**Statistiques numériques.** `min`, `max`, `sum`, `mean`, `std` et `count` sont exacts, calculés en une passe.
`median`, `p25` et `p75` viennent d'un échantillon de 2 000 valeurs : exacts tant que la colonne a au plus
2 000 nombres (`quantiles_exact: true`), sinon estimés. Les valeurs non finies sont ignorées.

## Ce qui est reconnu selon le format

| Format | Typage |
|---|---|
| `xlsx`, `xls`, `ods` | Types natifs des cellules (nombre, date, booléen, texte). Pour `xlsx`, ce sont les valeurs calculées en cache : une formule jamais calculée apparaît comme vide. |
| `csv` | Tout est du texte à l'origine, les types sont reconstruits prudemment : entiers et décimaux (virgule décimale acceptée si le séparateur n'est pas la virgule), dates `AAAA-MM-JJ`, `AAAA-MM-JJ hh:mm` et `JJ/MM/AAAA`, booléens `true/false/vrai/faux`. Un identifiant à zéros initiaux (`007`) reste du texte. L'encodage (UTF-8 ou Windows-1252) et le séparateur (`, ; tab |`) sont détectés. |

## Exemple

Fichier `ventes.csv` (séparateur `;`, décimales à virgule) :

```
produit;prix;quantite;date;actif;note
Stylo;1,50;10;01/02/2024;vrai;ok
Cahier;3,20;4;15/03/2024;faux;ok
Stylo;;7;20/04/2024;vrai;#N/A
Gomme;0,80;25;02/05/2024;vrai;ok
```

Résultat (colonnes `quantite` et `actif` omises, `preview` raccourci) :

```json
{
  "schema_version": 1,
  "file": { "name": "ventes.csv", "format": "csv", "size_bytes": 167 },
  "analyzed_at": "2026-10-17T15:30:00+00:00",
  "sheets": [
    {
      "index": 0,
      "name": "ventes",
      "hidden": false,
      "rows": 4,
      "header_detected": true,
      "truncated": false,
      "columns": [
        {
          "index": 0,
          "name": "produit",
          "type": "text",
          "non_null": 4,
          "null": 0,
          "type_counts": { "text": 4 },
          "distinct": 3,
          "distinct_exact": true,
          "sample_values": ["Stylo", "Cahier", "Stylo", "Gomme"],
          "text": { "min_length": 5, "max_length": 6 },
          "top_values": [
            { "value": "Stylo", "count": 2 },
            { "value": "Cahier", "count": 1 },
            { "value": "Gomme", "count": 1 }
          ]
        },
        {
          "index": 1,
          "name": "prix",
          "type": "number",
          "non_null": 3,
          "null": 1,
          "type_counts": { "number": 3 },
          "distinct": 3,
          "distinct_exact": true,
          "sample_values": [1.5, 3.2, 0.8],
          "numeric": {
            "count": 3,
            "min": 0.8,
            "max": 3.2,
            "sum": 5.5,
            "mean": 1.8333333333333335,
            "std": 1.2342339054382412,
            "median": 1.5,
            "p25": 1.15,
            "p75": 2.35,
            "quantiles_exact": true
          }
        },
        {
          "index": 3,
          "name": "date",
          "type": "date",
          "non_null": 4,
          "null": 0,
          "type_counts": { "date": 4 },
          "distinct": 4,
          "distinct_exact": true,
          "sample_values": ["2024-02-01", "2024-03-15", "2024-04-20", "2024-05-02"],
          "dates": { "min": "2024-02-01", "max": "2024-05-02" }
        },
        {
          "index": 5,
          "name": "note",
          "type": "text",
          "non_null": 4,
          "null": 0,
          "type_counts": { "text": 3, "error": 1 },
          "distinct": 1,
          "distinct_exact": true,
          "sample_values": ["ok", "ok", "#N/A", "ok"],
          "error_cells": 1,
          "text": { "min_length": 2, "max_length": 2 },
          "top_values": [{ "value": "ok", "count": 3 }]
        }
      ],
      "preview": [
        ["Stylo", 1.5, 10, "2024-02-01", true, "ok"],
        ["Stylo", null, 7, "2024-04-20", true, "#N/A"]
      ],
      "warnings": []
    }
  ],
  "warnings": [],
  "summary": { "sheets": 1, "rows": 4, "truncated": false }
}
```

## Limites

Elles bornent la mémoire et la taille du résultat, quelle que soit la taille du fichier. Chacune se règle par une
variable d'environnement du worker.

| Variable | Défaut | Effet |
|---|---|---|
| `ANALYSIS_MAX_FILE_BYTES` | 200 Mo | Fichier plus gros : analyse en `error`, sans téléchargement. |
| `ANALYSIS_MAX_UNCOMPRESSED_BYTES` | 2 Go | xlsx/ods dont le contenu décompressé dépasse cette taille (archive piégée) : `error`. |
| `ANALYSIS_MAX_SHEETS` | 100 | Feuilles au-delà ignorées (avertissement). |
| `ANALYSIS_MAX_ROWS_PER_SHEET` | 1 000 000 | Lignes au-delà ignorées, `truncated: true` : les statistiques portent sur les premières lignes. |
| `ANALYSIS_MAX_COLUMNS` | 500 | Colonnes au-delà ignorées (avertissement). |
| `ANALYSIS_MAX_DISTINCT` | 1 000 | Valeurs distinctes suivies par colonne avant de passer à `distinct_exact: false`. |
| `ANALYSIS_RESERVOIR_SIZE` | 2 000 | Taille de l'échantillon pour médiane et quartiles. |

## Ce qui n'est pas calculé

Corrélations entre colonnes, valeurs aberrantes, lignes en double, types métier (email, code postal, montant en
euros…), relations entre feuilles, formules, cellules fusionnées, graphiques. Les lignes entièrement vides au
milieu d'une feuille sont ignorées, donc la position d'une ligne dans le fichier n'est pas conservée.
