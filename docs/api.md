# Routes de l'API

Liste des routes du backend, générée depuis le document OpenAPI (`/api/openapi.json`, aussi lisible dans Swagger à
`/api/docs`). **Ne pas modifier à la main** : `cd backend && uv run python -m app.routes_doc ../docs/api.md`, un test
vérifie que ce fichier est à jour.

Accès : *public* (sans connexion), *connecté* (session Keycloak du navigateur, ou `Authorization: Bearer <jeton
Keycloak>`), *administrateur* (rôle `admin`), *jeton interne* (les workers, `INTERNAL_API_TOKEN`).


## Auth

Login/logout via Keycloak, session management.

| Méthode | Route | Description | Accès |
|---|---|---|---|
| GET | `/api/auth/login` | Redirect the browser to Keycloak's login page | public |
| GET | `/api/auth/callback` | Exchange the Keycloak authorization code for a session | public |
| POST | `/api/auth/token` | Password grant for non-browser clients (scripts, SDK) | public |
| POST | `/api/auth/refresh` | Refresh grant for non-browser clients (scripts, SDK) | public |
| POST | `/api/auth/logout` | End the BFF session and the Keycloak SSO session | connecté |
| GET | `/api/auth/me` | Return the current user's profile | connecté |

## Admin

Who has access to what (administrators only).

| Méthode | Route | Description | Accès |
|---|---|---|---|
| GET | `/api/admin/collections` | Every collection with its owner and who it is shared with | administrateur |
| GET | `/api/admin/people` | Every person (by email) with the collections they own or can read | administrateur |
| GET | `/api/admin/feedback` | Thumbs up/down given to the answers, latest first, with the exchange they are about | administrateur |
| GET | `/api/admin/usage` | Tokens consumed by everyone (or one person), per node, day, model and person | administrateur |
| POST | `/api/admin/collections/{collection_id}/access` | Give an email read access to any collection | administrateur |
| DELETE | `/api/admin/collections/{collection_id}/access/{email}` | Remove an email's read access to a collection | administrateur |
| POST | `/api/admin/collections/{collection_id}/search-index` | Rebuild a collection's saved search index from its analyses (backfill or repair) | administrateur |
| POST | `/api/admin/users/search-index` | Rebuild the saved search index of everything a person can read (by email) | administrateur |

## Collections

Collections, their files (upload) and sharing.

| Méthode | Route | Description | Accès |
|---|---|---|---|
| GET | `/api/collections` | Collections I own or that were shared with me | connecté |
| POST | `/api/collections` | Create a collection | connecté |
| GET | `/api/collections/{collection_id}` | Get a collection | connecté |
| PATCH | `/api/collections/{collection_id}` | Rename / describe a collection (owner only) | connecté |
| DELETE | `/api/collections/{collection_id}` | Delete a collection and its files (owner only) | connecté |
| GET | `/api/collections/{collection_id}/files` | Files of a collection with their analysis status | connecté |
| POST | `/api/collections/{collection_id}/files` | Upload one or more spreadsheets (multipart, field name 'files') - owner only | connecté |
| GET | `/api/collections/{collection_id}/access` | Who the collection is shared with | connecté |
| POST | `/api/collections/{collection_id}/access` | Share the collection (read-only) by email | connecté |
| DELETE | `/api/collections/{collection_id}/access/{email}` | Revoke an email's access | connecté |

## Conversations

Chat conversations and their messages (private to their creator): sending, running the assistant again, thumbs up/down on an answer, charts.

