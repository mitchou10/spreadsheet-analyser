# Graphiques dans les réponses

L'agent peut illustrer une réponse avec des graphiques : barres, barres horizontales, courbe, aires, camembert, nuage
de points, histogramme. Une réponse peut en contenir plusieurs (6 au plus). Les images sont dessinées côté serveur,
rangées dans S3, servies **uniquement par le backend**, et apparaissent dans la réponse en Markdown.

## D'abord la requête, ensuite le graphique

Un graphique est toujours fait à partir du résultat d'une requête SQL (voir [sql-queries.md](sql-queries.md)) :

1. l'agent prépare les données avec `query_data` (agrégées, triées, 40 catégories au plus pour des barres). La réponse
   de l'outil contient un `query_id` ;
2. il appelle `create_chart` avec ce `query_id` et une **description** du graphique, jamais du code :

| Champ | Rôle |
|---|---|
| `type` | `bar`, `barh`, `line`, `area`, `pie`, `scatter`, `histogram` |
| `x` | colonne des catégories (bar, pie), de l'axe horizontal (line, area, scatter) ou des valeurs (histogram) |
| `y` | colonne(s) numérique(s), jusqu'à 6 ; un seul pour `pie` ; aucune pour `histogram` |
| `color` | colonne dont chaque valeur fait une série (avec un seul `y`) |
| `title`, `x_label`, `y_label` | textes du graphique |
| `stacked` | empile les séries (barres, aires) |
| `sort` | ordre des catégories : `none`, `x`, `y_desc`, `y_asc` |

3. l'outil attend que le graphique soit dessiné et rend le Markdown de l'image, que l'agent colle dans sa réponse :
   `![Ventes par région](/api/conversations/<conversation>/messages/<message>/charts/<graphique>)`.

Un graphique impossible à dessiner (colonne qui n'existe pas, `y` non numérique, trop de catégories ou de séries,
valeur négative dans un camembert) échoue avec un message qui dit quoi changer et liste les colonnes du résultat : l'agent
corrige et recommence.

Si le modèle oublie de coller un graphique qu'il a fait dessiner, il est **ajouté à la fin de la réponse** : un graphique
dessiné n'est jamais perdu.

## Qui fait quoi

| Qui | Rôle |
|---|---|
| `agent-worker` | Outil `create_chart` : demande, attend, rend le Markdown. Ne dessine rien. |
| backend | Valide la demande (le run est en cours, la requête est de ce run et a réussi, 6 graphiques au plus), garde l'enregistrement (`charts`), sert l'image. |
| `query-worker` | Rejoue la requête (jusqu'à 5 000 lignes, plus que ce que voit l'agent), dessine avec matplotlib, écrit le PNG. Même file et même worker que le SQL. |

Les workers ne parlent ni entre eux ni à la base : tout passe par le backend avec le jeton interne.

## Où sont les images

Dans S3, **par conversation puis par message** :

```text
<projet>/conversations/<conversation_id>/<message_id>/<graphique_id>.png
```

Le message est celui de la réponse. Il n'existe qu'à la fin du run, alors que les graphiques sont dessinés pendant : le
run **réserve l'identifiant de sa réponse** (`runs.answer_message_id`) dès sa création, et la réponse est enregistrée
sous cet identifiant. Supprimer une conversation supprime aussi `<projet>/conversations/<conversation_id>/`.

## La route des images

```text
GET /api/conversations/{conversation_id}/messages/{message_id}/charts/{chart_id}   →   image/png
```

- Réservée au propriétaire de la conversation, avec la même session que le reste de l'application ; un autre
  utilisateur reçoit 404. Les trois identifiants de l'URL doivent correspondre au même graphique.
- Rien n'est jamais servi directement par S3 : aucune URL signée, aucun lien public.
- Le contenu d'un graphique ne change jamais : `Cache-Control: private, max-age=86400, immutable`, et
  `X-Content-Type-Options: nosniff`.

## Dans l'interface

Le Markdown de la réponse contient un chemin relatif (`/api/...`). L'interface le charge **avec la session** (un
`<img>` simple ne la joindrait pas toujours), l'affiche à la largeur du message, et un clic l'ouvre en grand. Une image
indisponible laisse son titre à la place.

Seules les images du backend sont chargées. Une image avec une autre adresse (`https://…`) dans une réponse n'est **pas**
chargée, seul son texte est affiché : un modèle ne peut pas faire envoyer de requête vers un site de son choix, ni y
glisser des données dans l'adresse.

Sous la réponse, l'étape « Graphique » du bloc « Sources et outils » montre l'image et la description qui l'a produite ;
l'étape « Requête SQL » juste avant montre les données.

## Limites (variables du `query-worker`)

| Variable | Défaut | Effet |
|---|---|---|
| `CHART_MAX_POINTS` | 5000 | Lignes de la requête qui sont dessinées ; si le résultat en a plus, l'image le dit en bas. |
| `CHART_MAX_CATEGORIES` | 40 | Catégories d'un graphique en barres ou en courbe sur du texte. |

L'image a une taille fixe (900 × 540 px), quelle que soit la quantité de données. Plus de 12 séries sont refusées ; un
camembert garde ses 11 plus grandes parts et regroupe le reste dans « Autres ».
