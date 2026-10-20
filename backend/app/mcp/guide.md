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
| `analyze_files` | envoie les fichiers (en base64) et la question en un appel ; **sans question**, renvoie seulement l'analyse des fichiers |
| `ask_known_files` | pose une question (ou, sans question, donne l'analyse) de fichiers déjà analysés, désignés par leur `sha256`, sans les renvoyer |
| `ask` | autre question sur les mêmes fichiers d'une analyse |
| `get_run` | statut, puis réponse (texte, graphiques en PNG base64) |
| `get_analysis` | état de la pré-analyse des fichiers et analyse de chacun (`detail` : `summary`, `full` ou `none`) |
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

## Avoir seulement l'analyse des fichiers

Pour connaître la structure de fichiers (feuilles, colonnes, types, statistiques) sans poser de question, appelez
`analyze_files` **sans `query`** (ou `ask_known_files` avec des hashes, ou `get_analysis` pour une analyse existante).
Aucune question n'est lancée, donc aucun modèle n'est utilisé. L'analyse de chaque fichier est dans `files[].profile` :

- pour chaque feuille : son nom, son nombre de lignes, si un en-tête a été reconnu et ses 3 premières lignes ;
- pour chaque colonne : le `type` (`integer`, `number`, `text`, `date`, …), les cellules renseignées (`non_null`) et
  vides (`null`), le nombre de valeurs distinctes, des exemples, les valeurs les plus fréquentes, et selon le type les
  statistiques (`numeric` : min, max, moyenne, médiane, somme ; `dates` : min, max).

`get_analysis(analysis_id, detail="full")` renvoie l'`analyse.json` complet (toutes les statistiques) tant qu'il tient
dans 1 Mio, sinon l'aperçu ci-dessus avec une note. `detail="none"` ne renvoie que l'état, pour attendre la
pré-analyse sans rien lire.

## Modèle

`model` est facultatif dans `analyze_files`, `ask_known_files` et `ask` : sans lui, le serveur utilise le premier
modèle de conversation proposé par le fournisseur. Si vous en donnez un, il doit exister (liste dans
`GET /api/models`), sinon l'outil répond une erreur ; il reste ensuite celui des questions suivantes de l'analyse.
Si vous ne connaissez pas les identifiants, ne l'envoyez pas.

## Limites

- Les fichiers voyagent en base64 dans l'appel : 10 Mio au total une fois décodés. Au-delà, utilisez la route
  `POST /api/ephemeral/analyses` (envoi en multipart), puis `ask` et `get_run` avec l'`analysis_id` obtenu.
- Tout est supprimé 24 heures (par défaut, réglable avec `ttl_hours`) après la fin de la dernière question.
