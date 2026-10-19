# Analyse éphémère

Analyser un ou plusieurs fichiers Excel/CSV **sans rien garder** : on envoie les fichiers, on attend leur
pré-analyse, on pose une question, on lit la réponse. Tout est supprimé automatiquement après un délai.

Les routes sont sous `/api/ephemeral`. Elles demandent la même authentification que le reste de l'API (session
Keycloak, ou `Authorization: Bearer <jeton>`), et une analyse n'est visible que par celui qui l'a créée.

## Déroulé

```bash
# 1. Envoyer les fichiers (champ multipart « files » : csv, xlsx, xls, ods). `ttl_hours` est facultatif.
curl -X POST https://<hôte>/api/ephemeral/analyses \
  -H "Authorization: Bearer $TOKEN" \
  -F files=@ventes.xlsx -F files=@stock.csv -F ttl_hours=24
# 202 {"id": "<analyse>", "status": "processing", "expires_at": "...",
#      "files": [{"id", "name", "size_bytes", "sha256", "status": "pending", "error": null}]}

# 2. Attendre la pré-analyse : status passe à "ready" (ou "partial" / "failed")
curl https://<hôte>/api/ephemeral/analyses/<analyse> -H "Authorization: Bearer $TOKEN"

# 3. Poser la question : la réponse est le run à interroger
curl -X POST https://<hôte>/api/ephemeral/analyses/<analyse>/runs \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"query": "Chiffre d affaires par région en 2025 ?"}'
# 202 {"id": "<run>", "status": "queued", ...}

# 4. Lire le run jusqu'à un état terminal (completed, failed, cancelled)
curl https://<hôte>/api/ephemeral/runs/<run> -H "Authorization: Bearer $TOKEN"
# {"id", "analysis_id", "status": "completed", "answer": "…", "trace": {…}, "model", "created_at",
#  "finished_at", "error": null}

# 5. Si la réponse a des graphiques : `charts` les liste, et `url` donne l'image (PNG, même authentification)
curl https://<hôte>/api/ephemeral/runs/<run>/charts/<graphique> -H "Authorization: Bearer $TOKEN" -o graphique.png

# 6. Facultatif : tout supprimer tout de suite
curl -X DELETE https://<hôte>/api/ephemeral/analyses/<analyse> -H "Authorization: Bearer $TOKEN"
```

On peut poser plusieurs questions sur les mêmes fichiers (un run à la fois : 409 tant que le précédent n'est pas
fini). `answer` est le même texte que dans le chat (markdown) ; `trace` dit comment il a été produit. Les images de graphiques
que ce texte affiche pointent vers `/api/ephemeral/runs/<run>/charts/<graphique>`, la route de l'étape 5, et non vers
celles du chat. Un graphique n'existe que tant que l'analyse n'a pas expiré : récupérez-le avant.

## Modèle

Le champ `model` de la question (`POST /api/ephemeral/analyses/<analyse>/runs`) est **facultatif**. Sans lui, le
backend prend le premier modèle de conversation que le fournisseur propose (`OPENAI_BASE_URL`) : il n'y a pas de
modèle par défaut écrit en dur. Si vous en donnez un, il doit figurer dans `GET /api/models` (sinon 422) ; il est
utilisé pour cette question et devient celui des questions suivantes de l'analyse, tant que vous n'en donnez pas un
autre. Si le fournisseur est injoignable et qu'aucun modèle n'est donné, la question échoue avec un message
explicite. `LLM_ALLOWED_MODELS` restreint la liste des modèles proposés.

## États

| `status` de l'analyse | Sens |
|---|---|
| `processing` | au moins un fichier est encore en cours de pré-analyse : poser une question répond 409 |
| `ready` | tous les fichiers sont prêts |
| `partial` | certains fichiers n'ont pas pu être analysés (`files[].error`) : la question ne porte que sur les autres |
| `failed` | aucun fichier n'a pu être analysé : poser une question répond 422 |

## Durée de vie

`ttl_hours` (défaut `EPHEMERAL_DEFAULT_TTL_HOURS` = 24, maximum `EPHEMERAL_MAX_TTL_HOURS` = 720) est la durée de
conservation **après la fin du dernier run** (réussi, échoué ou annulé) : `expires_at` avance au lancement de chaque
question et de nouveau à sa fin, quelle qu'ait été sa durée. Une analyse dont un run est en cours n'est jamais purgée. Passé ce délai, les fichiers (S3), les
analyses, la conversation, les requêtes et les graphiques sont supprimés, et les routes répondent 404.

La purge tourne dans le backend toutes les `EPHEMERAL_PURGE_INTERVAL_SECONDS` secondes (600 par défaut ; un verrou
Postgres évite que plusieurs réplicas la fassent en même temps). Avec `0`, elle est désactivée et un planificateur peut
appeler `POST /api/internal/ephemeral/purge` (jeton interne).

## Ce qui est différent d'une collection

- Elle n'apparaît ni dans la liste des collections, ni dans celle des conversations, ni dans l'administration, ni dans
  l'index de recherche de la personne, ni dans la « vue d'ensemble du compte » de l'assistant.
- Elle n'est pas partageable : seul son créateur la lit.
- Un contenu déjà analysé (même sha256 et même extension) réutilise le résultat existant : la pré-analyse est alors
  immédiate (voir `ANALYSIS_REUSE`).

## Limites

`EPHEMERAL_MAX_FILES` fichiers (20) par analyse, `MAX_UPLOAD_BYTES` (50 Mio) par fichier. Un fichier d'un autre type
répond 415.
