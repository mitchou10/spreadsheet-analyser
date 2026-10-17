# Requêtes SQL sur les vraies données

L'agent ne lit jamais les lignes d'un fichier lui-même. Pour calculer (« total par région », « combien de lignes
où… », « top 5 », une jointure entre deux fichiers), il écrit du SQL avec l'outil `query_data`, qu'un worker exécute sur
une copie typée des feuilles.

| Qui | Rôle |
|---|---|
| `analysis-worker` | À l'analyse d'un fichier, écrit aussi une copie **Parquet** de chaque feuille (voir [analyse-json.md](analyse-json.md)). |
| **`query-worker`** | Exécute les requêtes (file Celery `query`). Même image que l'`analysis-worker`, mais ses propres processus : une question n'attend pas derrière l'analyse d'un gros fichier. |
| backend | Décide ce qu'une requête peut lire, garde la requête et son résultat (`sql_queries`). |
| `agent-worker` | Écrit le SQL (outil `query_data`) et attend le résultat. Ne calcule rien. |

Les workers ne parlent ni entre eux ni à la base : tout passe par le backend avec le jeton interne.

## Le parcours d'une requête

1. L'agent appelle `query_data(sql, files?)`. Les fichiers à ouvrir sont ceux dont le SQL écrit le schéma (`f1.`,
   `f2.`…) plus ceux de `files`.
2. `POST /api/internal/runs/{run_id}/queries` : le backend vérifie que le run est en cours et que chaque fichier est **dans
   le périmètre du run** (donc lisible par la personne qui pose la question) et **analysé**. Il enregistre la requête
   (`queued`) et l'envoie au `query-worker`.
3. Le worker télécharge le Parquet des feuilles de ces fichiers (et d'eux seuls) dans un dossier privé, exécute la
   requête et renvoie un résultat borné (`completed`), ou une erreur avec la liste des tables utilisables (`failed`).
4. L'agent interroge `GET /api/internal/queries/{id}` toutes les demi-secondes, jusqu'à 60 secondes.

Le SQL et le résultat apparaissent dans le bloc « Sources et outils » sous la réponse : chaque chiffre se vérifie.

## Nommer les tables

Chaque fichier est un **schéma** nommé par sa référence (`f1`, `f2`…, celles de `list_files`) et chaque feuille une
**table** de ce schéma, nommée comme dans le fichier (un CSV : son nom sans extension) :

```sql
SELECT c."nom", ROUND(SUM(v."montant"), 2) AS total
FROM f1."Ventes" v
JOIN f2."Clients" c ON c."id" = v."client_id"
GROUP BY 1
ORDER BY total DESC
```

Les jointures entre fichiers marchent donc de la même façon qu'entre deux feuilles. Une requête ouvre au plus 10 fichiers.

## Les types

L'analyse a déjà trouvé le type de chaque colonne. La copie Parquet garde ce type (`BIGINT`, `DOUBLE`, `BOOLEAN`,
`DATE`, `TIMESTAMP`, `TIME`, `VARCHAR`) **seulement si toutes les cellules qui ont une valeur sont de ce type** ; sinon la
colonne entière est du texte (`VARCHAR`), pour ne jamais perdre une valeur à cause d'une conversion (l'agent utilise
`TRY_CAST`). Les cellules en erreur (`#N/A`, `#DIV/0!`…) deviennent `NULL` dans une colonne typée. Excel n'a pas de type
« date seule » : ses dates sont des `TIMESTAMP`. Une feuille tronquée par l'analyse (plus d'un million de lignes) l'est
aussi dans le Parquet.

## Ce qui est interdit

Le SQL est écrit par un modèle : rien n'y est de confiance.

- **Une seule instruction, et un `SELECT`** (éventuellement avec `WITH`). `COPY`, `ATTACH`, `INSTALL`, `LOAD`, `SET`,
  `PRAGMA`, `CREATE`, `INSERT`, `DROP`, `EXPLAIN`, `CALL`… sont refusés avant d'être exécutés.
- **DuckDB est verrouillé avant la requête** : aucun accès aux fichiers ou au réseau en dehors du dossier privé de la
  requête (qui ne contient que les Parquet des fichiers autorisés), et la configuration ne peut plus changer. Les
  variables d'environnement (clés S3…) et les variables Python ne sont pas lisibles, `query()` n'exécute que des `SELECT`.
- **Bornes** : mémoire (au-delà DuckDB écrit sur disque, puis échoue la requête, pas le worker), threads, durée (la
  requête est interrompue), lignes rendues, taille du résultat, volume de données téléchargé.

Ces refus sont testés (`analysis-worker/tests/test_query_engine.py`) : lecture de `/etc/passwd`, `glob`, `getenv`,
variables Python, requêtes imbriquées, requête infinie, trop de mémoire, trop de temps.

## Limites (variables du `query-worker`)

| Variable | Défaut | Effet |
|---|---|---|
| `QUERY_MAX_ROWS` | 200 | Lignes rendues ; au-delà, `truncated`. La requête peut lire des millions de lignes : l'agent agrège. |
| `QUERY_TIMEOUT_SECONDS` | 30 | Durée maximale d'une requête. |
| `QUERY_MEMORY_LIMIT` | 512MB | Mémoire de DuckDB avant d'écrire sur disque. |
| `QUERY_THREADS` | 2 | Threads de DuckDB. |
| `QUERY_MAX_TABLE_BYTES` | 500 Mo | Parquet téléchargés pour une requête. |
| `QUERY_MAX_FILES` | 10 | Fichiers ouverts par une requête. |
| `QUERY_MAX_RESULT_CHARS` | 200 000 | Taille du résultat avant coupe. |

L'agent ne voit que ~5 000 caractères du résultat : il agrège, et la coupe lui est signalée.

## Fichiers déjà analysés

Un fichier analysé avant l'arrivée du SQL n'a pas de Parquet : la requête répond « relancer l'analyse », et l'analyse
s'obtient avec la route habituelle (`POST /api/files/{id}/analysis`).
