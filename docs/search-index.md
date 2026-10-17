# Index de recherche (BM25) : par collection et par utilisateur

L'agent retrouve les colonnes, feuilles et valeurs des fichiers avec un index BM25. Cet index n'est **pas recalculé à
chaque message** : il est calculé une fois, enregistré dans S3 et tenu à jour par un service dédié, l'`index-worker`.

| Qui | Rôle |
|---|---|
| `analysis-worker` | Analyse les tableurs et écrit `analyse.json`. Ne sait rien des index. |
| **`index-worker`** | Construit et tient à jour les index enregistrés (file Celery `index`). |
| `agent-worker` | Lit les index pour répondre ; indexe en mémoire ce qui manque. |
| backend | Décide quand mettre à jour (événements ci-dessous) et dit qui a accès à quoi. |

## Deux niveaux d'index, dans S3

```text
<collection_id>/search-index.json.gz              l'index d'une collection (ses fichiers analysés)
users/<sha256 de l'email>/search-index.json.gz    l'index d'une personne : tout ce qu'elle peut lire
<collection_id>/<file_id>/versions/<n>/analyse.json     l'analyse d'un fichier (inchangée)
```

- **Index de collection** : un document par feuille et par colonne de chaque fichier analysé.
- **Index d'utilisateur** : la fusion des index de collection de toutes les collections que la personne peut lire (les
  siennes et celles partagées avec son email). Il est construit **à partir des index de collection**, jamais des
  analyses : aucun `analyse.json` n'est relu. La clé est un hachage de l'email normalisé : aucune adresse n'apparaît dans
  les noms d'objets du bucket.

Pourquoi les deux : pour une question sur une collection précise, l'agent lit l'index de cette collection ; pour une
question sur « tout ce que je peux lire », il lit **un seul** index au lieu d'un par collection.

## Qui a accès à quoi

Les destinataires d'un index viennent de la table d'accès (`access_collection`) et du propriétaire de la collection :
l'identité d'une personne est son **email**, comme pour les partages. Le propriétaire est identifié par
`collections.created_by_email` ; pour les collections créées avant que l'email soit enregistré, il est rempli au premier
usage de l'application par leur propriétaire (liste des collections ou première question).

Le backend expose à l'`index-worker`, avec le jeton interne :

- `GET /api/internal/collections/{id}/audience` : le propriétaire et les emails avec qui la collection est partagée ;
- `GET /api/internal/users/collections?email=` : les collections qu'une personne peut lire ;
- `GET /api/internal/collections/{id}/analyses` : les analyses prêtes d'une collection (reconstruction complète).

## Événements

| Événement | Message envoyé à la file `index` | Effet |
|---|---|---|
| Une analyse devient `ready` | `index.file_analysed(analysis_id)` | Les documents du fichier sont ajoutés ou remplacés dans l'index de la collection ; puis les index des personnes qui la lisent sont reconstruits. |
| Un fichier est supprimé | `index.forget_file(collection_id, file_id)` | Retiré de l'index de la collection (l'objet disparaît s'il ne reste rien) ; puis index des lecteurs. |
| Un accès est donné ou retiré (propriétaire ou administrateur) | `index.rebuild_user(email)` | L'index de cette personne est reconstruit tout de suite. |
| Une collection est supprimée | `index.rebuild_user(email)` pour chaque lecteur | L'index de collection part avec le préfixe S3 ; ceux des lecteurs sont reconstruits. |
| Rattrapage ou réparation | `POST /api/admin/collections/{id}/search-index`, `POST /api/admin/users/search-index` | Reconstruction complète d'une collection, ou de l'index d'une personne. |

Garanties :

- **Verrous Redis** : chaque lecture-modification-écriture d'un index se fait sous un verrou par collection ou par
  personne, pour que deux mises à jour simultanées ne s'écrasent pas.
- **Regroupement** : quand un index de collection change, la reconstruction de l'index de chaque lecteur est planifiée au
  plus une fois par fenêtre de 15 secondes et par personne : importer 100 fichiers ne reconstruit pas 100 fois.
- **Ordre** : une analyse plus ancienne qui arrive en retard n'écrase pas une version plus récente du même fichier.
- **Au mieux** : si l'envoi d'un message ou la mise à jour échoue, l'analyse, le partage ou la suppression aboutissent
  quand même ; l'agent compense (voir plus bas).