| Méthode | Route | Description | Accès |
|---|---|---|---|
| GET | `/api/conversations` | My conversations, most recently active first | connecté |
| POST | `/api/conversations` | Start a conversation, optionally on a given model | connecté |
| PATCH | `/api/conversations/{conversation_id}` | Rename a conversation or switch its model | connecté |
| DELETE | `/api/conversations/{conversation_id}` | Delete a conversation | connecté |
| GET | `/api/conversations/{conversation_id}/messages` | A page of messages, oldest first within the page | connecté |
| POST | `/api/conversations/{conversation_id}/messages` | Send a user message; the assistant's answer is produced asynchronously by a run | connecté |
| PUT | `/api/conversations/{conversation_id}/messages/{message_id}/feedback` | Thumbs up or down on an answer of the assistant (replaces the previous one) | connecté |
| DELETE | `/api/conversations/{conversation_id}/messages/{message_id}/feedback` | Remove my thumbs up/down on an answer | connecté |
| POST | `/api/conversations/{conversation_id}/runs/retry` | Run the assistant again on the last message (retry a failed run, or replace the last answer) | connecté |
| GET | `/api/conversations/{conversation_id}/active-run` | The run currently in progress, if any (null otherwise) | connecté |
| GET | `/api/conversations/{conversation_id}/messages/{message_id}/charts/{chart_id}` | The image of a chart of an answer (PNG), only for the owner of the conversation | connecté |

## Ephemeral analysis

Upload spreadsheets, wait for their pre-analysis, ask a question: nothing is kept.

| Méthode | Route | Description | Accès |
|---|---|---|---|
| POST | `/api/ephemeral/analyses` | Upload one or more spreadsheets for an analysis that is deleted after a while (multipart, field 'files') | connecté |
| GET | `/api/ephemeral/analyses/{analysis_id}` | State of the pre-analysis of the files | connecté |
| DELETE | `/api/ephemeral/analyses/{analysis_id}` | Delete the files and results now | connecté |
| POST | `/api/ephemeral/analyses/{analysis_id}/runs` | Ask a question about the files; returns the run to poll | connecté |
| GET | `/api/ephemeral/runs/{run_id}` | Status of a run and, once completed, the assistant's answer | connecté |
| GET | `/api/ephemeral/runs/{run_id}/charts/{chart_id}` | The image of a chart drawn by a run (PNG) | connecté |

## Models

LLMs available to the assistant.

| Méthode | Route | Description | Accès |
|---|---|---|---|
| GET | `/api/models` | LLMs the assistant can use (as listed by the OpenAI-compatible provider) | connecté |

## Runs

Asynchronous assistant runs started by a message.

| Méthode | Route | Description | Accès |
|---|---|---|---|
| GET | `/api/runs/{run_id}` | Status of a run | connecté |
| POST | `/api/runs/{run_id}/cancel` | Cancel a queued or running run | connecté |

## Files

Download, delete and analysis control of a single file.

| Méthode | Route | Description | Accès |
|---|---|---|---|
| GET | `/api/files/{file_id}/download` | Download the current version of a file | connecté |
| DELETE | `/api/files/{file_id}` | Delete a file (owner only) | connecté |
| GET | `/api/files/{file_id}/analysis` | Latest analysis of the file's current version, with its result | connecté |
| POST | `/api/files/{file_id}/analysis` | (Re)queue an analysis of the current version | connecté |
| POST | `/api/files/{file_id}/analysis/stop` | Stop the running analysis | connecté |

## Health

Liveness/readiness of the API and its dependencies, and its version.

| Méthode | Route | Description | Accès |
|---|---|---|---|
| GET | `/api/health` | Perform a health check | public |
| GET | `/api/version` | Version of the application (for signed-in users) | connecté |

## Help

Guides in markdown (how to connect an agent over MCP).

| Méthode | Route | Description | Accès |
|---|---|---|---|
| GET | `/api/help/mcp` | How to connect an agent to the MCP server (markdown) | public |

## Internal (SQL queries)

| Méthode | Route | Description | Accès |
|---|---|---|---|
| POST | `/api/internal/runs/{run_id}/queries` | The agent asks for a SQL query over some files of its run (poll GET /queries/{id}) | jeton interne |
| GET | `/api/internal/queries/{query_id}` | State and result of a SQL query | jeton interne |
| GET | `/api/internal/queries/{query_id}/context` | The SQL and the files a query may read (query worker) | jeton interne |
| POST | `/api/internal/queries/{query_id}/start` | queued -> running (409 if taken or cancelled) | jeton interne |
| POST | `/api/internal/queries/{query_id}/complete` | Store the result, running -> completed | jeton interne |
| POST | `/api/internal/queries/{query_id}/fail` | Mark the query failed, with what could have been queried | jeton interne |

