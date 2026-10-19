Connectez un agent (Claude Code, un IDE, un script) à cette application pour analyser des fichiers Excel ou CSV avec
une question, sans rien garder : tout est supprimé automatiquement après un délai.

## Adresse du serveur

`{{MCP_URL}}`

## Connexion

Le serveur utilise la même connexion que l'application (Keycloak). Un agent qui sait faire OAuth se connecte tout seul :

```bash
claude mcp add --transport http spreadsheet-analyser {{MCP_URL}}
```

Il vous ouvrira la page de connexion la première fois. Avec un script ou un service, prenez un jeton d'accès Keycloak
(compte de service) et présentez-le en en-tête :

```bash
claude mcp add --transport http spreadsheet-analyser {{MCP_URL}} --header "Authorization: Bearer $TOKEN"
```

ou, dans un fichier de configuration :

```json
{
  "mcpServers": {
    "spreadsheet-analyser": {
      "type": "http",
      "url": "{{MCP_URL}}",
      "headers": { "Authorization": "Bearer <jeton>" }
    }
  }
}
```

Chacun ne voit que ses propres analyses.

## Outils

| Outil | Rôle |
|---|---|
| `analyze_files` | envoie les fichiers (en base64) **et** la question en un appel |
| `ask_known_files` | pose une question sur des fichiers déjà analysés, désignés par leur `sha256`, sans les renvoyer |
| `ask` | autre question sur les mêmes fichiers d'une analyse |
| `get_run` | statut, puis réponse (texte, graphiques en PNG base64) |
| `get_analysis` | état de la pré-analyse des fichiers |
| `delete_analysis` | supprime tout de suite |

## Déroulé

1. `analyze_files` avec `files` (`[{"name": "ventes.xlsx", "content_base64": "…"}]`, csv, xlsx, xls ou ods, 20 au
   plus) et `query` (la question). L'outil attend la pré-analyse des fichiers (30 secondes au plus) puis lance la
   question : il renvoie `analysis_id` et `run_id`. Si la pré-analyse n'est pas finie, il renvoie seulement
   `analysis_id` : posez la question avec `ask` quand `get_analysis` dit `ready`.
2. `get_run` toutes les quelques secondes jusqu'à `completed` (ou `failed`, `cancelled`). La réponse est dans `answer`
   (markdown) et les graphiques dans `charts` (`image_base64`).
3. `ask` pour une autre question (une à la fois), puis `delete_analysis` quand vous avez fini.

Chaque fichier d'une analyse a un `sha256`. Avec `ask_known_files`, on repose une question sur ces fichiers sans les
renvoyer ; si l'un d'eux n'est plus connu (expiré, supprimé, jamais envoyé), rien n'est créé et l'erreur liste les
fichiers à renvoyer avec `analyze_files`.

## Limites

- Les fichiers voyagent en base64 dans l'appel : 10 Mio au total une fois décodés. Au-delà, utilisez la route
  `POST /api/ephemeral/analyses` (envoi en multipart), puis `ask` et `get_run` avec l'`analysis_id` obtenu.
- Tout est supprimé 24 heures (par défaut, réglable avec `ttl_hours`) après la fin de la dernière question.
