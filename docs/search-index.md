# Index de recherche d'une collection

L'agent retrouve les colonnes, feuilles et valeurs des fichiers avec un index BM25. Cet index est **calculé une seule
fois puis enregistré** dans S3, au niveau de la collection, et tenu à jour par l'`analysis-worker` : l'agent le lit en un
seul appel au lieu de relire chaque `analyse.json` et de tout réindexer à chaque message.

## Où et quand

```
<collection_id>/search-index.json.gz        l'index de la collection (JSON compressé)
<collection_id>/<file_id>/versions/<n>/analyse.json     l'analyse d'un fichier (inchangée)
```

| Événement | Qui | Effet sur l'index |
|---|---|---|
| Une analyse devient `ready` (nouveau fichier, nouvelle version, relance) | `analysis-worker` | Les documents du fichier sont remplacés ou ajoutés ; les statistiques BM25 sont recalculées et l'index est réécrit. |
| Un fichier est supprimé | backend → `analysis.forget_file` | Ses documents sont retirés. S'il ne reste aucun fichier, l'objet est supprimé. |
| Une collection est supprimée | backend | L'index part avec le préfixe `<collection_id>/`. |
| Index absent, illisible, ou construit avec un autre format ou une autre tokenisation | `analysis-worker` | Reconstruit en entier depuis la liste des analyses prêtes de la collection (`GET /api/internal/collections/{id}/analyses`). |
| Rattrapage ou réparation | administrateur : `POST /api/admin/collections/{id}/search-index` | Tâche `analysis.rebuild_index` : reconstruction complète. |

Chaque lecture-modification-écriture se fait sous un verrou Redis par collection (`search-index:<collection_id>`), pour
que deux analyses qui se terminent en même temps ne s'écrasent pas. La mise à jour de l'index est **au mieux** : si elle
échoue, l'analyse reste `ready` (elle est valide) et l'agent réindexe lui-même ce qui manque.

## Contenu du fichier

```
{
  "schema_version": 1,          format du fichier
  "tokenizer_version": 1,       version de la normalisation du texte (voir plus bas)
  "built_at": "…",
  "files": { "<file_id>": { file_name, collection_name, version, result_key, sheets: [{name, rows, columns, hidden}] } },
  "docs":  [ { "payload": …, "fields": { "name": [...], "values": [...], "context": [...], "type": [...] } } ],
  "stats": { "doc_count", "avg_length": {champ: n}, "postings": { "<mot>": [numéros de documents] } }
}
```

- Un document par **feuille** et par **colonne**. Son `payload` contient tout ce qu'un résultat de recherche affiche
  (type, vides, distincts, min/max, valeurs fréquentes…) et, pour une colonne, ses valeurs fréquentes et exemples :
  la recherche et la recherche de valeurs n'ont donc plus besoin d'`analyse.json`.
- `stats` est le BM25 enregistré : documents contenant chaque mot et longueur moyenne de chaque champ. Les IDF s'en
  déduisent à la lecture. Restaurer l'index ne recompte donc aucun mot.
- `result_key` (`…/versions/<n>/analyse.json`) contient la version du fichier : c'est ce qui permet à l'agent de savoir
  si les documents d'un fichier sont à jour.

## Ce que fait l'agent

1. Il lit l'index de chaque collection concernée (un appel par collection).
2. Pour chaque fichier à portée dont l'analyse est prête, il compare le `result_key` du backend avec celui de l'index :
   - **identique** : les documents enregistrés sont utilisés tels quels ;
   - **différent ou absent** (analyse plus récente que l'index, fichier pas encore indexé) : il lit l'`analyse.json` de ce
     fichier et l'indexe en mémoire.
3. Seuls les fichiers à portée (et analysés) peuvent apparaître dans les résultats : les documents d'un fichier supprimé,
   hors portée, ou dont la nouvelle version a échoué ne sont jamais servis.
4. Cas courant (une collection, index à jour) : les statistiques enregistrées sont utilisées telles quelles. Avec
   plusieurs collections, ou des fichiers réindexés en mémoire, les statistiques sont recalculées en mémoire sur les
   documents (sans relire d'`analyse.json` pour ceux qui viennent de l'index).
5. L'`analyse.json` complet d'un fichier n'est lu que lorsqu'un outil en a besoin (`describe_sheet`, `describe_column`),
   une fois par fichier et par message.

Les résultats ne dépendent donc jamais de la fraîcheur de l'index : un index absent, périmé ou corrompu ne fait que
ralentir la recherche.

## Un code, deux images

L'`analysis-worker` écrit l'index et l'agent le lit : la tokenisation (accents, pluriels, synonymes, mots vides) et le
format doivent être strictement les mêmes. Le package `app/search/` est donc **identique** dans `agent-worker/` et
`analysis-worker/`. Une vérification de la CI (et de `make lint`) échoue si les deux copies diffèrent.

Quand la tokenisation change (`app/search/text.py`), incrémentez `TOKENIZER_VERSION` : les index déjà enregistrés sont alors
ignorés par l'agent (il indexe en mémoire) et reconstruits par l'`analysis-worker` à la prochaine analyse de la
collection, ou tout de suite avec `POST /api/admin/collections/{id}/search-index`.

## Limites

- Les analyses terminées avant l'arrivée de l'index ne sont pas dedans tant qu'une analyse de leur collection ne se
  termine pas, ou qu'un administrateur ne demande pas la reconstruction. Entre-temps, l'agent les indexe en mémoire.
- Une collection d'une très grande quantité de fichiers produit un index volumineux (compressé) et chaque mise à jour
  le réécrit en entier : la réécriture est proportionnelle à la taille de l'index, pas à celle du fichier ajouté.
