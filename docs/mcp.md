# Serveur MCP

Analyser des fichiers Excel/CSV depuis un agent (Claude Code, un IDE, un autre service) avec un client
[MCP](https://modelcontextprotocol.io/) : on envoie des fichiers et une question, on lit la réponse, comme dans le
chat. C'est l'[analyse éphémère](ephemeral-analysis.md) en outils MCP : mêmes règles, mêmes données, rien n'est gardé
au-delà de `ttl_hours`.

Le serveur tourne dans le backend, en Streamable HTTP sous **`/mcp`** (par exemple
`https://<hôte>/mcp`). `MCP_ENABLED=false` le désactive.

Le guide d'utilisation (adresse, connexion, commandes, outils, déroulé, limites) est un fichier markdown du backend,
`backend/app/mcp/guide.md`. Il est affiché dans l'application (cliquer sur la version, en bas à gauche de la barre
latérale, onglet « Connecter un agent (MCP) ») et servi tel quel, avec la vraie adresse du serveur, par
`GET /api/help/mcp`. Cette page-ci est la référence pour ceux qui déploient et exploitent le serveur.

## Authentification

Comme le reste de l'API : un **jeton d'accès Keycloak** en `Authorization: Bearer <jeton>`, vérifié auprès de
Keycloak (`userinfo`). Chaque analyse appartient à l'identité du jeton, et personne d'autre ne la voit.

- **Un client MCP qui sait faire OAuth** (Claude Code, etc.) n'a rien à configurer : sans jeton, `/mcp` répond 401 avec
  l'adresse de `/.well-known/oauth-protected-resource/mcp`, qui désigne le realm Keycloak ; le client fait la
  connexion (code + PKCE) tout seul.
- **Un script ou un service** prend un jeton d'un client Keycloak en `client_credentials` (compte de service) et le
  présente en en-tête.

Le client Keycloak utilisé pour OAuth doit accepter l'URL de rappel du client MCP. Le jeton n'est pas lu dans un cookie :
une page web ne peut pas faire appeler ce serveur au nom d'un navigateur.

## Déclarer le serveur dans un client

```bash
# Claude Code
claude mcp add --transport http spreadsheet-analyser https://<hôte>/mcp
# ou, avec un jeton déjà obtenu
claude mcp add --transport http spreadsheet-analyser https://<hôte>/mcp --header "Authorization: Bearer $TOKEN"
```

```json
{ "mcpServers": { "spreadsheet-analyser": {
    "type": "http", "url": "https://<hôte>/mcp",
    "headers": { "Authorization": "Bearer <jeton>" } } } }
```

## Outils

| Outil | Rôle |
|---|---|
| `analyze_files(files, query, model?, ttl_hours?)` | envoie les fichiers **et** la question en un appel |
| `ask_known_files(file_hashes, query, model?, ttl_hours?)` | pose une question sur des fichiers **déjà analysés**, désignés par leur sha256, sans les renvoyer |
| `ask(analysis_id, query, model?)` | autre question sur les mêmes fichiers (ou première question si l'analyse n'était pas prête) |
| `get_run(run_id)` | statut puis réponse : texte (markdown), graphiques, trace |
| `get_analysis(analysis_id)` | état de la pré-analyse des fichiers |
| `delete_analysis(analysis_id)` | supprime tout de suite |

`files` est une liste de `{"name": "ventes.xlsx", "content_base64": "<fichier en base64>", "mimetype": "<facultatif>"}`
(csv, xlsx, xls, ods ; 20 fichiers au plus).

### Déroulé

1. `analyze_files` crée l'analyse, puis **attend** la pré-analyse des fichiers (`MCP_PREANALYSIS_WAIT_SECONDS`, 30 s).
   Si elle est finie, il lance la question et renvoie `{"analysis_id", "run_id", "status": "ready"}`. Sinon il renvoie
   `{"analysis_id", "status": "processing"}` : appelez `ask` quand `get_analysis` dit `ready`.
2. `get_run(run_id)` toutes les quelques secondes jusqu'à `completed`, `failed` (voir `error`) ou `cancelled`.
3. La réponse contient `answer` (le même texte que dans le chat) et `charts` : chaque graphique avec son
   `image_base64` (PNG) si l'image fait au plus `MCP_MAX_CHART_BYTES` (2 Mio), sinon une `url` à lire avec le même jeton.
   Dans `answer`, les images sont remplacées par `[graphique : <titre>]`.
4. `ask` pour une autre question (un run à la fois : 409 tant que le précédent n'est pas fini), `delete_analysis` pour
   finir.

### Fichiers déjà analysés : `ask_known_files`

Chaque fichier d'une analyse a son `sha256` (dans les résultats de `analyze_files` et de `get_analysis`). Pour reposer
une question sur les mêmes fichiers dans une autre analyse, sans les renvoyer :

```json
{ "tool": "ask_known_files",
  "arguments": { "file_hashes": ["<sha256 de ventes.csv>", "<sha256 de stock.csv>"], "query": "…" } }
```

- Si tous les fichiers sont connus, les fichiers sont copiés côté serveur, leur analyse est reprise (prête tout de
  suite) et la question démarre, comme avec `analyze_files` : `{"analysis_id", "run_id", …}`.
- Si l'un d'eux ne l'est pas, **rien n'est créé** et l'outil répond une erreur 404 avec `missing_hashes` et un `prompt`
  qui dit quoi faire : envoyer ces fichiers-là avec `analyze_files`, avec la même question. Les fichiers dont le hash
  n'est pas listé sont connus.
- Est « connu » un fichier que la personne peut lire (les siens, ceux qu'on a partagés avec elle, ses autres analyses
  éphémères) et dont l'analyse est prête. Un hash seul ne donne jamais accès au fichier de quelqu'un d'autre : il est
  alors traité comme inconnu. Un fichier expiré ou supprimé n'est plus connu.

Les erreurs que le modèle peut corriger (fichier d'un type non accepté, base64 invalide, modèle inconnu, analyse
introuvable, run déjà en cours) sont renvoyées dans le résultat : `{"error": "…", "status_code": 422}`.

## Limites

- Les fichiers voyagent en base64 dans l'appel : `MCP_MAX_UPLOAD_BYTES` (10 Mio) en tout une fois décodés. Au-delà,
  utilisez la route REST `POST /api/ephemeral/analyses`, puis `ask` / `get_run` avec l'`analysis_id` obtenu.
- Même durée de vie que l'analyse éphémère : `ttl_hours` après la fin du dernier run (24 h par défaut).

## Réglages

| Variable | Défaut | Rôle |
|---|---|---|
| `MCP_ENABLED` | `true` | monte le serveur sous `/mcp` |
| `MCP_PREANALYSIS_WAIT_SECONDS` | `30` | attente de `analyze_files` avant de rendre la main |
| `MCP_MAX_UPLOAD_BYTES` | 10 Mio | taille totale des fichiers d'un appel |
| `MCP_MAX_CHART_BYTES` | 2 Mio | taille maximale d'un graphique renvoyé en base64 |

## Déploiement

L'ingress du chart envoie `/mcp` et `/.well-known/oauth-protected-resource` au backend (`global.ingress.hosts` de
`helm/values/common-values.yaml`). Une liste Helm est **remplacée**, pas fusionnée : si le fichier de valeurs de
l'environnement redéfinit `global.ingress.hosts`, il doit reprendre ces deux chemins, sinon `/mcp` tombe sur le frontend.
