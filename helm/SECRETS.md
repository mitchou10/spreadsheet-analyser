# Secrets de spreadsheet-analyser

Ce document dit quels secrets l'application attend, qui en a besoin, comment ils sont stockés dans Vault, comment ils
arrivent dans les pods (Vault Secrets Operator, comme Muffin) et comment les renouveler. Il ne contient aucune valeur
réelle.

Le chart est celui de Muffin (basé sur les charts de [this-is-tobi](https://github.com/this-is-tobi/helm-charts)) :
chaque composant (`backend`, `frontend`, `agent_worker`, `analysis_worker`, `index_worker`, `query_worker`) et chaque job (`jobs.migration`) charge
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
`FRONTEND_URL`, `BACKEND_PUBLIC_URL`, `BACKEND_URL`…) n'est pas secret et va dans `env:`.

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
| `<vaultEnv>/spreadsheet-analyser/s3` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (optionnelles : `AWS_ENDPOINT_URL_S3`, `AWS_S3_BUCKET`, `AWS_REGION`, `S3_KEY_PREFIX`) | `spreadsheet-analyser-s3` | backend, agent_worker, analysis_worker, index_worker, query_worker |
| `<vaultEnv>/spreadsheet-analyser/keycloak` | `KEYCLOAK_CLIENT_SECRET` (optionnelles : `KEYCLOAK_URL`, `KEYCLOAK_PUBLIC_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`) | `spreadsheet-analyser-keycloak` | backend |
| `<vaultEnv>/spreadsheet-analyser/openai` | `OPENAI_API_KEY` (optionnelles : `OPENAI_BASE_URL`, `LLM_ALLOWED_MODELS`) | `spreadsheet-analyser-openai` | backend, agent_worker |
| `<vaultEnv>/spreadsheet-analyser/internal` | `INTERNAL_API_TOKEN` | `spreadsheet-analyser-internal` | backend, agent_worker, analysis_worker, index_worker, query_worker |
| `<vaultEnv>/spreadsheet-analyser/redis` | `REDIS_PASSWORD` | `spreadsheet-analyser-redis` (ajoute `REDIS_URL`) | backend, agent_worker, analysis_worker, index_worker, query_worker |
| `<vaultEnv>/spreadsheet-analyser/db-superuser` | `username` (`postgres`), `password` | `spreadsheet-analyser-db-superuser` (type `basic-auth`) | CloudNativePG |
| `<vaultEnv>/spreadsheet-analyser/db-appuser` | `username` (`spreadsheet_analyser`, le propriétaire créé par CloudNativePG), `password` | `spreadsheet-analyser-db-appuser` (type `basic-auth`, lu par CloudNativePG) et `spreadsheet-analyser-db-infos` (ne garde que `DATABASE_URL`) | CloudNativePG ; backend, jobs.migration |

Les clés « optionnelles » ne sont pas secrètes : le chart les définit déjà dans `env:` (section suivante). Les écrire dans Vault est possible, mais elles seraient alors ignorées tant qu'elles restent aussi dans `env:`, qui est prioritaire sur `envFrom` : retirez-les d'`env:` pour que Vault fasse foi.

Tous les chemins sont dans le moteur KV v2 `global.vaultMount` (`exploration` par défaut), préfixés par `global.vaultEnv` (`dev` par défaut ; `staging`, `prod`… dans le fichier de valeurs de l'environnement) : `<vaultEnv>/spreadsheet-analyser/<secret>`. Le `vaultAuthRef` dépend de votre plateforme. `INTERNAL_API_TOKEN` est volontairement dans **un seul** `Secret` partagé par tous les
composants, pour que le backend et les trois workers ne puissent jamais diverger.

### Écrire les secrets dans Vault

Générez les valeurs aléatoires directement vers Vault, sans les faire passer par l'historique du shell (`=-` lit la
valeur sur l'entrée standard) :

```bash
openssl rand -hex 32 | vault kv put -mount=<vaultMount> <vaultEnv>/spreadsheet-analyser/internal INTERNAL_API_TOKEN=-
```

- `INTERNAL_API_TOKEN` : 32 octets aléatoires, comme ci-dessus.
- `KEYCLOAK_CLIENT_SECRET` : générez-le **dans Keycloak** (client `spreadsheet-analyser-backend`, onglet
  *Credentials*) puis copiez-le dans Vault. Ne gardez pas le secret du realm de dev.
- `REDIS_PASSWORD`, `username` / `password` de la base, `AWS_*` : viennent du service concerné (Redis,
  PostgreSQL, RustFS ou S3).
- `username` / `password` de la base : avec CloudNativePG, c'est vous qui les choisissez, **avant le premier
  démarrage du cluster**. Comme pour Muffin, le chemin `db-appuser` alimente deux `Secret` :
  `spreadsheet-analyser-db-appuser` (CloudNativePG s'en sert pour `initdb`) et `spreadsheet-analyser-db-infos`
  (`DATABASE_URL` du backend et de la migration). Le superuser a son propre chemin, `db-superuser`. `username` doit valoir `spreadsheet_analyser` (le `owner` d'`initdb`), et le mot de passe doit être
  alphanumérique :

  ```bash
  vault kv put -mount=<vaultMount> <vaultEnv>/spreadsheet-analyser/db-appuser \
    username=spreadsheet_analyser \
    password="$(openssl rand -hex 24)"
  vault kv put -mount=<vaultMount> <vaultEnv>/spreadsheet-analyser/db-superuser \
    username=postgres \
    password="$(openssl rand -hex 24)"
  ```
- `OPENAI_API_KEY` : créée chez votre fournisseur, de préférence une clé dédiée à l'application avec un plafond de
  dépense.

### Variables non secrètes qui vont avec

Chaque secret ci-dessus a besoin de sa configuration, qui n'est **pas** dans Vault mais dans `env:` du composant
(`values/common-values.yaml`, surchargée par le fichier de valeurs de l'environnement).

| Secret | Variable `env:` | Rôle | Composants |
|---|---|---|---|
| S3 | `AWS_ENDPOINT_URL_S3` | URL du service S3 / RustFS. À omettre pour AWS S3 | backend, tous les workers |
| S3 | `AWS_S3_BUCKET` | Nom du bucket | backend, tous les workers |
| S3 | `AWS_REGION` | Région (`us-east-1` par défaut) | backend, tous les workers |
| S3 | `S3_KEY_PREFIX` | Premier niveau de chaque clé d'objet. **Même valeur** dans le backend, `agent_worker`, `index_worker` et `query_worker` | backend, agent, index, query |
| Keycloak | `KEYCLOAK_URL` | URL de Keycloak vue par le backend (service interne possible) | backend |
| Keycloak | `KEYCLOAK_PUBLIC_URL` | URL vue par le navigateur, si elle diffère de `KEYCLOAK_URL`. Sinon `KEYCLOAK_URL` est utilisée | backend |
| Keycloak | `KEYCLOAK_REALM` | Realm (`spreadsheet-analyser`) | backend |
| Keycloak | `KEYCLOAK_CLIENT_ID` | Client du backend (`spreadsheet-analyser-backend`), celui dont `KEYCLOAK_CLIENT_SECRET` est le secret | backend |
| Keycloak | `BACKEND_PUBLIC_URL` | URL publique du backend, d'où est construit le `redirect_uri` OAuth2 (`<BACKEND_PUBLIC_URL>/api/auth/callback`) | backend |
| Keycloak | `FRONTEND_URL` | Où le navigateur arrive après connexion et déconnexion | backend |
| Keycloak | `SESSION_COOKIE_SECURE` | `true` en HTTPS (valeur par défaut) | backend |
| OpenAI | `OPENAI_BASE_URL` | URL d'un fournisseur compatible OpenAI (LiteLLM, vLLM, Ollama…). Vide pour `api.openai.com` | backend, agent_worker |
| OpenAI | `LLM_ALLOWED_MODELS` | Identifiants de modèles exposés, séparés par des virgules. Vide : tous ceux que le fournisseur liste et qui répondent | backend |
| Redis / base | hôtes | Ils sont dans le modèle VSO de `REDIS_URL` et `DATABASE_URL` (`extraObjects`), pas dans `env:` | — |
| Interne | `BACKEND_URL` | URL du backend (`http://spreadsheet-analyser-backend`), que les workers appellent avec `INTERNAL_API_TOKEN` | tous les workers |

## Comment les secrets arrivent dans les pods

1. `extraObjects` déclare un `VaultStaticSecret` par `Secret` (`vaultAuthRef`, `mount`, `type: kv-v2`, `path`).
2. Vault Secrets Operator lit le chemin Vault et crée le `Secret` Kubernetes (`destination.create: true`).
3. Les conteneurs le chargent par `envFrom` (`backend.envFrom`, `agent_worker.envFrom`, `analysis_worker.envFrom`,
   `index_worker.envFrom`, `query_worker.envFrom`, `jobs.migration.envFrom`). Pour une variable définie dans
   plusieurs `Secret`, la **dernière** source gagne : placez les `Secret` calculés (`…-db`, `…-redis`) en dernier.
4. `refreshAfter` fait relire Vault périodiquement, et `rolloutRestartTargets` redémarre automatiquement les
   `Deployment` listés quand une valeur change.

Deux `Secret` sont **calculés** par une `transformation` VSO, pour ne stocker le mot de passe qu'une fois :

- `…-redis` : `REDIS_URL = redis://:<REDIS_PASSWORD>@<hôte>:6379/0` (le mot de passe brut est conservé).
- `…-db-infos` : `DATABASE_URL = postgresql+asyncpg://<username>:<password>@<hôte>:5432/<base>`, avec
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
kubectl get secret spreadsheet-analyser-db-infos -o jsonpath='{.data}' | jq 'keys'   # ["DATABASE_URL"] seulement
```

Un `Secret` absent fait rester le pod en `CreateContainerConfigError` : c'est le signe qu'un `VaultStaticSecret` n'a pas
été synchronisé (chemin ou rôle Vault incorrect).

### Dépannage

| Symptôme | Cause probable |
|---|---|
| Le backend logue `database is unhealthy: {'error': '[Errno 111] Connection refused'}` | Le chemin Vault `<vaultEnv>/spreadsheet-analyser/db-appuser` (ou `db-superuser`) est vide ou n'est pas dans le bon `mount`. Sans `…-db-appuser`, CloudNativePG ne lance pas `initdb` : le pod PostgreSQL ne démarre pas et le service `spreadsheet-analyser-pg-cluster-rw` n'a aucun endpoint. Sans `…-db-infos`, le backend n'a pas de `DATABASE_URL` et retombe sur `localhost:5432`. |
| Pod en `CreateContainerConfigError` | Un `Secret` listé dans `envFrom` n'existe pas : voir `kubectl get vaultstaticsecret` et les événements de la ressource. |

Pour trancher entre les deux causes du premier cas :

```bash
kubectl get secret spreadsheet-analyser-db-infos spreadsheet-analyser-db-appuser spreadsheet-analyser-db-superuser   # les trois doivent exister
kubectl get cluster,pods | grep pg                                           # le cluster doit être sain
kubectl get endpoints spreadsheet-analyser-pg-cluster-rw                     # une IP, pas <none>
```

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
maximum), `index_worker` (file `index` : index de recherche des collections et des utilisateurs), `query_worker` (file `query` : le SQL que l'agent écrit sur les vraies lignes des fichiers ; même image que `analysis_worker`, 2 Gio de mémoire maximum et 2 cœurs) et le job `migration` (`alembic upgrade head`, en hook `post-install` / `post-upgrade` pour que les `Secret`
créés par VSO existent déjà). Chaque worker a sa propre image (`agent-worker`, `analysis-worker`, `index-worker`) ; `query_worker` réutilise celle d'`analysis-worker`.

À votre charge, dans votre fichier de valeurs d'environnement :

- les URL (`KEYCLOAK_URL`, `BACKEND_PUBLIC_URL`, `FRONTEND_URL`, `AWS_ENDPOINT_URL_S3`) et l'exposition
  (`ingress`, `httpRoute` ou `gateway` du chart) ;
- PostgreSQL est déployé par CloudNativePG (`cnpg`, dépendance `cluster`, comme Muffin ; le service de lecture-écriture
  est `spreadsheet-analyser-pg-cluster-rw`). S3 / RustFS et Keycloak sont externes (le sous-chart `redis` est activé comme dans Muffin, son service `spreadsheet-analyser-redis` est l'hôte de `REDIS_URL` ; les sous-charts
  `postgres` et `rustfs` existent mais sont désactivés). L'opérateur CloudNativePG doit être installé dans le cluster ;
- le `mount`, les `path` et le `vaultAuthRef` des `VaultStaticSecret`, ainsi que les hôtes de `DATABASE_URL` et
  `REDIS_URL` ;
- l'URL de l'API du frontend se règle à l'exécution, sans reconstruire l'image : `frontend.env.API_BASE_URL` (vide ou
  absente = même origine, l'ingress envoie `/api` au backend). Le conteneur écrit `/tmp/config.js` au démarrage
  (`frontend/docker/40-runtime-config.sh`), que nginx sert en `/config.js`. `VITE_API_BASE_URL` (build) ne sert plus
  qu'au développement local.
