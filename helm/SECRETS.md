# Secrets de spreadsheet-analyser

Ce document dit quels secrets l'application attend, qui en a besoin, comment ils sont stockés dans Vault, comment ils
arrivent dans les pods (Vault Secrets Operator, comme Muffin) et comment les renouveler. Il ne contient aucune valeur
réelle.

Le chart est celui de Muffin (basé sur les charts de [this-is-tobi](https://github.com/this-is-tobi/helm-charts)) :
chaque composant (`backend`, `frontend`, `agent_worker`, `analysis_worker`, `index_worker`) et chaque job (`jobs.migration`) charge
des `Secret` dans son environnement avec `envFrom`, et `extraObjects` déclare les `VaultStaticSecret` qui créent ces
`Secret`. Tout est écrit dans [`values/common-values.yaml`](values/common-values.yaml), `values.yaml` ne contenant que
les valeurs par défaut du chart.

## Règles

1. Aucun secret dans Git, dans `values.yaml`, dans une image ni dans une variable `VITE_*` du frontend. Les `VITE_*`
   sont compilées dans le JavaScript servi à tout le monde. Le frontend n'a donc **aucun** secret à l'exécution.
2. `env:` ne sert qu'à la configuration non secrète. Il est visible dans les valeurs Helm et dans le secret de
   release Helm : n'y mettez jamais un identifiant, même « temporaire ».
3. Un secret par environnement : ne réutilisez jamais une valeur de dev en production (liste en fin de document).
4. Le dépôt est scanné par gitleaks (hook pre-commit et CI) : un secret commité fait échouer le contrôle, mais il
   reste dans l'historique. S'il arrive quand même dans Git, considérez-le comme compromis et renouvelez-le.

## Inventaire

| Variable | Rôle | Backend | Worker agent | Worker analyse | Worker index | Job de migration |
|---|---|:-:|:-:|:-:|:-:|:-:|
| `DATABASE_URL` | Connexion PostgreSQL, **mot de passe inclus** | ✔ | | | | ✔ |
| `REDIS_URL` | Redis : sessions du backend et file Celery. Contient un mot de passe s'il est protégé | ✔ | ✔ | ✔ | ✔ | |
| `KEYCLOAK_CLIENT_SECRET` | Secret du client Keycloak du backend (échange du code OAuth2) | ✔ | | | | |
| `AWS_ACCESS_KEY_ID` | Identifiant S3 / RustFS | ✔ | ✔ | ✔ | ✔ | |
| `AWS_SECRET_ACCESS_KEY` | Clé secrète S3 / RustFS | ✔ | ✔ | ✔ | ✔ | |
| `INTERNAL_API_TOKEN` | Jeton Bearer des workers vers `/api/internal/*`. **Même valeur partout** | ✔ | ✔ | ✔ | ✔ | |
| `OPENAI_API_KEY` | Clé du fournisseur de modèles (OpenAI ou compatible) | ✔ | ✔ | | | |

Tout le reste (`KEYCLOAK_URL`, `KEYCLOAK_REALM`, `AWS_S3_BUCKET`, `AWS_ENDPOINT_URL_S3`, `OPENAI_BASE_URL`,
`LLM_DEFAULT_MODEL`, `FRONTEND_URL`, `BACKEND_PUBLIC_URL`, `BACKEND_URL`…) n'est pas secret et va dans `env:`.

Précisions :

- **`DATABASE_URL`** doit utiliser le pilote asynchrone :
  `postgresql+asyncpg://<utilisateur>:<mot de passe>@<hôte>:5432/<base>`.
- **`INTERNAL_API_TOKEN`** : s'il est vide côté backend, les routes internes répondent 503 et plus aucune analyse
  ni réponse de l'assistant ne se termine. S'il diffère entre le backend et un worker, ce worker reçoit des 401.
- **`OPENAI_API_KEY`** : le backend l'utilise pour lister les modèles (`GET /api/models`), le worker agent pour
  répondre. Le worker d'analyse n'en a pas besoin. Sans clé, les runs échouent avec un message explicite.
- **`AWS_*`** : donnez à ces identifiants le droit minimal sur le seul bucket de l'application. Le backend lit,
  écrit et supprime des objets (et crée le bucket au démarrage s'il n'existe pas). Le worker d'analyse lit les
  fichiers et écrit les `analyse.json`. Le worker agent ne fait que lire.

## Organisation dans Vault

Un chemin Vault (KV v2) par `Secret` Kubernetes, comme pour Muffin. Le découpage suit la colonne « qui en a besoin » :
un pod ne reçoit que les `Secret` qu'il liste dans `envFrom`.

| Chemin Vault (exemple) | Clés à y écrire | `Secret` créé | Lu par |
|---|---|---|---|
| `spreadsheet-analyser/s3` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | `spreadsheet-analyser-s3` | backend, agent_worker, analysis_worker, index_worker |
| `spreadsheet-analyser/keycloak` | `KEYCLOAK_CLIENT_SECRET` | `spreadsheet-analyser-keycloak` | backend |
| `spreadsheet-analyser/openai` | `OPENAI_API_KEY` | `spreadsheet-analyser-openai` | backend, agent_worker |
| `spreadsheet-analyser/internal` | `INTERNAL_API_TOKEN` | `spreadsheet-analyser-internal` | backend, agent_worker, analysis_worker, index_worker |
| `spreadsheet-analyser/redis` | `REDIS_PASSWORD` | `spreadsheet-analyser-redis` (ajoute `REDIS_URL`) | backend, agent_worker, analysis_worker, index_worker |
| `spreadsheet-analyser/db` | `username`, `password` | `spreadsheet-analyser-db` (ne garde que `DATABASE_URL`) | backend, jobs.migration |

Le point d'accès (`mount`), les chemins et le `vaultAuthRef` dépendent de votre plateforme : ils se règlent dans vos
valeurs, pas dans le chart. `INTERNAL_API_TOKEN` est volontairement dans **un seul** `Secret` partagé par tous les
composants, pour que le backend et les trois workers ne puissent jamais diverger.

### Écrire les secrets dans Vault

Générez les valeurs aléatoires directement vers Vault, sans les faire passer par l'historique du shell (`=-` lit la
valeur sur l'entrée standard) :

```bash
openssl rand -hex 32 | vault kv put -mount=kv spreadsheet-analyser/internal INTERNAL_API_TOKEN=-
```

- `INTERNAL_API_TOKEN` : 32 octets aléatoires, comme ci-dessus.
- `KEYCLOAK_CLIENT_SECRET` : générez-le **dans Keycloak** (client `spreadsheet-analyser-backend`, onglet
  *Credentials*) puis copiez-le dans Vault. Ne gardez pas le secret du realm de dev.
- `REDIS_PASSWORD`, `username` / `password` de la base, `AWS_*` : viennent du service concerné (Redis,
  PostgreSQL, RustFS ou S3).
- `OPENAI_API_KEY` : créée chez votre fournisseur, de préférence une clé dédiée à l'application avec un plafond de
  dépense.

## Comment les secrets arrivent dans les pods

1. `extraObjects` déclare un `VaultStaticSecret` par `Secret` (`vaultAuthRef`, `mount`, `type: kv-v2`, `path`).
2. Vault Secrets Operator lit le chemin Vault et crée le `Secret` Kubernetes (`destination.create: true`).
3. Les conteneurs le chargent par `envFrom` (`backend.envFrom`, `agent_worker.envFrom`, `analysis_worker.envFrom`,
   `index_worker.envFrom`, `jobs.migration.envFrom`). Pour une variable définie dans
   plusieurs `Secret`, la **dernière** source gagne : placez les `Secret` calculés (`…-db`, `…-redis`) en dernier.
4. `refreshAfter` fait relire Vault périodiquement, et `rolloutRestartTargets` redémarre automatiquement les
   `Deployment` listés quand une valeur change.

Deux `Secret` sont **calculés** par une `transformation` VSO, pour ne stocker le mot de passe qu'une fois :

- `…-redis` : `REDIS_URL = redis://:<REDIS_PASSWORD>@<hôte>:6379/0` (le mot de passe brut est conservé).
- `…-db` : `DATABASE_URL = postgresql+asyncpg://<username>:<password>@<hôte>:5432/<base>`, avec
  `excludes: [".*"]` pour que les pods ne reçoivent pas `username` et `password` séparément.

Les modèles VSO ne savent pas encoder les caractères réservés d'une URL : utilisez des mots de passe
**alphanumériques** pour Redis et la base (sinon `@`, `/`, `:`, `%` cassent l'URL).

Dans un fichier de valeurs, les accolades du modèle VSO s'écrivent `{{ "{{" }} get .Secrets "password" {{ "}}" }}` :
`extraObjects` passe par `tpl`, qui les rend telles quelles (`{{ get .Secrets "password" }}`) pour VSO.

### Mise en place

```bash
# 1. Vault : écrire les chemins du tableau ci-dessus, et autoriser le rôle du VaultAuth à les lire
# 2. Déployer avec les valeurs communes, complétées de vos valeurs d'environnement
helm upgrade --install spreadsheet-analyser ./helm \
  -f helm/values/common-values.yaml -f values-<env>.yaml

# 3. Vérifier que l'opérateur a bien créé les Secret et que leurs clés sont là
kubectl get vaultstaticsecret
kubectl get secret spreadsheet-analyser-db -o jsonpath='{.data}' | jq 'keys'   # ["DATABASE_URL"] seulement
```

Un `Secret` absent fait rester le pod en `CreateContainerConfigError` : c'est le signe qu'un `VaultStaticSecret` n'a pas
été synchronisé (chemin ou rôle Vault incorrect).

Hors Vault (poste de dev, test), vous pouvez créer les mêmes `Secret` à la main avec les mêmes noms et les mêmes
clés, `envFrom` les lira de la même façon. Utilisez `kubectl create secret generic … --from-env-file=` depuis un fichier
hors du dépôt, jamais `--from-literal` (la valeur finit dans l'historique du shell).

## Renouveler

Écrivez la nouvelle valeur dans Vault : VSO la relit au prochain `refreshAfter` et redémarre les `Deployment`
concernés (`rolloutRestartTargets`, qui visent les noms fixes `spreadsheet-analyser-<composant>` : voir
`fullnameOverride` dans `values/common-values.yaml`). Les variables d'environnement ne sont lues qu'au démarrage, c'est ce redémarrage
qui les applique.

| Secret | À savoir |
|---|---|
| `INTERNAL_API_TOKEN` | Un seul `Secret` pour tous : le backend et les trois workers redémarrent ensemble. Brève fenêtre de 401 le temps du redémarrage. |
| `KEYCLOAK_CLIENT_SECRET` | Régénérer dans Keycloak d'abord, puis écrire dans Vault. Les sessions étant dans Redis, les connexions en cours ne sont pas coupées. |
| `username` / `password` (base) | Changer le mot de passe dans PostgreSQL, puis dans Vault : une courte coupure est possible entre les deux. Garder les mots de passe alphanumériques. |
| `REDIS_PASSWORD` | À changer côté Redis et dans Vault en même temps : les sessions et la file Celery sont interrompues pendant le redémarrage. |
| `AWS_*` | Créer une nouvelle paire de clés, l'écrire dans Vault, puis supprimer l'ancienne paire. |
| `OPENAI_API_KEY` | Créer la nouvelle clé, l'écrire dans Vault, puis révoquer l'ancienne. |

En cas de fuite : révoquez d'abord à la source, puis remplacez la valeur dans Vault. Pour `INTERNAL_API_TOKEN`, un
jeton divulgué permet de lire et d'écrire les runs et les analyses de tous les utilisateurs.

## Valeurs de développement à ne jamais utiliser en production

Elles sont publiques (dans `docker-compose.yaml`, `.env.example` ou `docker/keycloak/realm-spreadsheet-analyser.json`).

| Valeur | Où |
|---|---|
| `dev-only-secret-not-for-prod` | secret du client Keycloak du realm de dev |
| `dev-only-internal-token` | `INTERNAL_API_TOKEN` du compose |
| `rustfsadmin` / `rustfsadmin` | identifiants RustFS du compose |
| `spreadsheet_analyser` / `spreadsheet_analyser` | utilisateur et mot de passe PostgreSQL du compose |
| `admin` / `admin` | administrateur de démarrage de Keycloak |
| `dev` / `dev-password` | utilisateur de test du realm, qui a le rôle `admin` de l'application |

Le realm de dev (`redirectUris` et `webOrigins` en `localhost`) ne se réutilise pas tel quel : le client Keycloak de
production doit déclarer l'URL de rappel réelle (`<BACKEND_PUBLIC_URL>/api/auth/callback`) et les URL de
déconnexion de votre domaine.

## Ce que le chart déploie, et ce qui reste à votre charge

Déployé : `frontend`, `backend`, `agent_worker` (file `agent`), `analysis_worker` (file `analysis`, 1 Gio de mémoire
maximum), `index_worker` (file `index` : index de recherche des collections et des utilisateurs) et le job `migration` (`alembic upgrade head`, en hook `post-install` / `post-upgrade` pour que les `Secret`
créés par VSO existent déjà). Chaque worker a sa propre image (`agent-worker`, `analysis-worker`, `index-worker`).

À votre charge, dans votre fichier de valeurs d'environnement :

- les URL (`KEYCLOAK_URL`, `BACKEND_PUBLIC_URL`, `FRONTEND_URL`, `AWS_ENDPOINT_URL_S3`) et l'exposition
  (`ingress`, `httpRoute` ou `gateway` du chart) ;
- PostgreSQL, Redis, S3 / RustFS et Keycloak : externes par défaut (les sous-charts `redis`, `postgres` et `rustfs`
  existent mais sont désactivés) ;
- le `mount`, les `path` et le `vaultAuthRef` des `VaultStaticSecret`, ainsi que les hôtes de `DATABASE_URL` et
  `REDIS_URL` ;
- le frontend est compilé avec `VITE_API_BASE_URL=http://localhost:8000` par défaut : la CD doit passer cette
  variable (vide pour une même origine) dans les `BUILD_ARGS`, sans quoi le navigateur appelle `localhost`.