- Un index absent, illisible ou construit avec une autre tokenisation est reconstruit en entier plutôt que patché.

## Contenu du fichier

```text
{
  "schema_version": 1,          format du fichier
  "tokenizer_version": 1,       version de la normalisation du texte (voir plus bas)
  "built_at": "…",
  "files": { "<file_id>": { file_name, collection_name, version, result_key, sheets: [{name, rows, columns, hidden}] } },
  "docs":  [ { "payload": …, "fields": { "name": [...], "values": [...], "context": [...], "type": [...] } } ],
  "stats": { "doc_count", "avg_length": {champ: n}, "postings": { "<mot>": [numéros de documents] } }
}
```

- Le `payload` d'un document contient tout ce qu'un résultat affiche (type, vides, distincts, min/max, valeurs
  fréquentes…) et, pour une colonne, ses valeurs fréquentes et exemples : la recherche et la recherche de valeurs n'ont
  plus besoin d'`analyse.json`.
- `stats` est le BM25 enregistré : documents contenant chaque mot et longueur moyenne de chaque champ (les IDF s'en
  déduisent à la lecture). Restaurer l'index ne recompte aucun mot.
- `result_key` (`…/versions/<n>/analyse.json`) contient la version du fichier : c'est ce qui permet à l'agent de savoir si
  les documents d'un fichier sont à jour.

## Ce que fait l'agent

Pour chaque fichier à portée dont l'analyse est prête, il cherche une copie **à jour** (même `result_key` que celui du
backend), dans cet ordre :

1. l'index de la personne, si la portée couvre au moins deux collections (une lecture) ;
2. sinon, ou pour les fichiers qu'il n'y trouve pas à jour, l'index de leur collection (une lecture par collection) ;
3. sinon, il lit l'`analyse.json` du fichier et l'indexe en mémoire.

Si tout vient d'un seul index enregistré, ses statistiques BM25 sont utilisées telles quelles ; sinon elles sont
recalculées en mémoire sur les documents (sans relire d'`analyse.json` pour ceux qui viennent d'un index).
L'`analyse.json` complet d'un fichier n'est lu que lorsqu'un outil en a besoin (`describe_sheet`, `describe_column`).

**Les droits ne dépendent jamais d'un index.** La portée vient du backend à chaque message (ce que la personne peut lire
*maintenant*), et seuls les fichiers de cette portée peuvent apparaître dans les résultats. Un index d'utilisateur qui
contient encore une collection dont l'accès vient d'être retiré ne la fait donc jamais ressortir ; la reconstruction
déclenchée par la révocation retire en plus ce contenu de S3. Un index absent, périmé ou corrompu ne fait que ralentir la
recherche.

## Un code, deux images

L'`index-worker` écrit les index et l'agent les lit : la tokenisation (accents, pluriels, synonymes, mots vides) et le
format doivent être strictement les mêmes. Le package `app/search/` est donc **identique** dans `agent-worker/` et
`index-worker/`. Une vérification de la CI (et de `make lint`) échoue si les deux copies diffèrent.

Quand la tokenisation change (`app/search/text.py`), incrémentez `TOKENIZER_VERSION` : les index déjà enregistrés sont alors
ignorés par l'agent (il indexe en mémoire) et reconstruits par l'`index-worker` à la prochaine mise à jour, ou tout de
suite avec les routes d'administration ci-dessus.

## Limites

- Les analyses terminées avant l'arrivée des index n'y sont qu'après une reconstruction (routes d'administration) ou la
  prochaine analyse de leur collection. Entre-temps, l'agent les indexe en mémoire.
- Le propriétaire d'une collection ancienne n'a pas d'index personnel tant qu'il n'a pas utilisé l'application depuis que
  son email est enregistré.
- Chaque mise à jour réécrit l'index en entier : le coût est proportionnel à la taille de l'index, pas à celle du fichier
  ajouté. Un index d'utilisateur duplique les documents des collections qu'il fusionne.
- Si l'email d'une personne change dans Keycloak, son ancien index n'est plus utilisé (l'agent retombe sur les index de
  collection) ; un nouvel index se construit à la prochaine mise à jour de ses collections.