## Internal (charts)

| Méthode | Route | Description | Accès |
|---|---|---|---|
| POST | `/api/internal/runs/{run_id}/charts` | The agent asks for a chart of the result of a query of its run (poll GET /charts/{id}) | jeton interne |
| GET | `/api/internal/charts/{chart_id}` | State of a chart, and the markdown that shows it | jeton interne |
| GET | `/api/internal/charts/{chart_id}/context` | What to draw, from which query, and where to write it | jeton interne |
| POST | `/api/internal/charts/{chart_id}/start` | queued -> running (409 if taken) | jeton interne |
| POST | `/api/internal/charts/{chart_id}/complete` | The PNG is written: running -> completed | jeton interne |
| POST | `/api/internal/charts/{chart_id}/fail` | Mark the chart failed, with the columns of the query | jeton interne |

## Internal (worker)

| Méthode | Route | Description | Accès |
|---|---|---|---|
| POST | `/api/internal/ephemeral/purge` | Delete the ephemeral analyses past their expiry (for a scheduler) | jeton interne |
| GET | `/api/internal/runs/{run_id}/context` | Conversation history and scope the run works on | jeton interne |
| GET | `/api/internal/runs/{run_id}/files` | Files the agent may search, with their latest analysis | jeton interne |
| GET | `/api/internal/runs/{run_id}/account` | Everything the requester can read: collections, files, states | jeton interne |
| POST | `/api/internal/runs/{run_id}/start` | queued -> running (409 if cancelled meanwhile) | jeton interne |
| POST | `/api/internal/runs/{run_id}/complete` | Store the assistant reply, running -> completed | jeton interne |
| POST | `/api/internal/runs/{run_id}/usage` | Tokens consumed by the run's LLM calls, whatever the run's final status | jeton interne |
| POST | `/api/internal/runs/{run_id}/fail` | Mark the run failed | jeton interne |
| GET | `/api/internal/conversations/{conversation_id}/messages` | Full history of a conversation, oldest first | jeton interne |
| GET | `/api/internal/analyses/{analysis_id}/context` | Where to read the file and write analyse.json | jeton interne |
| POST | `/api/internal/analyses/{analysis_id}/start` | pending -> processing (409 if stopped meanwhile) | jeton interne |
| POST | `/api/internal/analyses/{analysis_id}/complete` | analyse.json is written: processing -> ready | jeton interne |
| POST | `/api/internal/analyses/{analysis_id}/fail` | Mark the analysis failed | jeton interne |
| GET | `/api/internal/collections/{collection_id}/analyses` | Files of a collection with a ready analysis (search index input) | jeton interne |
| GET | `/api/internal/collections/{collection_id}/audience` | Who can read a collection (owner and shares) | jeton interne |
| GET | `/api/internal/users/collections` | Collections a person can read, by email (user index input) | jeton interne |

## Usage

| Méthode | Route | Description | Accès |
|---|---|---|---|
| GET | `/api/usage/me` | Tokens my questions consumed, in total and per graph node, day and model | connecté |

## Hors OpenAPI

| Route | Description | Accès |
|---|---|---|
| `/mcp` | serveur MCP (Streamable HTTP), voir [mcp.md](mcp.md) | connecté (jeton Keycloak) |
| `GET /.well-known/oauth-protected-resource/mcp` | où se connecter pour utiliser le serveur MCP (RFC 9728) | public |

Guides : [analyse éphémère](ephemeral-analysis.md), [serveur MCP](mcp.md), [graphiques](charts.md),
[requêtes SQL](sql-queries.md), [index de recherche](search-index.md), [`analyse.json`](analyse-json.md).

