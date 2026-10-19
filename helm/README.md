# spreadsheet-analyser

![Version: 0.6.2](https://img.shields.io/badge/Version-0.6.2-informational?style=flat-square) ![Type: application](https://img.shields.io/badge/Type-application-informational?style=flat-square) ![AppVersion: 0.7.2](https://img.shields.io/badge/AppVersion-0.7.2-informational?style=flat-square)

A Helm chart to deploy spreadsheet-analyser (frontend, backend, agent worker, analysis worker).

## Requirements

Kubernetes: `>=1.25.0-0`

| Repository | Name | Version |
|------------|------|---------|
| https://cloudnative-pg.github.io/charts | cnpg(cluster) | 0.8.1 |
| oci://registry-1.docker.io/cloudpirates | postgres(postgres) | 0.19.6 |
| oci://registry-1.docker.io/cloudpirates | redis(redis) | 0.27.9 |
| oci://registry-1.docker.io/cloudpirates | rustfs(rustfs) | 0.10.0 |

## Values

### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| cnpg | object | `{"enabled":false}` | CloudNativePG cluster (the `cluster` chart, aliased `cnpg`). Off by default: the environment values enable it and configure it (see `values/common-values.yaml`). |
| commonLabels | object | `{}` | Add labels to all the deployed resources |
| cronjobs | object | `{}` | Map of CronJobs to create (e.g. periodic archiving, cleanup, reports...). Each key is used as the cronjob name and as its `app.kubernetes.io/component` label. Every entry accepts the same fields as a `jobs` entry (see above, minus `hook`) plus the scheduling fields documented in the commented example below. |
| enabled | bool | `true` | Master switch for the whole chart. When `false`, every template renders nothing - use this to keep a release/namespace registered with a deployment system (e.g. an ArgoCD Application that always gets generated for every app/env combination) without actually deploying any resource into it. Note this does NOT cover subchart dependencies added via `Chart.yaml` (e.g. a bundled database/cache) - those still need their own `enabled: false` alongside this one. |
| extraObjects | object | `{}` | Map of extra specs to dynamically add to this chart. Each key is a unique, arbitrary name for the object (only used so `-f` values files/overrides can add, override or remove a single entry by key instead of the whole list - lists don't merge across values files in Helm). |
| fullnameOverride | string | `""` | String to fully override the default application name. |
| jobs | object | `{}` | Map of Jobs to create (e.g. one-off DB migrations, data seeding, archiving...). Each key is used as the job name and as its `app.kubernetes.io/component` label. Every entry accepts the fields documented in the commented example below. |
| nameOverride | string | `""` | Provide a name in place of the default application name. |
| postgres | object | `{"enabled":false}` | Bundled PostgreSQL. Off by default: point `DATABASE_URL` at an existing database instead. |
| query_worker | object | `{"affinity":{},"args":[],"automountServiceAccountToken":false,"autoscaling":{"enabled":false,"maxReplicas":3,"minReplicas":1,"targetCPUUtilizationPercentage":80,"targetMemoryUtilizationPercentage":80},"command":[],"containerPort":null,"containerPortName":"http","deploymentType":"Deployment","dnsConfig":{},"dnsPolicy":"","enableServiceLinks":false,"env":{},"envCm":{},"envFrom":[],"envSecret":{},"extraContainers":[],"extraPorts":[],"extraVolumeClaims":[],"extraVolumeMounts":[],"extraVolumes":[],"grpcRoute":{"annotations":{},"enabled":false,"hostnames":[],"labels":{},"parentRefs":[],"rules":[]},"hostAliases":[],"hostNetwork":false,"hostPID":false,"httpRoute":{"annotations":{},"enabled":false,"hostnames":[],"labels":{},"parentRefs":[],"rules":[]},"image":{"digest":"","pullPolicy":"IfNotPresent","registry":"ghcr.io","repository":"mitchou10/spreadsheet-analyser/analysis-worker","tag":""},"imagePullSecrets":[],"ingress":{"annotations":{},"className":"","enabled":false,"hosts":[{"name":"domain.local","paths":[{"backend":{"portNumber":null,"serviceName":""},"path":"/","pathType":"Prefix"}]}],"labels":{},"tls":[]},"initContainers":[],"metrics":{"enabled":false,"service":{"annotations":{},"labels":{},"port":9000,"portName":"metrics","targetPort":9000,"type":"ClusterIP"},"serviceMonitor":{"annotations":{},"enabled":false,"endpoints":[{"basicAuth":{"password":"","username":""},"bearerTokenSecret":{"key":"","name":""},"honorLabels":false,"interval":"30s","metricRelabelings":[],"path":"/metrics","relabelings":[],"scheme":"","scrapeTimeout":"10s","selector":{},"tlsConfig":{}}],"labels":{}}},"networkPolicy":{"annotations":{},"create":false,"egress":[],"ingress":[],"labels":{},"policyTypes":["Ingress"]},"nodeSelector":{},"pdb":{"annotations":{},"enabled":false,"labels":{},"maxUnavailable":"","minAvailable":""},"podAnnotations":{},"podLabels":{},"podSecurityContext":{"fsGroup":1000,"fsGroupChangePolicy":"OnRootMismatch","runAsGroup":1000,"runAsNonRoot":true,"runAsUser":1000,"seccompProfile":{"type":"RuntimeDefault"}},"priorityClassName":"","probes":{"livenessProbe":{"exec":{"command":["sh","-c","celery -A app.celery_app inspect ping -d celery@$HOSTNAME"]},"failureThreshold":3,"initialDelaySeconds":30,"periodSeconds":30,"successThreshold":1,"timeoutSeconds":10},"readinessProbe":{"exec":{"command":["sh","-c","celery -A app.celery_app inspect ping -d celery@$HOSTNAME"]},"failureThreshold":2,"initialDelaySeconds":10,"periodSeconds":10,"successThreshold":2,"timeoutSeconds":10},"startupProbe":{"exec":{"command":["sh","-c","celery -A app.celery_app inspect ping -d celery@$HOSTNAME"]},"failureThreshold":10,"initialDelaySeconds":0,"periodSeconds":10,"successThreshold":1,"timeoutSeconds":10}},"replicaCount":1,"resources":{"limits":{"cpu":"500m","memory":"2Gi"},"requests":{"cpu":"100m","memory":"256Mi"}},"revisionHistoryLimit":10,"securityContext":{"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]},"privileged":false,"readOnlyRootFilesystem":true,"runAsGroup":1000,"runAsNonRoot":true,"runAsUser":1000},"service":{"enabled":false,"extraPorts":[],"nodePort":null,"port":80,"portName":"http","protocol":"TCP","type":"ClusterIP"},"serviceAccount":{"annotations":{},"automountServiceAccountToken":false,"clusterRole":{"create":false,"rules":[]},"create":false,"enabled":false,"name":"","role":{"create":false,"rules":[]}},"strategy":{"rollingUpdate":{"maxSurge":1,"maxUnavailable":1},"type":"RollingUpdate"},"terminationGracePeriodSeconds":null,"tolerations":[],"topologySpreadConstraints":[],"updateStrategy":{},"volumeClaims":[],"volumeMounts":[{"mountPath":"/tmp","name":"tmp"}],"volumes":[{"emptyDir":{},"name":"tmp"}]}` | Bundled Redis (sessions of the backend and Celery broker). Off by default: point `REDIS_URL` at an existing Redis instead. See the `redis` dependency in Chart.yaml for its own values. |
| rustfs | object | `{"enabled":false}` | Bundled RustFS (S3-compatible object storage). Off by default: point `AWS_ENDPOINT_URL_S3` at an existing S3 instead. |

### Global

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| global.env | object | `{}` | Map or array of environment variables to inject into all containers (`valueFrom` supported). |
| global.envCm | object | `{}` | Map of environment variables to inject into a configmap loaded by all containers (`valueFrom` not supported). |
| global.envFrom | list | `[]` | List or map of `configMapRef`/`secretRef` entries to load into every container's `envFrom` (merged with each component's own `envFrom`, global entries first). |
| global.envSecret | object | `{}` | Map of environment variables to inject into a secret loaded by all containers (`valueFrom` not supported). |
| global.httpRoute.annotations | object | `{}` | Additional HTTPRoute annotations. |
| global.httpRoute.enabled | bool | `false` | Whether or not the chart-level HTTPRoute should be enabled. |
| global.httpRoute.hostnames | list | `[]` | Hostnames for the HTTPRoute to match. |
| global.httpRoute.labels | object | `{}` | Additional HTTPRoute labels. |
| global.httpRoute.parentRefs | list | `[]` | Parent references (Gateways) to attach the HTTPRoute to. |
| global.httpRoute.rules | list | `[]` | Routing rules for the HTTPRoute. Required when `enabled` is true, and every `backendRefs` entry must carry a `name`. |
| global.imagePullSecrets | list | `[]` | Image credentials applied to every component in addition to any component-specific `imagePullSecrets`. |
| global.imageRegistry | string | `""` | Global Docker image registry |
| global.ingress.annotations | object | `{}` | Additional ingress annotations. |
| global.ingress.className | string | `""` | Defines which ingress controller will implement the resource. |
| global.ingress.enabled | bool | `false` | Whether or not the chart-level ingress should be enabled. |
| global.ingress.hosts | list | `[]` | Hosts and paths served by the chart-level ingress. Each path's `backend.serviceName` is required (see above); `backend.portNumber` defaults to 80. |
| global.ingress.labels | object | `{}` | Additional ingress labels. |
| global.ingress.tls | list | `[]` | TLS configuration for the chart-level ingress. |

### AgentWorker

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| agent_worker.affinity | object | `{}` | Affinity used for app pod. |
| agent_worker.args | list | `[]` | Agent_worker container command args. |
| agent_worker.automountServiceAccountToken | bool | `false` | Mount the ServiceAccount token into the app pods. Defaults to false so a compromised container holds no API credentials; the API server does not need the token unless the app actually talks to the Kubernetes API. Applied at pod level so it holds even when `serviceAccount.name` points at an SA that automounts. |
| agent_worker.command | list | `[]` | Agent_worker container command. |
| agent_worker.containerPort | string | `nil` | Agent_worker container port number. Set to `null`/`0` (and disable `service`/probes) for components that don't listen on any port (e.g. a queue consumer). |
| agent_worker.containerPortName | string | `"http"` | Agent_worker container port name. |
| agent_worker.deploymentType | string | `"Deployment"` | Workload kind to deploy the app as. One of "Deployment", "StatefulSet" or "DaemonSet" (validated at render time - an unknown value fails instead of producing a release with no workload). Use the top-level `jobs` / `cronjobs` maps for one-off or scheduled workloads. Some values only apply to certain kinds: `replicaCount`/`autoscaling` and `strategy` are Deployment-only (`autoscaling` also works on a StatefulSet), `volumeClaims`/`extraVolumeClaims` are StatefulSet-only, and `updateStrategy` covers StatefulSet and DaemonSet. |
| agent_worker.dnsConfig | object | `{}` | Pod DNS configuration, merged with `dnsPolicy` by the kubelet. |
| agent_worker.dnsPolicy | string | `""` (`ClusterFirstWithHostNet` when `hostNetwork` is true) | Pod DNS policy. Left empty, it defaults to `ClusterFirstWithHostNet` when `hostNetwork` is true (otherwise a hostNetwork pod silently stops resolving cluster DNS) and to the Kubernetes default `ClusterFirst` when it isn't. |
| agent_worker.enableServiceLinks | bool | `false` | Inject the legacy `{SVC}_SERVICE_HOST`/`_PORT` environment variables for every Service in the namespace. Defaults to false: the variables are rarely used, leak the namespace's topology into every container, and can collide with the app's own configuration. Set to true only for an app that genuinely reads them. |
| agent_worker.env | object | `{}` | Map or array of environment variables to inject into the app container (`valueFrom` supported). |
| agent_worker.envCm | object | `{}` | Map of environment variables to inject into a configmap loaded by the app container (`valueFrom` not supported). |
| agent_worker.envFrom | list | `[]` | Agent_worker container env variables loaded from configmap or secret reference. List or map (merged with `global.envFrom` above, global entries first); see `global.envFrom` for both forms. |
| agent_worker.envSecret | object | `{}` | Map of environment variables to inject into a secret loaded by the app container (`valueFrom` not supported). Values placed here are stored in plain text in the values file AND in the Helm release secret, so use it for non-sensitive-but-secret-shaped config only. For real credentials prefer referencing a Secret you manage elsewhere via `envFrom`, or have an operator materialise it (see the `VaultStaticSecret` example under `extraObjects`). |
| agent_worker.extraContainers | list | `[]` | Extra containers to add to the app pod as sidecars. |
| agent_worker.extraPorts | list | `[]` | Agent_worker extra container ports. |
| agent_worker.extraVolumeClaims | list | `[]` | Additional volumeClaims to add, concatenated with `volumeClaims` above at render time. |
| agent_worker.extraVolumeMounts | list | `[]` | Additional volumeMounts to add, concatenated with `volumeMounts` above at render time. |
| agent_worker.extraVolumes | list | `[]` | Additional volumes to add, concatenated with `volumes` above at render time (e.g. to mount a cert or config from a values override without repeating the chart's own volumes). |
| agent_worker.hostAliases | list | `[]` | Host aliases that will be injected at pod-level into /etc/hosts. |
| agent_worker.hostNetwork | bool | `false` | Share the host network namespace. Container ports then bind directly on the node, so they must not collide with anything else running there. |
| agent_worker.hostPID | bool | `false` | Share the host PID namespace (lets the container see and signal host processes). |
| agent_worker.imagePullSecrets | list | `[]` | Image credentials configuration. |
| agent_worker.initContainers | list | `[]` | Init containers to add to the app pod. |
| agent_worker.nodeSelector | object | `{}` | Default node selector for app. |
| agent_worker.podAnnotations | object | `{}` | Annotations for the app deployed pods. |
| agent_worker.podLabels | object | `{}` | Labels for the app deployed pods. |
| agent_worker.podSecurityContext | object | `{"fsGroup":1000,"fsGroupChangePolicy":"OnRootMismatch","runAsGroup":1000,"runAsNonRoot":true,"runAsUser":1000,"seccompProfile":{"type":"RuntimeDefault"}}` | Pod-level security context. Defaults to a hardened baseline that satisfies the `restricted` Pod Security Standard. Rendered via `toYaml`, so any `PodSecurityContext` field is accepted. Adjust the UID/GID to whatever your image actually ships with - `runAsNonRoot` makes the kubelet refuse to start a container that would run as root, which is the intended failure mode rather than something to switch off. Set to `null` to omit the block entirely. |
| agent_worker.priorityClassName | string | `""` | PriorityClass to schedule the pods with (e.g. `system-node-critical` for a node agent that must not be evicted under pressure). |
| agent_worker.replicaCount | int | `1` | The number of application controller pods to run. Ignored when `deploymentType` is "DaemonSet" (one pod per node) or when `autoscaling.enabled` is true. |
| agent_worker.revisionHistoryLimit | int | `10` | Revision history limit for the app. |
| agent_worker.securityContext | object | `{"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]},"privileged":false,"readOnlyRootFilesystem":true,"runAsGroup":1000,"runAsNonRoot":true,"runAsUser":1000}` | Container-level security context. Defaults to a hardened baseline that satisfies the `restricted` Pod Security Standard: no privilege escalation, no capabilities, immutable root filesystem. Rendered via `toYaml`, so any `SecurityContext` field is accepted. Note `readOnlyRootFilesystem` requires the app to write only to mounted volumes - the default `volumes`/`volumeMounts` below provide an `emptyDir` on /tmp for that reason. Set to `null` to omit the block entirely. |
| agent_worker.terminationGracePeriodSeconds | int | `null` (Kubernetes default of 30) | Grace period, in seconds, given to the pod to shut down cleanly before it is killed. |
| agent_worker.tolerations | list | `[]` | Default tolerations for app. |
| agent_worker.topologySpreadConstraints | list | `[]` | Topology spread constraints used to spread the pods across failure domains. |
| agent_worker.updateStrategy | object | `{}` | Update strategy applied when `deploymentType` is "StatefulSet" or "DaemonSet" (ignored for a Deployment, which uses `strategy` above). Rendered verbatim via `toYaml`, so it takes the native `StatefulSetUpdateStrategy`/`DaemonSetUpdateStrategy` shape of the selected kind; left empty, Kubernetes applies its own default (`RollingUpdate` for both). |
| agent_worker.volumeClaims | list | `[]` | List of volumeClaims to add, rendered as the StatefulSet's `volumeClaimTemplates`. Requires `deploymentType: "StatefulSet"` - setting it on a Deployment or DaemonSet fails at render time rather than being silently dropped (use `volumes`/`extraVolumes` there instead). |
| agent_worker.volumeMounts | list | `[{"mountPath":"/tmp","name":"tmp"}]` | List of mounts to add (normally used with `volumes` or `volumeClaims`). Prefer this for mounts the chart itself always needs; use `extraVolumeMounts` below for anything you add on top, so overriding one doesn't require repeating the other. Defaults to the `/tmp` mount backing the hardened `readOnlyRootFilesystem` default (see `volumes` above). |
| agent_worker.volumes | list | `[{"emptyDir":{},"name":"tmp"}]` | List of volumes to add. Prefer this for volumes the chart itself always needs (e.g. security-hardening `emptyDir`s); use `extraVolumes` below for anything you add on top, so overriding one doesn't require repeating the other. Defaults to a `/tmp` `emptyDir`, which is what makes the default `securityContext.readOnlyRootFilesystem: true` usable - drop it only if you also relax that. Helm replaces lists wholesale rather than merging them, so overriding this key means restating the entries you want to keep. |

#### Autoscaling

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| agent_worker.autoscaling.enabled | bool | `false` | Enable Horizontal Pod Autoscaler for the app. |
| agent_worker.autoscaling.maxReplicas | int | `3` | Maximum number of replicas for the app. |
| agent_worker.autoscaling.minReplicas | int | `1` | Minimum number of replicas for the app. |
| agent_worker.autoscaling.targetCPUUtilizationPercentage | int | `80` | Average CPU utilization percentage for the app. |
| agent_worker.autoscaling.targetMemoryUtilizationPercentage | int | `80` | Average memory utilization percentage for the app. |

#### GrpcRoute

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| agent_worker.grpcRoute.annotations | object | `{}` | Additional GRPCRoute annotations. |
| agent_worker.grpcRoute.enabled | bool | `false` | Enable a GRPCRoute resource for this service. |
| agent_worker.grpcRoute.hostnames | list | `[]` | Hostnames for the GRPCRoute to match. |
| agent_worker.grpcRoute.labels | object | `{}` | Additional GRPCRoute labels. |
| agent_worker.grpcRoute.parentRefs | list | `[]` | Parent references (Gateways) to attach the GRPCRoute to. |
| agent_worker.grpcRoute.rules | list | `[]` | Routing rules for the GRPCRoute. |

#### HttpRoute

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| agent_worker.httpRoute.annotations | object | `{}` | Additional HTTPRoute annotations. |
| agent_worker.httpRoute.enabled | bool | `false` | Enable an HTTPRoute resource for this service. |
| agent_worker.httpRoute.hostnames | list | `[]` | Hostnames for the HTTPRoute to match. |
| agent_worker.httpRoute.labels | object | `{}` | Additional HTTPRoute labels. |
| agent_worker.httpRoute.parentRefs | list | `[]` | Parent references (Gateways) to attach the HTTPRoute to. |
| agent_worker.httpRoute.rules | list | `[]` | Routing rules for the HTTPRoute. |

#### Image

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| agent_worker.image.digest | string | `""` | Image digest (`sha256:...`). When set it takes precedence over `tag`, pinning the exact image content so the same release can never resolve to a different build - preferred over a mutable tag for anything you deploy to production. |
| agent_worker.image.pullPolicy | string | `"IfNotPresent"` | Image pull policy for the app. |
| agent_worker.image.registry | string | `"ghcr.io"` | Registry to use for the app. |
| agent_worker.image.repository | string | `"mitchou10/spreadsheet-analyser/agent-worker"` | Repository to use for the app. |
| agent_worker.image.tag | string | `""` | Tag to use for the app. Overrides the image tag whose default is the chart appVersion. |

#### Ingress

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| agent_worker.ingress.annotations | object | `{}` | Additional ingress annotations. |
| agent_worker.ingress.className | string | `""` | Defines which ingress controller will implement the resource. |
| agent_worker.ingress.enabled | bool | `false` | Whether or not ingress should be enabled. |
| agent_worker.ingress.hosts[0].name | string | `"domain.local"` | Name of the host record. |
| agent_worker.ingress.hosts[0].paths | list | `[{"backend":{"portNumber":null,"serviceName":""},"path":"/","pathType":"Prefix"}]` | Paths of the host record to manage routing (avoids repeating the same host for multiple paths/backends). |
| agent_worker.ingress.hosts[0].paths[0].backend.portNumber | string | `nil` | Port used by the backend service linked to the path (leave null to use the app service port). |
| agent_worker.ingress.hosts[0].paths[0].backend.serviceName | string | `""` | Name of the backend service linked to the path (leave empty to use the app service). |
| agent_worker.ingress.hosts[0].paths[0].path | string | `"/"` | Path of the host record to manage routing. |
| agent_worker.ingress.hosts[0].paths[0].pathType | string | `"Prefix"` | Path type of the host record. |
| agent_worker.ingress.labels | object | `{}` | Additional ingress labels. |
| agent_worker.ingress.tls | list | `[]` | Enable TLS configuration. |

#### Metrics

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| agent_worker.metrics.enabled | bool | `false` | Deploy metrics service. |
| agent_worker.metrics.service.annotations | object | `{}` | Metrics service annotations. |
| agent_worker.metrics.service.labels | object | `{}` | Metrics service labels. |
| agent_worker.metrics.service.port | int | `9000` | Metrics service port. |
| agent_worker.metrics.service.portName | string | `"metrics"` | Metrics service port name. |
| agent_worker.metrics.service.targetPort | int | `9000` | Metrics service target port. |
| agent_worker.metrics.service.type | string | `"ClusterIP"` | Type of metrics service to create. |
| agent_worker.metrics.serviceMonitor.annotations | object | `{}` | Prometheus ServiceMonitor annotations. |
| agent_worker.metrics.serviceMonitor.enabled | bool | `false` | Enable a prometheus ServiceMonitor. |
| agent_worker.metrics.serviceMonitor.endpoints[0].basicAuth.password | string | `""` | The secret in the service monitor namespace that contains the password for authentication. |
| agent_worker.metrics.serviceMonitor.endpoints[0].basicAuth.username | string | `""` | The secret in the service monitor namespace that contains the username for authentication. |
| agent_worker.metrics.serviceMonitor.endpoints[0].bearerTokenSecret.key | string | `""` | Secret key to mount to read bearer token for scraping targets. The secret needs to be in the same namespace as the service monitor and accessible by the Prometheus Operator. |
| agent_worker.metrics.serviceMonitor.endpoints[0].bearerTokenSecret.name | string | `""` | Secret name to mount to read bearer token for scraping targets. The secret needs to be in the same namespace as the service monitor and accessible by the Prometheus Operator. |
| agent_worker.metrics.serviceMonitor.endpoints[0].honorLabels | bool | `false` | When true, honorLabels preserves the metric’s labels when they collide with the target’s labels. |
| agent_worker.metrics.serviceMonitor.endpoints[0].interval | string | `"30s"` | Prometheus ServiceMonitor interval. |
| agent_worker.metrics.serviceMonitor.endpoints[0].metricRelabelings | list | `[]` | Prometheus MetricRelabelConfigs to apply to samples before ingestion. |
| agent_worker.metrics.serviceMonitor.endpoints[0].path | string | `"/metrics"` | Path used by the Prometheus ServiceMonitor to scrape metrics. |
| agent_worker.metrics.serviceMonitor.endpoints[0].relabelings | list | `[]` | Prometheus RelabelConfigs to apply to samples before scraping. |
| agent_worker.metrics.serviceMonitor.endpoints[0].scheme | string | `""` | Prometheus ServiceMonitor scheme. |
| agent_worker.metrics.serviceMonitor.endpoints[0].scrapeTimeout | string | `"10s"` | Prometheus ServiceMonitor scrapeTimeout. If empty, Prometheus uses the global scrape timeout unless it is less than the target's scrape interval value in which the latter is used. |
| agent_worker.metrics.serviceMonitor.endpoints[0].selector | object | `{}` | Prometheus ServiceMonitor selector. |
| agent_worker.metrics.serviceMonitor.endpoints[0].tlsConfig | object | `{}` | Prometheus ServiceMonitor tlsConfig. |
| agent_worker.metrics.serviceMonitor.labels | object | `{}` | Prometheus ServiceMonitor labels. |

#### NetworkPolicy

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| agent_worker.networkPolicy.annotations | object | `{}` | Annotations to be added to the app NetworkPolicy. |
| agent_worker.networkPolicy.create | bool | `false` | Create NetworkPolicy object for the app. The policy always selects this component's pods only (via its selector labels), never the whole namespace. |
| agent_worker.networkPolicy.egress | list | `[]` | Egress rules for the NetworkPolicy object. |
| agent_worker.networkPolicy.ingress | list | `[]` | Ingress rules for the NetworkPolicy object. |
| agent_worker.networkPolicy.labels | object | `{}` | Labels to be added to the app NetworkPolicy. |
| agent_worker.networkPolicy.policyTypes | list | `["Ingress"]` | Policy types used in the NetworkPolicy object. |

#### Pdb

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| agent_worker.pdb.annotations | object | `{}` | Annotations to be added to app pdb. |
| agent_worker.pdb.enabled | bool | `false` | Deploy a PodDisruptionBudget for the app |
| agent_worker.pdb.labels | object | `{}` | Labels to be added to app pdb. |
| agent_worker.pdb.maxUnavailable | string | `""` | Number of pods that are unavailable after eviction as number or percentage (eg.: 50%). Has higher precedence over `agent_worker.pdb.minAvailable`. |
| agent_worker.pdb.minAvailable | string | `""` | Number of pods that are available after eviction as number or percentage (eg.: 50%). One of `minAvailable` / `maxUnavailable` must be set when `pdb.enabled` is true - a budget of 0 is the same as having no budget at all, so leaving both empty fails at render time. |

#### Probes

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| agent_worker.probes.livenessProbe.exec | object | `{"command":["sh","-c","celery -A app.celery_app inspect ping -d celery@$HOSTNAME"]}` | Agent_worker container healthcheck (livenessProbe is defined using `toYaml` so it is possible to override it completely). Uses `celery inspect ping` since Celery workers don't expose an HTTP endpoint. It runs in a shell so that $HOSTNAME is the pod's real hostname (Kubernetes only expands `$(VAR)` for variables declared in the pod spec). |
| agent_worker.probes.livenessProbe.failureThreshold | int | `3` | Minimum consecutive failures for the probe to be considered failed after having succeeded. |
| agent_worker.probes.livenessProbe.initialDelaySeconds | int | `30` | Number of seconds after the container has started before probe is initiated. |
| agent_worker.probes.livenessProbe.periodSeconds | int | `30` | How often (in seconds) to perform the probe. |
| agent_worker.probes.livenessProbe.successThreshold | int | `1` | Minimum consecutive successes for the probe to be considered successful after having failed. |
| agent_worker.probes.livenessProbe.timeoutSeconds | int | `10` | Number of seconds after which the probe times out. |
| agent_worker.probes.readinessProbe.exec | object | `{"command":["sh","-c","celery -A app.celery_app inspect ping -d celery@$HOSTNAME"]}` | Agent_worker container healthcheck (readinessProbe is defined using `toYaml` so it is possible to override it completely). Uses `celery inspect ping` since Celery workers don't expose an HTTP endpoint. It runs in a shell so that $HOSTNAME is the pod's real hostname (Kubernetes only expands `$(VAR)` for variables declared in the pod spec). |
| agent_worker.probes.readinessProbe.failureThreshold | int | `2` | Minimum consecutive failures for the probe to be considered failed after having succeeded. |
| agent_worker.probes.readinessProbe.initialDelaySeconds | int | `10` | Number of seconds after the container has started before probe is initiated. |
| agent_worker.probes.readinessProbe.periodSeconds | int | `10` | How often (in seconds) to perform the probe. |
| agent_worker.probes.readinessProbe.successThreshold | int | `2` | Minimum consecutive successes for the probe to be considered successful after having failed. |
| agent_worker.probes.readinessProbe.timeoutSeconds | int | `10` | Number of seconds after which the probe times out. |
| agent_worker.probes.startupProbe.exec | object | `{"command":["sh","-c","celery -A app.celery_app inspect ping -d celery@$HOSTNAME"]}` | Agent_worker container healthcheck (startupProbe is defined using `toYaml` so it is possible to override it completely). Uses `celery inspect ping` since Celery workers don't expose an HTTP endpoint. It runs in a shell so that $HOSTNAME is the pod's real hostname (Kubernetes only expands `$(VAR)` for variables declared in the pod spec). |
| agent_worker.probes.startupProbe.failureThreshold | int | `10` | Minimum consecutive failures for the probe to be considered failed after having succeeded. |
| agent_worker.probes.startupProbe.initialDelaySeconds | int | `0` | Number of seconds after the container has started before probe is initiated. |
| agent_worker.probes.startupProbe.periodSeconds | int | `10` | How often (in seconds) to perform the probe. |
| agent_worker.probes.startupProbe.successThreshold | int | `1` | Minimum consecutive successes for the probe to be considered successful after having failed. |
| agent_worker.probes.startupProbe.timeoutSeconds | int | `10` | Number of seconds after which the probe times out. |

#### Resources

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| agent_worker.resources.limits.cpu | string | `"500m"` | CPU limit for the app. |
| agent_worker.resources.limits.memory | string | `"2Gi"` | Memory limit for the app. |
| agent_worker.resources.requests.cpu | string | `"100m"` | CPU request for the app. |
| agent_worker.resources.requests.memory | string | `"256Mi"` | Memory request for the app. |

#### Service

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| agent_worker.service.enabled | bool | `false` | Whether or not to create a Service for the app. Set to `false` for components that don't accept traffic (e.g. a queue consumer with no `containerPort`). |
| agent_worker.service.extraPorts | list | `[]` | Extra service ports. |
| agent_worker.service.nodePort | int | `null` (allocated by Kubernetes) | Port used when type is `NodePort` to expose the service on the given node port. Left empty, Kubernetes allocates one from the configured node-port range, which avoids two releases of this chart colliding on the same hardcoded port. |
| agent_worker.service.port | int | `80` | Port used by the service. |
| agent_worker.service.portName | string | `"http"` | Port name used by the service. |
| agent_worker.service.protocol | string | `"TCP"` | Protocol used by the service. |
| agent_worker.service.type | string | `"ClusterIP"` | Type of service to create for the app. |

#### ServiceAccount

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| agent_worker.serviceAccount.annotations | object | `{}` | Annotations applied to created service account. |
| agent_worker.serviceAccount.automountServiceAccountToken | bool | `false` | Should the service account access token be automount in the pod. |
| agent_worker.serviceAccount.clusterRole.create | bool | `false` | Should the clusterRole be created. |
| agent_worker.serviceAccount.clusterRole.rules | list | `[]` | ClusterRole rules associated with the service account. |
| agent_worker.serviceAccount.create | bool | `false` | Create a service account. |
| agent_worker.serviceAccount.enabled | bool | `false` | Enable the service account. |
| agent_worker.serviceAccount.name | string | `""` | Service account name. |
| agent_worker.serviceAccount.role.create | bool | `false` | Should the role be created. |
| agent_worker.serviceAccount.role.rules | list | `[]` | Role rules associated with the service account. |

#### Strategy

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| agent_worker.strategy.rollingUpdate.maxSurge | int | `1` | The maximum number of pods that can be scheduled above the desired number of pods. |
| agent_worker.strategy.rollingUpdate.maxUnavailable | int | `1` | The maximum number of pods that can be unavailable during the update process. |
| agent_worker.strategy.type | string | `"RollingUpdate"` | Strategy type used to replace old Pods by new ones, can be `Recreate` or `RollingUpdate`. Only applied when `deploymentType` is "Deployment". |

### AnalysisWorker

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| analysis_worker.affinity | object | `{}` | Affinity used for app pod. |
| analysis_worker.args | list | `[]` | Analysis_worker container command args. |
| analysis_worker.automountServiceAccountToken | bool | `false` | Mount the ServiceAccount token into the app pods. Defaults to false so a compromised container holds no API credentials; the API server does not need the token unless the app actually talks to the Kubernetes API. Applied at pod level so it holds even when `serviceAccount.name` points at an SA that automounts. |
| analysis_worker.command | list | `[]` | Analysis_worker container command. |
| analysis_worker.containerPort | string | `nil` | Analysis_worker container port number. Set to `null`/`0` (and disable `service`/probes) for components that don't listen on any port (e.g. a queue consumer). |
| analysis_worker.containerPortName | string | `"http"` | Analysis_worker container port name. |
| analysis_worker.deploymentType | string | `"Deployment"` | Workload kind to deploy the app as. One of "Deployment", "StatefulSet" or "DaemonSet" (validated at render time - an unknown value fails instead of producing a release with no workload). Use the top-level `jobs` / `cronjobs` maps for one-off or scheduled workloads. Some values only apply to certain kinds: `replicaCount`/`autoscaling` and `strategy` are Deployment-only (`autoscaling` also works on a StatefulSet), `volumeClaims`/`extraVolumeClaims` are StatefulSet-only, and `updateStrategy` covers StatefulSet and DaemonSet. |
| analysis_worker.dnsConfig | object | `{}` | Pod DNS configuration, merged with `dnsPolicy` by the kubelet. |
| analysis_worker.dnsPolicy | string | `""` (`ClusterFirstWithHostNet` when `hostNetwork` is true) | Pod DNS policy. Left empty, it defaults to `ClusterFirstWithHostNet` when `hostNetwork` is true (otherwise a hostNetwork pod silently stops resolving cluster DNS) and to the Kubernetes default `ClusterFirst` when it isn't. |
| analysis_worker.enableServiceLinks | bool | `false` | Inject the legacy `{SVC}_SERVICE_HOST`/`_PORT` environment variables for every Service in the namespace. Defaults to false: the variables are rarely used, leak the namespace's topology into every container, and can collide with the app's own configuration. Set to true only for an app that genuinely reads them. |
| analysis_worker.env | object | `{}` | Map or array of environment variables to inject into the app container (`valueFrom` supported). |
| analysis_worker.envCm | object | `{}` | Map of environment variables to inject into a configmap loaded by the app container (`valueFrom` not supported). |
| analysis_worker.envFrom | list | `[]` | Analysis_worker container env variables loaded from configmap or secret reference. List or map (merged with `global.envFrom` above, global entries first); see `global.envFrom` for both forms. |
| analysis_worker.envSecret | object | `{}` | Map of environment variables to inject into a secret loaded by the app container (`valueFrom` not supported). Values placed here are stored in plain text in the values file AND in the Helm release secret, so use it for non-sensitive-but-secret-shaped config only. For real credentials prefer referencing a Secret you manage elsewhere via `envFrom`, or have an operator materialise it (see the `VaultStaticSecret` example under `extraObjects`). |
| analysis_worker.extraContainers | list | `[]` | Extra containers to add to the app pod as sidecars. |
| analysis_worker.extraPorts | list | `[]` | Analysis_worker extra container ports. |
| analysis_worker.extraVolumeClaims | list | `[]` | Additional volumeClaims to add, concatenated with `volumeClaims` above at render time. |
| analysis_worker.extraVolumeMounts | list | `[]` | Additional volumeMounts to add, concatenated with `volumeMounts` above at render time. |
| analysis_worker.extraVolumes | list | `[]` | Additional volumes to add, concatenated with `volumes` above at render time (e.g. to mount a cert or config from a values override without repeating the chart's own volumes). |
| analysis_worker.hostAliases | list | `[]` | Host aliases that will be injected at pod-level into /etc/hosts. |
| analysis_worker.hostNetwork | bool | `false` | Share the host network namespace. Container ports then bind directly on the node, so they must not collide with anything else running there. |
| analysis_worker.hostPID | bool | `false` | Share the host PID namespace (lets the container see and signal host processes). |
| analysis_worker.imagePullSecrets | list | `[]` | Image credentials configuration. |
| analysis_worker.initContainers | list | `[]` | Init containers to add to the app pod. |
| analysis_worker.nodeSelector | object | `{}` | Default node selector for app. |
| analysis_worker.podAnnotations | object | `{}` | Annotations for the app deployed pods. |
| analysis_worker.podLabels | object | `{}` | Labels for the app deployed pods. |
| analysis_worker.podSecurityContext | object | `{"fsGroup":1000,"fsGroupChangePolicy":"OnRootMismatch","runAsGroup":1000,"runAsNonRoot":true,"runAsUser":1000,"seccompProfile":{"type":"RuntimeDefault"}}` | Pod-level security context. Defaults to a hardened baseline that satisfies the `restricted` Pod Security Standard. Rendered via `toYaml`, so any `PodSecurityContext` field is accepted. Adjust the UID/GID to whatever your image actually ships with - `runAsNonRoot` makes the kubelet refuse to start a container that would run as root, which is the intended failure mode rather than something to switch off. Set to `null` to omit the block entirely. |
| analysis_worker.priorityClassName | string | `""` | PriorityClass to schedule the pods with (e.g. `system-node-critical` for a node agent that must not be evicted under pressure). |
| analysis_worker.replicaCount | int | `1` | The number of application controller pods to run. Ignored when `deploymentType` is "DaemonSet" (one pod per node) or when `autoscaling.enabled` is true. |
| analysis_worker.revisionHistoryLimit | int | `10` | Revision history limit for the app. |
| analysis_worker.securityContext | object | `{"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]},"privileged":false,"readOnlyRootFilesystem":true,"runAsGroup":1000,"runAsNonRoot":true,"runAsUser":1000}` | Container-level security context. Defaults to a hardened baseline that satisfies the `restricted` Pod Security Standard: no privilege escalation, no capabilities, immutable root filesystem. Rendered via `toYaml`, so any `SecurityContext` field is accepted. Note `readOnlyRootFilesystem` requires the app to write only to mounted volumes - the default `volumes`/`volumeMounts` below provide an `emptyDir` on /tmp for that reason. Set to `null` to omit the block entirely. |
| analysis_worker.terminationGracePeriodSeconds | int | `null` (Kubernetes default of 30) | Grace period, in seconds, given to the pod to shut down cleanly before it is killed. |
| analysis_worker.tolerations | list | `[]` | Default tolerations for app. |
| analysis_worker.topologySpreadConstraints | list | `[]` | Topology spread constraints used to spread the pods across failure domains. |
| analysis_worker.updateStrategy | object | `{}` | Update strategy applied when `deploymentType` is "StatefulSet" or "DaemonSet" (ignored for a Deployment, which uses `strategy` above). Rendered verbatim via `toYaml`, so it takes the native `StatefulSetUpdateStrategy`/`DaemonSetUpdateStrategy` shape of the selected kind; left empty, Kubernetes applies its own default (`RollingUpdate` for both). |
| analysis_worker.volumeClaims | list | `[]` | List of volumeClaims to add, rendered as the StatefulSet's `volumeClaimTemplates`. Requires `deploymentType: "StatefulSet"` - setting it on a Deployment or DaemonSet fails at render time rather than being silently dropped (use `volumes`/`extraVolumes` there instead). |
| analysis_worker.volumeMounts | list | `[{"mountPath":"/tmp","name":"tmp"}]` | List of mounts to add (normally used with `volumes` or `volumeClaims`). Prefer this for mounts the chart itself always needs; use `extraVolumeMounts` below for anything you add on top, so overriding one doesn't require repeating the other. Defaults to the `/tmp` mount backing the hardened `readOnlyRootFilesystem` default (see `volumes` above). |
| analysis_worker.volumes | list | `[{"emptyDir":{},"name":"tmp"}]` | List of volumes to add. Prefer this for volumes the chart itself always needs (e.g. security-hardening `emptyDir`s); use `extraVolumes` below for anything you add on top, so overriding one doesn't require repeating the other. Defaults to a `/tmp` `emptyDir`, which is what makes the default `securityContext.readOnlyRootFilesystem: true` usable - drop it only if you also relax that. Helm replaces lists wholesale rather than merging them, so overriding this key means restating the entries you want to keep. |

#### Autoscaling

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| analysis_worker.autoscaling.enabled | bool | `false` | Enable Horizontal Pod Autoscaler for the app. |
| analysis_worker.autoscaling.maxReplicas | int | `3` | Maximum number of replicas for the app. |
| analysis_worker.autoscaling.minReplicas | int | `1` | Minimum number of replicas for the app. |
| analysis_worker.autoscaling.targetCPUUtilizationPercentage | int | `80` | Average CPU utilization percentage for the app. |
| analysis_worker.autoscaling.targetMemoryUtilizationPercentage | int | `80` | Average memory utilization percentage for the app. |

#### GrpcRoute

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| analysis_worker.grpcRoute.annotations | object | `{}` | Additional GRPCRoute annotations. |
| analysis_worker.grpcRoute.enabled | bool | `false` | Enable a GRPCRoute resource for this service. |
| analysis_worker.grpcRoute.hostnames | list | `[]` | Hostnames for the GRPCRoute to match. |
| analysis_worker.grpcRoute.labels | object | `{}` | Additional GRPCRoute labels. |
| analysis_worker.grpcRoute.parentRefs | list | `[]` | Parent references (Gateways) to attach the GRPCRoute to. |
| analysis_worker.grpcRoute.rules | list | `[]` | Routing rules for the GRPCRoute. |

#### HttpRoute

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| analysis_worker.httpRoute.annotations | object | `{}` | Additional HTTPRoute annotations. |
| analysis_worker.httpRoute.enabled | bool | `false` | Enable an HTTPRoute resource for this service. |
| analysis_worker.httpRoute.hostnames | list | `[]` | Hostnames for the HTTPRoute to match. |
| analysis_worker.httpRoute.labels | object | `{}` | Additional HTTPRoute labels. |
| analysis_worker.httpRoute.parentRefs | list | `[]` | Parent references (Gateways) to attach the HTTPRoute to. |
| analysis_worker.httpRoute.rules | list | `[]` | Routing rules for the HTTPRoute. |

#### Image

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| analysis_worker.image.digest | string | `""` | Image digest (`sha256:...`). When set it takes precedence over `tag`, pinning the exact image content so the same release can never resolve to a different build - preferred over a mutable tag for anything you deploy to production. |
| analysis_worker.image.pullPolicy | string | `"IfNotPresent"` | Image pull policy for the app. |
| analysis_worker.image.registry | string | `"ghcr.io"` | Registry to use for the app. |
| analysis_worker.image.repository | string | `"mitchou10/spreadsheet-analyser/analysis-worker"` | Repository to use for the app. |
| analysis_worker.image.tag | string | `""` | Tag to use for the app. Overrides the image tag whose default is the chart appVersion. |

#### Ingress

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| analysis_worker.ingress.annotations | object | `{}` | Additional ingress annotations. |
| analysis_worker.ingress.className | string | `""` | Defines which ingress controller will implement the resource. |
| analysis_worker.ingress.enabled | bool | `false` | Whether or not ingress should be enabled. |
| analysis_worker.ingress.hosts[0].name | string | `"domain.local"` | Name of the host record. |
| analysis_worker.ingress.hosts[0].paths | list | `[{"backend":{"portNumber":null,"serviceName":""},"path":"/","pathType":"Prefix"}]` | Paths of the host record to manage routing (avoids repeating the same host for multiple paths/backends). |
| analysis_worker.ingress.hosts[0].paths[0].backend.portNumber | string | `nil` | Port used by the backend service linked to the path (leave null to use the app service port). |
| analysis_worker.ingress.hosts[0].paths[0].backend.serviceName | string | `""` | Name of the backend service linked to the path (leave empty to use the app service). |
| analysis_worker.ingress.hosts[0].paths[0].path | string | `"/"` | Path of the host record to manage routing. |
| analysis_worker.ingress.hosts[0].paths[0].pathType | string | `"Prefix"` | Path type of the host record. |
| analysis_worker.ingress.labels | object | `{}` | Additional ingress labels. |
| analysis_worker.ingress.tls | list | `[]` | Enable TLS configuration. |

#### Metrics

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| analysis_worker.metrics.enabled | bool | `false` | Deploy metrics service. |
| analysis_worker.metrics.service.annotations | object | `{}` | Metrics service annotations. |
| analysis_worker.metrics.service.labels | object | `{}` | Metrics service labels. |
| analysis_worker.metrics.service.port | int | `9000` | Metrics service port. |
| analysis_worker.metrics.service.portName | string | `"metrics"` | Metrics service port name. |
| analysis_worker.metrics.service.targetPort | int | `9000` | Metrics service target port. |
| analysis_worker.metrics.service.type | string | `"ClusterIP"` | Type of metrics service to create. |
| analysis_worker.metrics.serviceMonitor.annotations | object | `{}` | Prometheus ServiceMonitor annotations. |
| analysis_worker.metrics.serviceMonitor.enabled | bool | `false` | Enable a prometheus ServiceMonitor. |
| analysis_worker.metrics.serviceMonitor.endpoints[0].basicAuth.password | string | `""` | The secret in the service monitor namespace that contains the password for authentication. |
| analysis_worker.metrics.serviceMonitor.endpoints[0].basicAuth.username | string | `""` | The secret in the service monitor namespace that contains the username for authentication. |
| analysis_worker.metrics.serviceMonitor.endpoints[0].bearerTokenSecret.key | string | `""` | Secret key to mount to read bearer token for scraping targets. The secret needs to be in the same namespace as the service monitor and accessible by the Prometheus Operator. |
| analysis_worker.metrics.serviceMonitor.endpoints[0].bearerTokenSecret.name | string | `""` | Secret name to mount to read bearer token for scraping targets. The secret needs to be in the same namespace as the service monitor and accessible by the Prometheus Operator. |
| analysis_worker.metrics.serviceMonitor.endpoints[0].honorLabels | bool | `false` | When true, honorLabels preserves the metric’s labels when they collide with the target’s labels. |
| analysis_worker.metrics.serviceMonitor.endpoints[0].interval | string | `"30s"` | Prometheus ServiceMonitor interval. |
| analysis_worker.metrics.serviceMonitor.endpoints[0].metricRelabelings | list | `[]` | Prometheus MetricRelabelConfigs to apply to samples before ingestion. |
| analysis_worker.metrics.serviceMonitor.endpoints[0].path | string | `"/metrics"` | Path used by the Prometheus ServiceMonitor to scrape metrics. |
| analysis_worker.metrics.serviceMonitor.endpoints[0].relabelings | list | `[]` | Prometheus RelabelConfigs to apply to samples before scraping. |
| analysis_worker.metrics.serviceMonitor.endpoints[0].scheme | string | `""` | Prometheus ServiceMonitor scheme. |
| analysis_worker.metrics.serviceMonitor.endpoints[0].scrapeTimeout | string | `"10s"` | Prometheus ServiceMonitor scrapeTimeout. If empty, Prometheus uses the global scrape timeout unless it is less than the target's scrape interval value in which the latter is used. |
| analysis_worker.metrics.serviceMonitor.endpoints[0].selector | object | `{}` | Prometheus ServiceMonitor selector. |
| analysis_worker.metrics.serviceMonitor.endpoints[0].tlsConfig | object | `{}` | Prometheus ServiceMonitor tlsConfig. |
| analysis_worker.metrics.serviceMonitor.labels | object | `{}` | Prometheus ServiceMonitor labels. |

#### NetworkPolicy

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| analysis_worker.networkPolicy.annotations | object | `{}` | Annotations to be added to the app NetworkPolicy. |
| analysis_worker.networkPolicy.create | bool | `false` | Create NetworkPolicy object for the app. The policy always selects this component's pods only (via its selector labels), never the whole namespace. |
| analysis_worker.networkPolicy.egress | list | `[]` | Egress rules for the NetworkPolicy object. |
| analysis_worker.networkPolicy.ingress | list | `[]` | Ingress rules for the NetworkPolicy object. |
| analysis_worker.networkPolicy.labels | object | `{}` | Labels to be added to the app NetworkPolicy. |
| analysis_worker.networkPolicy.policyTypes | list | `["Ingress"]` | Policy types used in the NetworkPolicy object. |

#### Pdb

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| analysis_worker.pdb.annotations | object | `{}` | Annotations to be added to app pdb. |
| analysis_worker.pdb.enabled | bool | `false` | Deploy a PodDisruptionBudget for the app |
| analysis_worker.pdb.labels | object | `{}` | Labels to be added to app pdb. |
| analysis_worker.pdb.maxUnavailable | string | `""` | Number of pods that are unavailable after eviction as number or percentage (eg.: 50%). Has higher precedence over `analysis_worker.pdb.minAvailable`. |
| analysis_worker.pdb.minAvailable | string | `""` | Number of pods that are available after eviction as number or percentage (eg.: 50%). One of `minAvailable` / `maxUnavailable` must be set when `pdb.enabled` is true - a budget of 0 is the same as having no budget at all, so leaving both empty fails at render time. |

#### Probes

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| analysis_worker.probes.livenessProbe.exec | object | `{"command":["sh","-c","celery -A app.celery_app inspect ping -d celery@$HOSTNAME"]}` | Analysis_worker container healthcheck (livenessProbe is defined using `toYaml` so it is possible to override it completely). Uses `celery inspect ping` since Celery workers don't expose an HTTP endpoint. It runs in a shell so that $HOSTNAME is the pod's real hostname (Kubernetes only expands `$(VAR)` for variables declared in the pod spec). |
| analysis_worker.probes.livenessProbe.failureThreshold | int | `3` | Minimum consecutive failures for the probe to be considered failed after having succeeded. |
| analysis_worker.probes.livenessProbe.initialDelaySeconds | int | `30` | Number of seconds after the container has started before probe is initiated. |
| analysis_worker.probes.livenessProbe.periodSeconds | int | `30` | How often (in seconds) to perform the probe. |
| analysis_worker.probes.livenessProbe.successThreshold | int | `1` | Minimum consecutive successes for the probe to be considered successful after having failed. |
| analysis_worker.probes.livenessProbe.timeoutSeconds | int | `10` | Number of seconds after which the probe times out. |
| analysis_worker.probes.readinessProbe.exec | object | `{"command":["sh","-c","celery -A app.celery_app inspect ping -d celery@$HOSTNAME"]}` | Analysis_worker container healthcheck (readinessProbe is defined using `toYaml` so it is possible to override it completely). Uses `celery inspect ping` since Celery workers don't expose an HTTP endpoint. It runs in a shell so that $HOSTNAME is the pod's real hostname (Kubernetes only expands `$(VAR)` for variables declared in the pod spec). |
| analysis_worker.probes.readinessProbe.failureThreshold | int | `2` | Minimum consecutive failures for the probe to be considered failed after having succeeded. |
| analysis_worker.probes.readinessProbe.initialDelaySeconds | int | `10` | Number of seconds after the container has started before probe is initiated. |
| analysis_worker.probes.readinessProbe.periodSeconds | int | `10` | How often (in seconds) to perform the probe. |
| analysis_worker.probes.readinessProbe.successThreshold | int | `2` | Minimum consecutive successes for the probe to be considered successful after having failed. |
| analysis_worker.probes.readinessProbe.timeoutSeconds | int | `10` | Number of seconds after which the probe times out. |
| analysis_worker.probes.startupProbe.exec | object | `{"command":["sh","-c","celery -A app.celery_app inspect ping -d celery@$HOSTNAME"]}` | Analysis_worker container healthcheck (startupProbe is defined using `toYaml` so it is possible to override it completely). Uses `celery inspect ping` since Celery workers don't expose an HTTP endpoint. It runs in a shell so that $HOSTNAME is the pod's real hostname (Kubernetes only expands `$(VAR)` for variables declared in the pod spec). |
| analysis_worker.probes.startupProbe.failureThreshold | int | `10` | Minimum consecutive failures for the probe to be considered failed after having succeeded. |
| analysis_worker.probes.startupProbe.initialDelaySeconds | int | `0` | Number of seconds after the container has started before probe is initiated. |
| analysis_worker.probes.startupProbe.periodSeconds | int | `10` | How often (in seconds) to perform the probe. |
| analysis_worker.probes.startupProbe.successThreshold | int | `1` | Minimum consecutive successes for the probe to be considered successful after having failed. |
| analysis_worker.probes.startupProbe.timeoutSeconds | int | `10` | Number of seconds after which the probe times out. |

#### Resources

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| analysis_worker.resources.limits.cpu | string | `"500m"` | CPU limit for the app. |
| analysis_worker.resources.limits.memory | string | `"2Gi"` | Memory limit for the app. |
| analysis_worker.resources.requests.cpu | string | `"100m"` | CPU request for the app. |
| analysis_worker.resources.requests.memory | string | `"256Mi"` | Memory request for the app. |

#### Service

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| analysis_worker.service.enabled | bool | `false` | Whether or not to create a Service for the app. Set to `false` for components that don't accept traffic (e.g. a queue consumer with no `containerPort`). |
| analysis_worker.service.extraPorts | list | `[]` | Extra service ports. |
| analysis_worker.service.nodePort | int | `null` (allocated by Kubernetes) | Port used when type is `NodePort` to expose the service on the given node port. Left empty, Kubernetes allocates one from the configured node-port range, which avoids two releases of this chart colliding on the same hardcoded port. |
| analysis_worker.service.port | int | `80` | Port used by the service. |
| analysis_worker.service.portName | string | `"http"` | Port name used by the service. |
| analysis_worker.service.protocol | string | `"TCP"` | Protocol used by the service. |
| analysis_worker.service.type | string | `"ClusterIP"` | Type of service to create for the app. |

#### ServiceAccount

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| analysis_worker.serviceAccount.annotations | object | `{}` | Annotations applied to created service account. |
| analysis_worker.serviceAccount.automountServiceAccountToken | bool | `false` | Should the service account access token be automount in the pod. |
| analysis_worker.serviceAccount.clusterRole.create | bool | `false` | Should the clusterRole be created. |
| analysis_worker.serviceAccount.clusterRole.rules | list | `[]` | ClusterRole rules associated with the service account. |
| analysis_worker.serviceAccount.create | bool | `false` | Create a service account. |
| analysis_worker.serviceAccount.enabled | bool | `false` | Enable the service account. |
| analysis_worker.serviceAccount.name | string | `""` | Service account name. |
| analysis_worker.serviceAccount.role.create | bool | `false` | Should the role be created. |
| analysis_worker.serviceAccount.role.rules | list | `[]` | Role rules associated with the service account. |

#### Strategy

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| analysis_worker.strategy.rollingUpdate.maxSurge | int | `1` | The maximum number of pods that can be scheduled above the desired number of pods. |
| analysis_worker.strategy.rollingUpdate.maxUnavailable | int | `1` | The maximum number of pods that can be unavailable during the update process. |
| analysis_worker.strategy.type | string | `"RollingUpdate"` | Strategy type used to replace old Pods by new ones, can be `Recreate` or `RollingUpdate`. Only applied when `deploymentType` is "Deployment". |

### Backend

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.affinity | object | `{}` | Affinity used for app pod. |
| backend.args | list | `[]` | Backend container command args. |
| backend.automountServiceAccountToken | bool | `false` | Mount the ServiceAccount token into the app pods. Defaults to false so a compromised container holds no API credentials; the API server does not need the token unless the app actually talks to the Kubernetes API. Applied at pod level so it holds even when `serviceAccount.name` points at an SA that automounts. |
| backend.command | list | `[]` | Backend container command. |
| backend.containerPort | int | `8000` | Backend container port number. Set to `null`/`0` (and disable `service`/probes) for components that don't listen on any port (e.g. a queue consumer). |
| backend.containerPortName | string | `"http"` | Backend container port name. |
| backend.deploymentType | string | `"Deployment"` | Workload kind to deploy the app as. One of "Deployment", "StatefulSet" or "DaemonSet" (validated at render time - an unknown value fails instead of producing a release with no workload). Use the top-level `jobs` / `cronjobs` maps for one-off or scheduled workloads. Some values only apply to certain kinds: `replicaCount`/`autoscaling` and `strategy` are Deployment-only (`autoscaling` also works on a StatefulSet), `volumeClaims`/`extraVolumeClaims` are StatefulSet-only, and `updateStrategy` covers StatefulSet and DaemonSet. |
| backend.dnsConfig | object | `{}` | Pod DNS configuration, merged with `dnsPolicy` by the kubelet. |
| backend.dnsPolicy | string | `""` (`ClusterFirstWithHostNet` when `hostNetwork` is true) | Pod DNS policy. Left empty, it defaults to `ClusterFirstWithHostNet` when `hostNetwork` is true (otherwise a hostNetwork pod silently stops resolving cluster DNS) and to the Kubernetes default `ClusterFirst` when it isn't. |
| backend.enableServiceLinks | bool | `false` | Inject the legacy `{SVC}_SERVICE_HOST`/`_PORT` environment variables for every Service in the namespace. Defaults to false: the variables are rarely used, leak the namespace's topology into every container, and can collide with the app's own configuration. Set to true only for an app that genuinely reads them. |
| backend.env | object | `{}` | Map or array of environment variables to inject into the app container (`valueFrom` supported). |
| backend.envCm | object | `{}` | Map of environment variables to inject into a configmap loaded by the app container (`valueFrom` not supported). |
| backend.envFrom | list | `[]` | Backend container env variables loaded from configmap or secret reference. List or map (merged with `global.envFrom` above, global entries first); see `global.envFrom` for both forms. |
| backend.envSecret | object | `{}` | Map of environment variables to inject into a secret loaded by the app container (`valueFrom` not supported). Values placed here are stored in plain text in the values file AND in the Helm release secret, so use it for non-sensitive-but-secret-shaped config only. For real credentials prefer referencing a Secret you manage elsewhere via `envFrom`, or have an operator materialise it (see the `VaultStaticSecret` example under `extraObjects`). |
| backend.extraContainers | list | `[]` | Extra containers to add to the app pod as sidecars. |
| backend.extraPorts | list | `[]` | Backend extra container ports. |
| backend.extraVolumeClaims | list | `[]` | Additional volumeClaims to add, concatenated with `volumeClaims` above at render time. |
| backend.extraVolumeMounts | list | `[]` | Additional volumeMounts to add, concatenated with `volumeMounts` above at render time. |
| backend.extraVolumes | list | `[]` | Additional volumes to add, concatenated with `volumes` above at render time (e.g. to mount a cert or config from a values override without repeating the chart's own volumes). |
| backend.hostAliases | list | `[]` | Host aliases that will be injected at pod-level into /etc/hosts. |
| backend.hostNetwork | bool | `false` | Share the host network namespace. Container ports then bind directly on the node, so they must not collide with anything else running there. |
| backend.hostPID | bool | `false` | Share the host PID namespace (lets the container see and signal host processes). |
| backend.imagePullSecrets | list | `[]` | Image credentials configuration. |
| backend.initContainers | list | `[]` | Init containers to add to the app pod. |
| backend.nodeSelector | object | `{}` | Default node selector for app. |
| backend.podAnnotations | object | `{}` | Annotations for the app deployed pods. |
| backend.podLabels | object | `{}` | Labels for the app deployed pods. |
| backend.podSecurityContext | object | `{"fsGroup":1000,"fsGroupChangePolicy":"OnRootMismatch","runAsGroup":1000,"runAsNonRoot":true,"runAsUser":1000,"seccompProfile":{"type":"RuntimeDefault"}}` | Pod-level security context. Defaults to a hardened baseline that satisfies the `restricted` Pod Security Standard. Rendered via `toYaml`, so any `PodSecurityContext` field is accepted. Adjust the UID/GID to whatever your image actually ships with - `runAsNonRoot` makes the kubelet refuse to start a container that would run as root, which is the intended failure mode rather than something to switch off. Set to `null` to omit the block entirely. |
| backend.priorityClassName | string | `""` | PriorityClass to schedule the pods with (e.g. `system-node-critical` for a node agent that must not be evicted under pressure). |
| backend.replicaCount | int | `1` | The number of application controller pods to run. Ignored when `deploymentType` is "DaemonSet" (one pod per node) or when `autoscaling.enabled` is true. |
| backend.revisionHistoryLimit | int | `10` | Revision history limit for the app. |
| backend.securityContext | object | `{"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]},"privileged":false,"readOnlyRootFilesystem":true,"runAsGroup":1000,"runAsNonRoot":true,"runAsUser":1000}` | Container-level security context. Defaults to a hardened baseline that satisfies the `restricted` Pod Security Standard: no privilege escalation, no capabilities, immutable root filesystem. Rendered via `toYaml`, so any `SecurityContext` field is accepted. Note `readOnlyRootFilesystem` requires the app to write only to mounted volumes - the default `volumes`/`volumeMounts` below provide an `emptyDir` on /tmp for that reason. Set to `null` to omit the block entirely. |
| backend.terminationGracePeriodSeconds | int | `null` (Kubernetes default of 30) | Grace period, in seconds, given to the pod to shut down cleanly before it is killed. |
| backend.tolerations | list | `[]` | Default tolerations for app. |
| backend.topologySpreadConstraints | list | `[]` | Topology spread constraints used to spread the pods across failure domains. |
| backend.updateStrategy | object | `{}` | Update strategy applied when `deploymentType` is "StatefulSet" or "DaemonSet" (ignored for a Deployment, which uses `strategy` above). Rendered verbatim via `toYaml`, so it takes the native `StatefulSetUpdateStrategy`/`DaemonSetUpdateStrategy` shape of the selected kind; left empty, Kubernetes applies its own default (`RollingUpdate` for both). |
| backend.volumeClaims | list | `[]` | List of volumeClaims to add, rendered as the StatefulSet's `volumeClaimTemplates`. Requires `deploymentType: "StatefulSet"` - setting it on a Deployment or DaemonSet fails at render time rather than being silently dropped (use `volumes`/`extraVolumes` there instead). |
| backend.volumeMounts | list | `[{"mountPath":"/tmp","name":"tmp"}]` | List of mounts to add (normally used with `volumes` or `volumeClaims`). Prefer this for mounts the chart itself always needs; use `extraVolumeMounts` below for anything you add on top, so overriding one doesn't require repeating the other. Defaults to the `/tmp` mount backing the hardened `readOnlyRootFilesystem` default (see `volumes` above). |
| backend.volumes | list | `[{"emptyDir":{},"name":"tmp"}]` | List of volumes to add. Prefer this for volumes the chart itself always needs (e.g. security-hardening `emptyDir`s); use `extraVolumes` below for anything you add on top, so overriding one doesn't require repeating the other. Defaults to a `/tmp` `emptyDir`, which is what makes the default `securityContext.readOnlyRootFilesystem: true` usable - drop it only if you also relax that. Helm replaces lists wholesale rather than merging them, so overriding this key means restating the entries you want to keep. |

#### Autoscaling

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.autoscaling.enabled | bool | `false` | Enable Horizontal Pod Autoscaler for the app. |
| backend.autoscaling.maxReplicas | int | `3` | Maximum number of replicas for the app. |
| backend.autoscaling.minReplicas | int | `1` | Minimum number of replicas for the app. |
| backend.autoscaling.targetCPUUtilizationPercentage | int | `80` | Average CPU utilization percentage for the app. |
| backend.autoscaling.targetMemoryUtilizationPercentage | int | `80` | Average memory utilization percentage for the app. |

#### GrpcRoute

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.grpcRoute.annotations | object | `{}` | Additional GRPCRoute annotations. |
| backend.grpcRoute.enabled | bool | `false` | Enable a GRPCRoute resource for this service. |
| backend.grpcRoute.hostnames | list | `[]` | Hostnames for the GRPCRoute to match. |
| backend.grpcRoute.labels | object | `{}` | Additional GRPCRoute labels. |
| backend.grpcRoute.parentRefs | list | `[]` | Parent references (Gateways) to attach the GRPCRoute to. |
| backend.grpcRoute.rules | list | `[]` | Routing rules for the GRPCRoute. |

#### HttpRoute

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.httpRoute.annotations | object | `{}` | Additional HTTPRoute annotations. |
| backend.httpRoute.enabled | bool | `false` | Enable an HTTPRoute resource for this service. |
| backend.httpRoute.hostnames | list | `[]` | Hostnames for the HTTPRoute to match. |
| backend.httpRoute.labels | object | `{}` | Additional HTTPRoute labels. |
| backend.httpRoute.parentRefs | list | `[]` | Parent references (Gateways) to attach the HTTPRoute to. |
| backend.httpRoute.rules | list | `[]` | Routing rules for the HTTPRoute. |

#### Image

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.image.digest | string | `""` | Image digest (`sha256:...`). When set it takes precedence over `tag`, pinning the exact image content so the same release can never resolve to a different build - preferred over a mutable tag for anything you deploy to production. |
| backend.image.pullPolicy | string | `"IfNotPresent"` | Image pull policy for the app. |
| backend.image.registry | string | `"ghcr.io"` | Registry to use for the app. |
| backend.image.repository | string | `"mitchou10/spreadsheet-analyser/backend"` | Repository to use for the app. |
| backend.image.tag | string | `""` | Tag to use for the app. Overrides the image tag whose default is the chart appVersion. |

#### Ingress

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.ingress.annotations | object | `{}` | Additional ingress annotations. |
| backend.ingress.className | string | `""` | Defines which ingress controller will implement the resource. |
| backend.ingress.enabled | bool | `false` | Whether or not ingress should be enabled. |
| backend.ingress.hosts[0].name | string | `"domain.local"` | Name of the host record. |
| backend.ingress.hosts[0].paths | list | `[{"backend":{"portNumber":null,"serviceName":""},"path":"/","pathType":"Prefix"}]` | Paths of the host record to manage routing (avoids repeating the same host for multiple paths/backends). |
| backend.ingress.hosts[0].paths[0].backend.portNumber | string | `nil` | Port used by the backend service linked to the path (leave null to use the app service port). |
| backend.ingress.hosts[0].paths[0].backend.serviceName | string | `""` | Name of the backend service linked to the path (leave empty to use the app service). |
| backend.ingress.hosts[0].paths[0].path | string | `"/"` | Path of the host record to manage routing. |
| backend.ingress.hosts[0].paths[0].pathType | string | `"Prefix"` | Path type of the host record. |
| backend.ingress.labels | object | `{}` | Additional ingress labels. |
| backend.ingress.tls | list | `[]` | Enable TLS configuration. |

#### Metrics

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.metrics.enabled | bool | `false` | Deploy metrics service. |
| backend.metrics.service.annotations | object | `{}` | Metrics service annotations. |
| backend.metrics.service.labels | object | `{}` | Metrics service labels. |
| backend.metrics.service.port | int | `9000` | Metrics service port. |
| backend.metrics.service.portName | string | `"metrics"` | Metrics service port name. |
| backend.metrics.service.targetPort | int | `9000` | Metrics service target port. |
| backend.metrics.service.type | string | `"ClusterIP"` | Type of metrics service to create. |
| backend.metrics.serviceMonitor.annotations | object | `{}` | Prometheus ServiceMonitor annotations. |
| backend.metrics.serviceMonitor.enabled | bool | `false` | Enable a prometheus ServiceMonitor. |
| backend.metrics.serviceMonitor.endpoints[0].basicAuth.password | string | `""` | The secret in the service monitor namespace that contains the password for authentication. |
| backend.metrics.serviceMonitor.endpoints[0].basicAuth.username | string | `""` | The secret in the service monitor namespace that contains the username for authentication. |
| backend.metrics.serviceMonitor.endpoints[0].bearerTokenSecret.key | string | `""` | Secret key to mount to read bearer token for scraping targets. The secret needs to be in the same namespace as the service monitor and accessible by the Prometheus Operator. |
| backend.metrics.serviceMonitor.endpoints[0].bearerTokenSecret.name | string | `""` | Secret name to mount to read bearer token for scraping targets. The secret needs to be in the same namespace as the service monitor and accessible by the Prometheus Operator. |
| backend.metrics.serviceMonitor.endpoints[0].honorLabels | bool | `false` | When true, honorLabels preserves the metric’s labels when they collide with the target’s labels. |
| backend.metrics.serviceMonitor.endpoints[0].interval | string | `"30s"` | Prometheus ServiceMonitor interval. |
| backend.metrics.serviceMonitor.endpoints[0].metricRelabelings | list | `[]` | Prometheus MetricRelabelConfigs to apply to samples before ingestion. |
| backend.metrics.serviceMonitor.endpoints[0].path | string | `"/metrics"` | Path used by the Prometheus ServiceMonitor to scrape metrics. |
| backend.metrics.serviceMonitor.endpoints[0].relabelings | list | `[]` | Prometheus RelabelConfigs to apply to samples before scraping. |
| backend.metrics.serviceMonitor.endpoints[0].scheme | string | `""` | Prometheus ServiceMonitor scheme. |
| backend.metrics.serviceMonitor.endpoints[0].scrapeTimeout | string | `"10s"` | Prometheus ServiceMonitor scrapeTimeout. If empty, Prometheus uses the global scrape timeout unless it is less than the target's scrape interval value in which the latter is used. |
| backend.metrics.serviceMonitor.endpoints[0].selector | object | `{}` | Prometheus ServiceMonitor selector. |
| backend.metrics.serviceMonitor.endpoints[0].tlsConfig | object | `{}` | Prometheus ServiceMonitor tlsConfig. |
| backend.metrics.serviceMonitor.labels | object | `{}` | Prometheus ServiceMonitor labels. |

#### NetworkPolicy

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.networkPolicy.annotations | object | `{}` | Annotations to be added to the app NetworkPolicy. |
| backend.networkPolicy.create | bool | `false` | Create NetworkPolicy object for the app. The policy always selects this component's pods only (via its selector labels), never the whole namespace. |
| backend.networkPolicy.egress | list | `[]` | Egress rules for the NetworkPolicy object. |
| backend.networkPolicy.ingress | list | `[]` | Ingress rules for the NetworkPolicy object. |
| backend.networkPolicy.labels | object | `{}` | Labels to be added to the app NetworkPolicy. |
| backend.networkPolicy.policyTypes | list | `["Ingress"]` | Policy types used in the NetworkPolicy object. |

#### Pdb

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.pdb.annotations | object | `{}` | Annotations to be added to app pdb. |
| backend.pdb.enabled | bool | `false` | Deploy a PodDisruptionBudget for the app |
| backend.pdb.labels | object | `{}` | Labels to be added to app pdb. |
| backend.pdb.maxUnavailable | string | `""` | Number of pods that are unavailable after eviction as number or percentage (eg.: 50%). Has higher precedence over `backend.pdb.minAvailable`. |
| backend.pdb.minAvailable | string | `""` | Number of pods that are available after eviction as number or percentage (eg.: 50%). One of `minAvailable` / `maxUnavailable` must be set when `pdb.enabled` is true - a budget of 0 is the same as having no budget at all, so leaving both empty fails at render time. |

#### Probes

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.probes.livenessProbe.failureThreshold | int | `3` | Minimum consecutive failures for the probe to be considered failed after having succeeded. |
| backend.probes.livenessProbe.httpGet.path | string | `"/api/health"` | Backend container healthcheck endpoint (livenessProbe is defined using `toYaml` so it is possible to override it completely). |
| backend.probes.livenessProbe.httpGet.port | int | `8000` | Port to use for healthcheck (defaults to container port). |
| backend.probes.livenessProbe.initialDelaySeconds | int | `30` | Number of seconds after the container has started before probe is initiated. |
| backend.probes.livenessProbe.periodSeconds | int | `30` | How often (in seconds) to perform the probe. |
| backend.probes.livenessProbe.successThreshold | int | `1` | Minimum consecutive successes for the probe to be considered successful after having failed. |
| backend.probes.livenessProbe.timeoutSeconds | int | `5` | Number of seconds after which the probe times out. |
| backend.probes.readinessProbe.failureThreshold | int | `2` | Minimum consecutive failures for the probe to be considered failed after having succeeded. |
| backend.probes.readinessProbe.httpGet.path | string | `"/api/health"` | Backend container healthcheck endpoint (readinessProbe is defined using `toYaml` so it is possible to override it completely). |
| backend.probes.readinessProbe.httpGet.port | int | `8000` | Port to use for healthcheck (defaults to container port). |
| backend.probes.readinessProbe.initialDelaySeconds | int | `10` | Number of seconds after the container has started before probe is initiated. |
| backend.probes.readinessProbe.periodSeconds | int | `10` | How often (in seconds) to perform the probe. |
| backend.probes.readinessProbe.successThreshold | int | `2` | Minimum consecutive successes for the probe to be considered successful after having failed. |
| backend.probes.readinessProbe.timeoutSeconds | int | `5` | Number of seconds after which the probe times out. |
| backend.probes.startupProbe.failureThreshold | int | `10` | Minimum consecutive failures for the probe to be considered failed after having succeeded. |
| backend.probes.startupProbe.httpGet.path | string | `"/api/health"` | Backend container healthcheck endpoint (startupProbe is defined using `toYaml` so it is possible to override it completely). |
| backend.probes.startupProbe.httpGet.port | int | `8000` | Port to use for healthcheck (defaults to container port). |
| backend.probes.startupProbe.initialDelaySeconds | int | `0` | Number of seconds after the container has started before probe is initiated. |
| backend.probes.startupProbe.periodSeconds | int | `10` | How often (in seconds) to perform the probe. |
| backend.probes.startupProbe.successThreshold | int | `1` | Minimum consecutive successes for the probe to be considered successful after having failed. |
| backend.probes.startupProbe.timeoutSeconds | int | `5` | Number of seconds after which the probe times out. |

#### Resources

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.resources.limits.cpu | string | `"500m"` | CPU limit for the app. |
| backend.resources.limits.memory | string | `"2Gi"` | Memory limit for the app. |
| backend.resources.requests.cpu | string | `"100m"` | CPU request for the app. |
| backend.resources.requests.memory | string | `"256Mi"` | Memory request for the app. |

#### Service

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.service.enabled | bool | `true` | Whether or not to create a Service for the app. Set to `false` for components that don't accept traffic (e.g. a queue consumer with no `containerPort`). |
| backend.service.extraPorts | list | `[]` | Extra service ports. |
| backend.service.nodePort | int | `null` (allocated by Kubernetes) | Port used when type is `NodePort` to expose the service on the given node port. Left empty, Kubernetes allocates one from the configured node-port range, which avoids two releases of this chart colliding on the same hardcoded port. |
| backend.service.port | int | `80` | Port used by the service. |
| backend.service.portName | string | `"http"` | Port name used by the service. |
| backend.service.protocol | string | `"TCP"` | Protocol used by the service. |
| backend.service.type | string | `"ClusterIP"` | Type of service to create for the app. |

#### ServiceAccount

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.serviceAccount.annotations | object | `{}` | Annotations applied to created service account. |
| backend.serviceAccount.automountServiceAccountToken | bool | `false` | Should the service account access token be automount in the pod. |
| backend.serviceAccount.clusterRole.create | bool | `false` | Should the clusterRole be created. |
| backend.serviceAccount.clusterRole.rules | list | `[]` | ClusterRole rules associated with the service account. |
| backend.serviceAccount.create | bool | `false` | Create a service account. |
| backend.serviceAccount.enabled | bool | `false` | Enable the service account. |
| backend.serviceAccount.name | string | `""` | Service account name. |
| backend.serviceAccount.role.create | bool | `false` | Should the role be created. |
| backend.serviceAccount.role.rules | list | `[]` | Role rules associated with the service account. |

#### Strategy

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.strategy.rollingUpdate.maxSurge | int | `1` | The maximum number of pods that can be scheduled above the desired number of pods. |
| backend.strategy.rollingUpdate.maxUnavailable | int | `1` | The maximum number of pods that can be unavailable during the update process. |
| backend.strategy.type | string | `"RollingUpdate"` | Strategy type used to replace old Pods by new ones, can be `Recreate` or `RollingUpdate`. Only applied when `deploymentType` is "Deployment". |

### Frontend

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| frontend.affinity | object | `{}` | Affinity used for app pod. |
| frontend.args | list | `[]` | Frontend container command args. |
| frontend.automountServiceAccountToken | bool | `false` | Mount the ServiceAccount token into the app pods. Defaults to false so a compromised container holds no API credentials; the API server does not need the token unless the app actually talks to the Kubernetes API. Applied at pod level so it holds even when `serviceAccount.name` points at an SA that automounts. |
| frontend.command | list | `[]` | Frontend container command. |
| frontend.containerPort | int | `8080` | Frontend container port number. Set to `null`/`0` (and disable `service`/probes) for components that don't listen on any port (e.g. a queue consumer). |
| frontend.containerPortName | string | `"http"` | Frontend container port name. |
| frontend.deploymentType | string | `"Deployment"` | Workload kind to deploy the app as. One of "Deployment", "StatefulSet" or "DaemonSet" (validated at render time - an unknown value fails instead of producing a release with no workload). Use the top-level `jobs` / `cronjobs` maps for one-off or scheduled workloads. Some values only apply to certain kinds: `replicaCount`/`autoscaling` and `strategy` are Deployment-only (`autoscaling` also works on a StatefulSet), `volumeClaims`/`extraVolumeClaims` are StatefulSet-only, and `updateStrategy` covers StatefulSet and DaemonSet. |
| frontend.dnsConfig | object | `{}` | Pod DNS configuration, merged with `dnsPolicy` by the kubelet. |
| frontend.dnsPolicy | string | `""` (`ClusterFirstWithHostNet` when `hostNetwork` is true) | Pod DNS policy. Left empty, it defaults to `ClusterFirstWithHostNet` when `hostNetwork` is true (otherwise a hostNetwork pod silently stops resolving cluster DNS) and to the Kubernetes default `ClusterFirst` when it isn't. |
| frontend.enableServiceLinks | bool | `false` | Inject the legacy `{SVC}_SERVICE_HOST`/`_PORT` environment variables for every Service in the namespace. Defaults to false: the variables are rarely used, leak the namespace's topology into every container, and can collide with the app's own configuration. Set to true only for an app that genuinely reads them. |
| frontend.env | object | `{}` | Map or array of environment variables to inject into the app container (`valueFrom` supported). |
| frontend.envCm | object | `{}` | Map of environment variables to inject into a configmap loaded by the app container (`valueFrom` not supported). |
| frontend.envFrom | list | `[]` | Frontend container env variables loaded from configmap or secret reference. List or map (merged with `global.envFrom` above, global entries first); see `global.envFrom` for both forms. |
| frontend.envSecret | object | `{}` | Map of environment variables to inject into a secret loaded by the app container (`valueFrom` not supported). Values placed here are stored in plain text in the values file AND in the Helm release secret, so use it for non-sensitive-but-secret-shaped config only. For real credentials prefer referencing a Secret you manage elsewhere via `envFrom`, or have an operator materialise it (see the `VaultStaticSecret` example under `extraObjects`). |
| frontend.extraContainers | list | `[]` | Extra containers to add to the app pod as sidecars. |
| frontend.extraPorts | list | `[]` | Frontend extra container ports. |
| frontend.extraVolumeClaims | list | `[]` | Additional volumeClaims to add, concatenated with `volumeClaims` above at render time. |
| frontend.extraVolumeMounts | list | `[]` | Additional volumeMounts to add, concatenated with `volumeMounts` above at render time. |
| frontend.extraVolumes | list | `[]` | Additional volumes to add, concatenated with `volumes` above at render time (e.g. to mount a cert or config from a values override without repeating the chart's own volumes). |
| frontend.hostAliases | list | `[]` | Host aliases that will be injected at pod-level into /etc/hosts. |
| frontend.hostNetwork | bool | `false` | Share the host network namespace. Container ports then bind directly on the node, so they must not collide with anything else running there. |
| frontend.hostPID | bool | `false` | Share the host PID namespace (lets the container see and signal host processes). |
| frontend.imagePullSecrets | list | `[]` | Image credentials configuration. |
| frontend.initContainers | list | `[]` | Init containers to add to the app pod. |
| frontend.nodeSelector | object | `{}` | Default node selector for app. |
| frontend.podAnnotations | object | `{}` | Annotations for the app deployed pods. |
| frontend.podLabels | object | `{}` | Labels for the app deployed pods. |
| frontend.podSecurityContext | object | `{"fsGroup":1000,"fsGroupChangePolicy":"OnRootMismatch","runAsGroup":1000,"runAsNonRoot":true,"runAsUser":1000,"seccompProfile":{"type":"RuntimeDefault"}}` | Pod-level security context. Defaults to a hardened baseline that satisfies the `restricted` Pod Security Standard. Rendered via `toYaml`, so any `PodSecurityContext` field is accepted. Adjust the UID/GID to whatever your image actually ships with - `runAsNonRoot` makes the kubelet refuse to start a container that would run as root, which is the intended failure mode rather than something to switch off. Set to `null` to omit the block entirely. |
| frontend.priorityClassName | string | `""` | PriorityClass to schedule the pods with (e.g. `system-node-critical` for a node agent that must not be evicted under pressure). |
| frontend.replicaCount | int | `1` | The number of application controller pods to run. Ignored when `deploymentType` is "DaemonSet" (one pod per node) or when `autoscaling.enabled` is true. |
| frontend.revisionHistoryLimit | int | `10` | Revision history limit for the app. |
| frontend.securityContext | object | `{"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]},"privileged":false,"readOnlyRootFilesystem":true,"runAsGroup":1000,"runAsNonRoot":true,"runAsUser":1000}` | Container-level security context. Defaults to a hardened baseline that satisfies the `restricted` Pod Security Standard: no privilege escalation, no capabilities, immutable root filesystem. Rendered via `toYaml`, so any `SecurityContext` field is accepted. Note `readOnlyRootFilesystem` requires the app to write only to mounted volumes - the default `volumes`/`volumeMounts` below provide an `emptyDir` on /tmp for that reason. Set to `null` to omit the block entirely. |
| frontend.terminationGracePeriodSeconds | int | `null` (Kubernetes default of 30) | Grace period, in seconds, given to the pod to shut down cleanly before it is killed. |
| frontend.tolerations | list | `[]` | Default tolerations for app. |
| frontend.topologySpreadConstraints | list | `[]` | Topology spread constraints used to spread the pods across failure domains. |
| frontend.updateStrategy | object | `{}` | Update strategy applied when `deploymentType` is "StatefulSet" or "DaemonSet" (ignored for a Deployment, which uses `strategy` above). Rendered verbatim via `toYaml`, so it takes the native `StatefulSetUpdateStrategy`/`DaemonSetUpdateStrategy` shape of the selected kind; left empty, Kubernetes applies its own default (`RollingUpdate` for both). |
| frontend.volumeClaims | list | `[]` | List of volumeClaims to add, rendered as the StatefulSet's `volumeClaimTemplates`. Requires `deploymentType: "StatefulSet"` - setting it on a Deployment or DaemonSet fails at render time rather than being silently dropped (use `volumes`/`extraVolumes` there instead). |
| frontend.volumeMounts | list | `[{"mountPath":"/tmp","name":"tmp"}]` | List of mounts to add (normally used with `volumes` or `volumeClaims`). Prefer this for mounts the chart itself always needs; use `extraVolumeMounts` below for anything you add on top, so overriding one doesn't require repeating the other. Defaults to the `/tmp` mount backing the hardened `readOnlyRootFilesystem` default (see `volumes` above). |
| frontend.volumes | list | `[{"emptyDir":{},"name":"tmp"}]` | List of volumes to add. Prefer this for volumes the chart itself always needs (e.g. security-hardening `emptyDir`s); use `extraVolumes` below for anything you add on top, so overriding one doesn't require repeating the other. Defaults to a `/tmp` `emptyDir`, which is what makes the default `securityContext.readOnlyRootFilesystem: true` usable - drop it only if you also relax that. Helm replaces lists wholesale rather than merging them, so overriding this key means restating the entries you want to keep. |

#### Autoscaling

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| frontend.autoscaling.enabled | bool | `false` | Enable Horizontal Pod Autoscaler for the app. |
| frontend.autoscaling.maxReplicas | int | `3` | Maximum number of replicas for the app. |
| frontend.autoscaling.minReplicas | int | `1` | Minimum number of replicas for the app. |
| frontend.autoscaling.targetCPUUtilizationPercentage | int | `80` | Average CPU utilization percentage for the app. |
| frontend.autoscaling.targetMemoryUtilizationPercentage | int | `80` | Average memory utilization percentage for the app. |

#### GrpcRoute

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| frontend.grpcRoute.annotations | object | `{}` | Additional GRPCRoute annotations. |
| frontend.grpcRoute.enabled | bool | `false` | Enable a GRPCRoute resource for this service. |
| frontend.grpcRoute.hostnames | list | `[]` | Hostnames for the GRPCRoute to match. |
| frontend.grpcRoute.labels | object | `{}` | Additional GRPCRoute labels. |
| frontend.grpcRoute.parentRefs | list | `[]` | Parent references (Gateways) to attach the GRPCRoute to. |
| frontend.grpcRoute.rules | list | `[]` | Routing rules for the GRPCRoute. |

#### HttpRoute

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| frontend.httpRoute.annotations | object | `{}` | Additional HTTPRoute annotations. |
| frontend.httpRoute.enabled | bool | `false` | Enable an HTTPRoute resource for this service. |
| frontend.httpRoute.hostnames | list | `[]` | Hostnames for the HTTPRoute to match. |
| frontend.httpRoute.labels | object | `{}` | Additional HTTPRoute labels. |
| frontend.httpRoute.parentRefs | list | `[]` | Parent references (Gateways) to attach the HTTPRoute to. |
| frontend.httpRoute.rules | list | `[]` | Routing rules for the HTTPRoute. |

#### Image

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| frontend.image.digest | string | `""` | Image digest (`sha256:...`). When set it takes precedence over `tag`, pinning the exact image content so the same release can never resolve to a different build - preferred over a mutable tag for anything you deploy to production. |
| frontend.image.pullPolicy | string | `"IfNotPresent"` | Image pull policy for the app. |
| frontend.image.registry | string | `"ghcr.io"` | Registry to use for the app. |
| frontend.image.repository | string | `"mitchou10/spreadsheet-analyser/frontend"` | Repository to use for the app. |
| frontend.image.tag | string | `""` | Tag to use for the app. Overrides the image tag whose default is the chart appVersion. |

#### Ingress

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| frontend.ingress.annotations | object | `{}` | Additional ingress annotations. |
| frontend.ingress.className | string | `""` | Defines which ingress controller will implement the resource. |
| frontend.ingress.enabled | bool | `false` | Whether or not ingress should be enabled. |
| frontend.ingress.hosts[0].name | string | `"domain.local"` | Name of the host record. |
| frontend.ingress.hosts[0].paths | list | `[{"backend":{"portNumber":null,"serviceName":""},"path":"/","pathType":"Prefix"}]` | Paths of the host record to manage routing (avoids repeating the same host for multiple paths/backends). |
| frontend.ingress.hosts[0].paths[0].backend.portNumber | string | `nil` | Port used by the backend service linked to the path (leave null to use the app service port). |
| frontend.ingress.hosts[0].paths[0].backend.serviceName | string | `""` | Name of the backend service linked to the path (leave empty to use the app service). |
| frontend.ingress.hosts[0].paths[0].path | string | `"/"` | Path of the host record to manage routing. |
| frontend.ingress.hosts[0].paths[0].pathType | string | `"Prefix"` | Path type of the host record. |
| frontend.ingress.labels | object | `{}` | Additional ingress labels. |
| frontend.ingress.tls | list | `[]` | Enable TLS configuration. |

#### Metrics

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| frontend.metrics.enabled | bool | `false` | Deploy metrics service. |
| frontend.metrics.service.annotations | object | `{}` | Metrics service annotations. |
| frontend.metrics.service.labels | object | `{}` | Metrics service labels. |
| frontend.metrics.service.port | int | `9000` | Metrics service port. |
| frontend.metrics.service.portName | string | `"metrics"` | Metrics service port name. |
| frontend.metrics.service.targetPort | int | `9000` | Metrics service target port. |
| frontend.metrics.service.type | string | `"ClusterIP"` | Type of metrics service to create. |
| frontend.metrics.serviceMonitor.annotations | object | `{}` | Prometheus ServiceMonitor annotations. |
| frontend.metrics.serviceMonitor.enabled | bool | `false` | Enable a prometheus ServiceMonitor. |
| frontend.metrics.serviceMonitor.endpoints[0].basicAuth.password | string | `""` | The secret in the service monitor namespace that contains the password for authentication. |
| frontend.metrics.serviceMonitor.endpoints[0].basicAuth.username | string | `""` | The secret in the service monitor namespace that contains the username for authentication. |
| frontend.metrics.serviceMonitor.endpoints[0].bearerTokenSecret.key | string | `""` | Secret key to mount to read bearer token for scraping targets. The secret needs to be in the same namespace as the service monitor and accessible by the Prometheus Operator. |
| frontend.metrics.serviceMonitor.endpoints[0].bearerTokenSecret.name | string | `""` | Secret name to mount to read bearer token for scraping targets. The secret needs to be in the same namespace as the service monitor and accessible by the Prometheus Operator. |
| frontend.metrics.serviceMonitor.endpoints[0].honorLabels | bool | `false` | When true, honorLabels preserves the metric’s labels when they collide with the target’s labels. |
| frontend.metrics.serviceMonitor.endpoints[0].interval | string | `"30s"` | Prometheus ServiceMonitor interval. |
| frontend.metrics.serviceMonitor.endpoints[0].metricRelabelings | list | `[]` | Prometheus MetricRelabelConfigs to apply to samples before ingestion. |
| frontend.metrics.serviceMonitor.endpoints[0].path | string | `"/metrics"` | Path used by the Prometheus ServiceMonitor to scrape metrics. |
| frontend.metrics.serviceMonitor.endpoints[0].relabelings | list | `[]` | Prometheus RelabelConfigs to apply to samples before scraping. |
| frontend.metrics.serviceMonitor.endpoints[0].scheme | string | `""` | Prometheus ServiceMonitor scheme. |
| frontend.metrics.serviceMonitor.endpoints[0].scrapeTimeout | string | `"10s"` | Prometheus ServiceMonitor scrapeTimeout. If empty, Prometheus uses the global scrape timeout unless it is less than the target's scrape interval value in which the latter is used. |
| frontend.metrics.serviceMonitor.endpoints[0].selector | object | `{}` | Prometheus ServiceMonitor selector. |
| frontend.metrics.serviceMonitor.endpoints[0].tlsConfig | object | `{}` | Prometheus ServiceMonitor tlsConfig. |
| frontend.metrics.serviceMonitor.labels | object | `{}` | Prometheus ServiceMonitor labels. |

#### NetworkPolicy

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| frontend.networkPolicy.annotations | object | `{}` | Annotations to be added to the app NetworkPolicy. |
| frontend.networkPolicy.create | bool | `false` | Create NetworkPolicy object for the app. The policy always selects this component's pods only (via its selector labels), never the whole namespace. |
| frontend.networkPolicy.egress | list | `[]` | Egress rules for the NetworkPolicy object. |
| frontend.networkPolicy.ingress | list | `[]` | Ingress rules for the NetworkPolicy object. |
| frontend.networkPolicy.labels | object | `{}` | Labels to be added to the app NetworkPolicy. |
| frontend.networkPolicy.policyTypes | list | `["Ingress"]` | Policy types used in the NetworkPolicy object. |

#### Pdb

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| frontend.pdb.annotations | object | `{}` | Annotations to be added to app pdb. |
| frontend.pdb.enabled | bool | `false` | Deploy a PodDisruptionBudget for the app |
| frontend.pdb.labels | object | `{}` | Labels to be added to app pdb. |
| frontend.pdb.maxUnavailable | string | `""` | Number of pods that are unavailable after eviction as number or percentage (eg.: 50%). Has higher precedence over `frontend.pdb.minAvailable`. |
| frontend.pdb.minAvailable | string | `""` | Number of pods that are available after eviction as number or percentage (eg.: 50%). One of `minAvailable` / `maxUnavailable` must be set when `pdb.enabled` is true - a budget of 0 is the same as having no budget at all, so leaving both empty fails at render time. |

#### Probes

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| frontend.probes.livenessProbe.failureThreshold | int | `3` | Minimum consecutive failures for the probe to be considered failed after having succeeded. |
| frontend.probes.livenessProbe.httpGet.path | string | `"/"` | Frontend container healthcheck endpoint (livenessProbe is defined using `toYaml` so it is possible to override it completely). |
| frontend.probes.livenessProbe.httpGet.port | int | `8080` | Port to use for healthcheck (defaults to container port). |
| frontend.probes.livenessProbe.initialDelaySeconds | int | `30` | Number of seconds after the container has started before probe is initiated. |
| frontend.probes.livenessProbe.periodSeconds | int | `30` | How often (in seconds) to perform the probe. |
| frontend.probes.livenessProbe.successThreshold | int | `1` | Minimum consecutive successes for the probe to be considered successful after having failed. |
| frontend.probes.livenessProbe.timeoutSeconds | int | `5` | Number of seconds after which the probe times out. |
| frontend.probes.readinessProbe.failureThreshold | int | `2` | Minimum consecutive failures for the probe to be considered failed after having succeeded. |
| frontend.probes.readinessProbe.httpGet.path | string | `"/"` | Frontend container healthcheck endpoint (readinessProbe is defined using `toYaml` so it is possible to override it completely). |
| frontend.probes.readinessProbe.httpGet.port | int | `8080` | Port to use for healthcheck (defaults to container port). |
| frontend.probes.readinessProbe.initialDelaySeconds | int | `10` | Number of seconds after the container has started before probe is initiated. |
| frontend.probes.readinessProbe.periodSeconds | int | `10` | How often (in seconds) to perform the probe. |
| frontend.probes.readinessProbe.successThreshold | int | `2` | Minimum consecutive successes for the probe to be considered successful after having failed. |
| frontend.probes.readinessProbe.timeoutSeconds | int | `5` | Number of seconds after which the probe times out. |
| frontend.probes.startupProbe.failureThreshold | int | `10` | Minimum consecutive failures for the probe to be considered failed after having succeeded. |
| frontend.probes.startupProbe.httpGet.path | string | `"/"` | Frontend container healthcheck endpoint (startupProbe is defined using `toYaml` so it is possible to override it completely). |
| frontend.probes.startupProbe.httpGet.port | int | `8080` | Port to use for healthcheck (defaults to container port). |
| frontend.probes.startupProbe.initialDelaySeconds | int | `0` | Number of seconds after the container has started before probe is initiated. |
| frontend.probes.startupProbe.periodSeconds | int | `10` | How often (in seconds) to perform the probe. |
| frontend.probes.startupProbe.successThreshold | int | `1` | Minimum consecutive successes for the probe to be considered successful after having failed. |
| frontend.probes.startupProbe.timeoutSeconds | int | `5` | Number of seconds after which the probe times out. |

#### Resources

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| frontend.resources.limits.cpu | string | `"500m"` | CPU limit for the app. |
| frontend.resources.limits.memory | string | `"2Gi"` | Memory limit for the app. |
| frontend.resources.requests.cpu | string | `"100m"` | CPU request for the app. |
| frontend.resources.requests.memory | string | `"256Mi"` | Memory request for the app. |

#### Service

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| frontend.service.enabled | bool | `true` | Whether or not to create a Service for the app. Set to `false` for components that don't accept traffic (e.g. a queue consumer with no `containerPort`). |
| frontend.service.extraPorts | list | `[]` | Extra service ports. |
| frontend.service.nodePort | int | `null` (allocated by Kubernetes) | Port used when type is `NodePort` to expose the service on the given node port. Left empty, Kubernetes allocates one from the configured node-port range, which avoids two releases of this chart colliding on the same hardcoded port. |
| frontend.service.port | int | `80` | Port used by the service. |
| frontend.service.portName | string | `"http"` | Port name used by the service. |
| frontend.service.protocol | string | `"TCP"` | Protocol used by the service. |
| frontend.service.type | string | `"ClusterIP"` | Type of service to create for the app. |

#### ServiceAccount

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| frontend.serviceAccount.annotations | object | `{}` | Annotations applied to created service account. |
| frontend.serviceAccount.automountServiceAccountToken | bool | `false` | Should the service account access token be automount in the pod. |
| frontend.serviceAccount.clusterRole.create | bool | `false` | Should the clusterRole be created. |
| frontend.serviceAccount.clusterRole.rules | list | `[]` | ClusterRole rules associated with the service account. |
| frontend.serviceAccount.create | bool | `false` | Create a service account. |
| frontend.serviceAccount.enabled | bool | `false` | Enable the service account. |
| frontend.serviceAccount.name | string | `""` | Service account name. |
| frontend.serviceAccount.role.create | bool | `false` | Should the role be created. |
| frontend.serviceAccount.role.rules | list | `[]` | Role rules associated with the service account. |

#### Strategy

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| frontend.strategy.rollingUpdate.maxSurge | int | `1` | The maximum number of pods that can be scheduled above the desired number of pods. |
| frontend.strategy.rollingUpdate.maxUnavailable | int | `1` | The maximum number of pods that can be unavailable during the update process. |
| frontend.strategy.type | string | `"RollingUpdate"` | Strategy type used to replace old Pods by new ones, can be `Recreate` or `RollingUpdate`. Only applied when `deploymentType` is "Deployment". |

### Gateway

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| gateway.addresses | list | `[]` | Gateway addresses configuration. |
| gateway.annotations | object | `{}` | Additional gateway annotations. |
| gateway.className | string | `""` | GatewayClass name. Required when creating a Gateway. |
| gateway.create | bool | `false` | Create a Gateway resource. Usually, you reference an existing Gateway managed by the infrastructure team. |
| gateway.labels | object | `{}` | Additional gateway labels. |
| gateway.listeners | list | `[]` | Gateway listeners configuration. |
| gateway.name | string | `""` | Name of the Gateway resource. If not set, uses the release fullname. |

### IndexWorker

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| index_worker.affinity | object | `{}` | Affinity used for app pod. |
| index_worker.args | list | `[]` | Index_worker container command args. |
| index_worker.automountServiceAccountToken | bool | `false` | Mount the ServiceAccount token into the app pods. Defaults to false so a compromised container holds no API credentials; the API server does not need the token unless the app actually talks to the Kubernetes API. Applied at pod level so it holds even when `serviceAccount.name` points at an SA that automounts. |
| index_worker.command | list | `[]` | Index_worker container command. |
| index_worker.containerPort | string | `nil` | Index_worker container port number. Set to `null`/`0` (and disable `service`/probes) for components that don't listen on any port (e.g. a queue consumer). |
| index_worker.containerPortName | string | `"http"` | Index_worker container port name. |
| index_worker.deploymentType | string | `"Deployment"` | Workload kind to deploy the app as. One of "Deployment", "StatefulSet" or "DaemonSet" (validated at render time - an unknown value fails instead of producing a release with no workload). Use the top-level `jobs` / `cronjobs` maps for one-off or scheduled workloads. Some values only apply to certain kinds: `replicaCount`/`autoscaling` and `strategy` are Deployment-only (`autoscaling` also works on a StatefulSet), `volumeClaims`/`extraVolumeClaims` are StatefulSet-only, and `updateStrategy` covers StatefulSet and DaemonSet. |
| index_worker.dnsConfig | object | `{}` | Pod DNS configuration, merged with `dnsPolicy` by the kubelet. |
| index_worker.dnsPolicy | string | `""` (`ClusterFirstWithHostNet` when `hostNetwork` is true) | Pod DNS policy. Left empty, it defaults to `ClusterFirstWithHostNet` when `hostNetwork` is true (otherwise a hostNetwork pod silently stops resolving cluster DNS) and to the Kubernetes default `ClusterFirst` when it isn't. |
| index_worker.enableServiceLinks | bool | `false` | Inject the legacy `{SVC}_SERVICE_HOST`/`_PORT` environment variables for every Service in the namespace. Defaults to false: the variables are rarely used, leak the namespace's topology into every container, and can collide with the app's own configuration. Set to true only for an app that genuinely reads them. |
| index_worker.env | object | `{}` | Map or array of environment variables to inject into the app container (`valueFrom` supported). |
| index_worker.envCm | object | `{}` | Map of environment variables to inject into a configmap loaded by the app container (`valueFrom` not supported). |
| index_worker.envFrom | list | `[]` | Index_worker container env variables loaded from configmap or secret reference. List or map (merged with `global.envFrom` above, global entries first); see `global.envFrom` for both forms. |
| index_worker.envSecret | object | `{}` | Map of environment variables to inject into a secret loaded by the app container (`valueFrom` not supported). Values placed here are stored in plain text in the values file AND in the Helm release secret, so use it for non-sensitive-but-secret-shaped config only. For real credentials prefer referencing a Secret you manage elsewhere via `envFrom`, or have an operator materialise it (see the `VaultStaticSecret` example under `extraObjects`). |
| index_worker.extraContainers | list | `[]` | Extra containers to add to the app pod as sidecars. |
| index_worker.extraPorts | list | `[]` | Index_worker extra container ports. |
| index_worker.extraVolumeClaims | list | `[]` | Additional volumeClaims to add, concatenated with `volumeClaims` above at render time. |
| index_worker.extraVolumeMounts | list | `[]` | Additional volumeMounts to add, concatenated with `volumeMounts` above at render time. |
| index_worker.extraVolumes | list | `[]` | Additional volumes to add, concatenated with `volumes` above at render time (e.g. to mount a cert or config from a values override without repeating the chart's own volumes). |
| index_worker.hostAliases | list | `[]` | Host aliases that will be injected at pod-level into /etc/hosts. |
| index_worker.hostNetwork | bool | `false` | Share the host network namespace. Container ports then bind directly on the node, so they must not collide with anything else running there. |
| index_worker.hostPID | bool | `false` | Share the host PID namespace (lets the container see and signal host processes). |
| index_worker.imagePullSecrets | list | `[]` | Image credentials configuration. |
| index_worker.initContainers | list | `[]` | Init containers to add to the app pod. |
| index_worker.nodeSelector | object | `{}` | Default node selector for app. |
| index_worker.podAnnotations | object | `{}` | Annotations for the app deployed pods. |
| index_worker.podLabels | object | `{}` | Labels for the app deployed pods. |
| index_worker.podSecurityContext | object | `{"fsGroup":1000,"fsGroupChangePolicy":"OnRootMismatch","runAsGroup":1000,"runAsNonRoot":true,"runAsUser":1000,"seccompProfile":{"type":"RuntimeDefault"}}` | Pod-level security context. Defaults to a hardened baseline that satisfies the `restricted` Pod Security Standard. Rendered via `toYaml`, so any `PodSecurityContext` field is accepted. Adjust the UID/GID to whatever your image actually ships with - `runAsNonRoot` makes the kubelet refuse to start a container that would run as root, which is the intended failure mode rather than something to switch off. Set to `null` to omit the block entirely. |
| index_worker.priorityClassName | string | `""` | PriorityClass to schedule the pods with (e.g. `system-node-critical` for a node agent that must not be evicted under pressure). |
| index_worker.replicaCount | int | `1` | The number of application controller pods to run. Ignored when `deploymentType` is "DaemonSet" (one pod per node) or when `autoscaling.enabled` is true. |
| index_worker.revisionHistoryLimit | int | `10` | Revision history limit for the app. |
| index_worker.securityContext | object | `{"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]},"privileged":false,"readOnlyRootFilesystem":true,"runAsGroup":1000,"runAsNonRoot":true,"runAsUser":1000}` | Container-level security context. Defaults to a hardened baseline that satisfies the `restricted` Pod Security Standard: no privilege escalation, no capabilities, immutable root filesystem. Rendered via `toYaml`, so any `SecurityContext` field is accepted. Note `readOnlyRootFilesystem` requires the app to write only to mounted volumes - the default `volumes`/`volumeMounts` below provide an `emptyDir` on /tmp for that reason. Set to `null` to omit the block entirely. |
| index_worker.terminationGracePeriodSeconds | int | `null` (Kubernetes default of 30) | Grace period, in seconds, given to the pod to shut down cleanly before it is killed. |
| index_worker.tolerations | list | `[]` | Default tolerations for app. |
| index_worker.topologySpreadConstraints | list | `[]` | Topology spread constraints used to spread the pods across failure domains. |
| index_worker.updateStrategy | object | `{}` | Update strategy applied when `deploymentType` is "StatefulSet" or "DaemonSet" (ignored for a Deployment, which uses `strategy` above). Rendered verbatim via `toYaml`, so it takes the native `StatefulSetUpdateStrategy`/`DaemonSetUpdateStrategy` shape of the selected kind; left empty, Kubernetes applies its own default (`RollingUpdate` for both). |
| index_worker.volumeClaims | list | `[]` | List of volumeClaims to add, rendered as the StatefulSet's `volumeClaimTemplates`. Requires `deploymentType: "StatefulSet"` - setting it on a Deployment or DaemonSet fails at render time rather than being silently dropped (use `volumes`/`extraVolumes` there instead). |
| index_worker.volumeMounts | list | `[{"mountPath":"/tmp","name":"tmp"}]` | List of mounts to add (normally used with `volumes` or `volumeClaims`). Prefer this for mounts the chart itself always needs; use `extraVolumeMounts` below for anything you add on top, so overriding one doesn't require repeating the other. Defaults to the `/tmp` mount backing the hardened `readOnlyRootFilesystem` default (see `volumes` above). |
| index_worker.volumes | list | `[{"emptyDir":{},"name":"tmp"}]` | List of volumes to add. Prefer this for volumes the chart itself always needs (e.g. security-hardening `emptyDir`s); use `extraVolumes` below for anything you add on top, so overriding one doesn't require repeating the other. Defaults to a `/tmp` `emptyDir`, which is what makes the default `securityContext.readOnlyRootFilesystem: true` usable - drop it only if you also relax that. Helm replaces lists wholesale rather than merging them, so overriding this key means restating the entries you want to keep. |

#### Autoscaling

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| index_worker.autoscaling.enabled | bool | `false` | Enable Horizontal Pod Autoscaler for the app. |
| index_worker.autoscaling.maxReplicas | int | `3` | Maximum number of replicas for the app. |
| index_worker.autoscaling.minReplicas | int | `1` | Minimum number of replicas for the app. |
| index_worker.autoscaling.targetCPUUtilizationPercentage | int | `80` | Average CPU utilization percentage for the app. |
| index_worker.autoscaling.targetMemoryUtilizationPercentage | int | `80` | Average memory utilization percentage for the app. |

#### GrpcRoute

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| index_worker.grpcRoute.annotations | object | `{}` | Additional GRPCRoute annotations. |
| index_worker.grpcRoute.enabled | bool | `false` | Enable a GRPCRoute resource for this service. |
| index_worker.grpcRoute.hostnames | list | `[]` | Hostnames for the GRPCRoute to match. |
| index_worker.grpcRoute.labels | object | `{}` | Additional GRPCRoute labels. |
| index_worker.grpcRoute.parentRefs | list | `[]` | Parent references (Gateways) to attach the GRPCRoute to. |
| index_worker.grpcRoute.rules | list | `[]` | Routing rules for the GRPCRoute. |

#### HttpRoute

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| index_worker.httpRoute.annotations | object | `{}` | Additional HTTPRoute annotations. |
| index_worker.httpRoute.enabled | bool | `false` | Enable an HTTPRoute resource for this service. |
| index_worker.httpRoute.hostnames | list | `[]` | Hostnames for the HTTPRoute to match. |
| index_worker.httpRoute.labels | object | `{}` | Additional HTTPRoute labels. |
| index_worker.httpRoute.parentRefs | list | `[]` | Parent references (Gateways) to attach the HTTPRoute to. |
| index_worker.httpRoute.rules | list | `[]` | Routing rules for the HTTPRoute. |

#### Image

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| index_worker.image.digest | string | `""` | Image digest (`sha256:...`). When set it takes precedence over `tag`, pinning the exact image content so the same release can never resolve to a different build - preferred over a mutable tag for anything you deploy to production. |
| index_worker.image.pullPolicy | string | `"IfNotPresent"` | Image pull policy for the app. |
| index_worker.image.registry | string | `"ghcr.io"` | Registry to use for the app. |
| index_worker.image.repository | string | `"mitchou10/spreadsheet-analyser/index-worker"` | Repository to use for the app. |
| index_worker.image.tag | string | `""` | Tag to use for the app. Overrides the image tag whose default is the chart appVersion. |

#### Ingress

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| index_worker.ingress.annotations | object | `{}` | Additional ingress annotations. |
| index_worker.ingress.className | string | `""` | Defines which ingress controller will implement the resource. |
| index_worker.ingress.enabled | bool | `false` | Whether or not ingress should be enabled. |
| index_worker.ingress.hosts[0].name | string | `"domain.local"` | Name of the host record. |
| index_worker.ingress.hosts[0].paths | list | `[{"backend":{"portNumber":null,"serviceName":""},"path":"/","pathType":"Prefix"}]` | Paths of the host record to manage routing (avoids repeating the same host for multiple paths/backends). |
| index_worker.ingress.hosts[0].paths[0].backend.portNumber | string | `nil` | Port used by the backend service linked to the path (leave null to use the app service port). |
| index_worker.ingress.hosts[0].paths[0].backend.serviceName | string | `""` | Name of the backend service linked to the path (leave empty to use the app service). |
| index_worker.ingress.hosts[0].paths[0].path | string | `"/"` | Path of the host record to manage routing. |
| index_worker.ingress.hosts[0].paths[0].pathType | string | `"Prefix"` | Path type of the host record. |
| index_worker.ingress.labels | object | `{}` | Additional ingress labels. |
| index_worker.ingress.tls | list | `[]` | Enable TLS configuration. |

#### Metrics

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| index_worker.metrics.enabled | bool | `false` | Deploy metrics service. |
| index_worker.metrics.service.annotations | object | `{}` | Metrics service annotations. |
| index_worker.metrics.service.labels | object | `{}` | Metrics service labels. |
| index_worker.metrics.service.port | int | `9000` | Metrics service port. |
| index_worker.metrics.service.portName | string | `"metrics"` | Metrics service port name. |
| index_worker.metrics.service.targetPort | int | `9000` | Metrics service target port. |
| index_worker.metrics.service.type | string | `"ClusterIP"` | Type of metrics service to create. |
| index_worker.metrics.serviceMonitor.annotations | object | `{}` | Prometheus ServiceMonitor annotations. |
| index_worker.metrics.serviceMonitor.enabled | bool | `false` | Enable a prometheus ServiceMonitor. |
| index_worker.metrics.serviceMonitor.endpoints[0].basicAuth.password | string | `""` | The secret in the service monitor namespace that contains the password for authentication. |
| index_worker.metrics.serviceMonitor.endpoints[0].basicAuth.username | string | `""` | The secret in the service monitor namespace that contains the username for authentication. |
| index_worker.metrics.serviceMonitor.endpoints[0].bearerTokenSecret.key | string | `""` | Secret key to mount to read bearer token for scraping targets. The secret needs to be in the same namespace as the service monitor and accessible by the Prometheus Operator. |
| index_worker.metrics.serviceMonitor.endpoints[0].bearerTokenSecret.name | string | `""` | Secret name to mount to read bearer token for scraping targets. The secret needs to be in the same namespace as the service monitor and accessible by the Prometheus Operator. |
| index_worker.metrics.serviceMonitor.endpoints[0].honorLabels | bool | `false` | When true, honorLabels preserves the metric’s labels when they collide with the target’s labels. |
| index_worker.metrics.serviceMonitor.endpoints[0].interval | string | `"30s"` | Prometheus ServiceMonitor interval. |
| index_worker.metrics.serviceMonitor.endpoints[0].metricRelabelings | list | `[]` | Prometheus MetricRelabelConfigs to apply to samples before ingestion. |
| index_worker.metrics.serviceMonitor.endpoints[0].path | string | `"/metrics"` | Path used by the Prometheus ServiceMonitor to scrape metrics. |
| index_worker.metrics.serviceMonitor.endpoints[0].relabelings | list | `[]` | Prometheus RelabelConfigs to apply to samples before scraping. |
| index_worker.metrics.serviceMonitor.endpoints[0].scheme | string | `""` | Prometheus ServiceMonitor scheme. |
| index_worker.metrics.serviceMonitor.endpoints[0].scrapeTimeout | string | `"10s"` | Prometheus ServiceMonitor scrapeTimeout. If empty, Prometheus uses the global scrape timeout unless it is less than the target's scrape interval value in which the latter is used. |
| index_worker.metrics.serviceMonitor.endpoints[0].selector | object | `{}` | Prometheus ServiceMonitor selector. |
| index_worker.metrics.serviceMonitor.endpoints[0].tlsConfig | object | `{}` | Prometheus ServiceMonitor tlsConfig. |
| index_worker.metrics.serviceMonitor.labels | object | `{}` | Prometheus ServiceMonitor labels. |

#### NetworkPolicy

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| index_worker.networkPolicy.annotations | object | `{}` | Annotations to be added to the app NetworkPolicy. |
| index_worker.networkPolicy.create | bool | `false` | Create NetworkPolicy object for the app. The policy always selects this component's pods only (via its selector labels), never the whole namespace. |
| index_worker.networkPolicy.egress | list | `[]` | Egress rules for the NetworkPolicy object. |
| index_worker.networkPolicy.ingress | list | `[]` | Ingress rules for the NetworkPolicy object. |
| index_worker.networkPolicy.labels | object | `{}` | Labels to be added to the app NetworkPolicy. |
| index_worker.networkPolicy.policyTypes | list | `["Ingress"]` | Policy types used in the NetworkPolicy object. |

#### Pdb

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| index_worker.pdb.annotations | object | `{}` | Annotations to be added to app pdb. |
| index_worker.pdb.enabled | bool | `false` | Deploy a PodDisruptionBudget for the app |
| index_worker.pdb.labels | object | `{}` | Labels to be added to app pdb. |
| index_worker.pdb.maxUnavailable | string | `""` | Number of pods that are unavailable after eviction as number or percentage (eg.: 50%). Has higher precedence over `index_worker.pdb.minAvailable`. |
| index_worker.pdb.minAvailable | string | `""` | Number of pods that are available after eviction as number or percentage (eg.: 50%). One of `minAvailable` / `maxUnavailable` must be set when `pdb.enabled` is true - a budget of 0 is the same as having no budget at all, so leaving both empty fails at render time. |

#### Probes

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| index_worker.probes.livenessProbe.exec | object | `{"command":["sh","-c","celery -A app.celery_app inspect ping -d celery@$HOSTNAME"]}` | Index_worker container healthcheck (livenessProbe is defined using `toYaml` so it is possible to override it completely). Uses `celery inspect ping` since Celery workers don't expose an HTTP endpoint. It runs in a shell so that $HOSTNAME is the pod's real hostname (Kubernetes only expands `$(VAR)` for variables declared in the pod spec). |
| index_worker.probes.livenessProbe.failureThreshold | int | `3` | Minimum consecutive failures for the probe to be considered failed after having succeeded. |
| index_worker.probes.livenessProbe.initialDelaySeconds | int | `30` | Number of seconds after the container has started before probe is initiated. |
| index_worker.probes.livenessProbe.periodSeconds | int | `30` | How often (in seconds) to perform the probe. |
| index_worker.probes.livenessProbe.successThreshold | int | `1` | Minimum consecutive successes for the probe to be considered successful after having failed. |
| index_worker.probes.livenessProbe.timeoutSeconds | int | `10` | Number of seconds after which the probe times out. |
| index_worker.probes.readinessProbe.exec | object | `{"command":["sh","-c","celery -A app.celery_app inspect ping -d celery@$HOSTNAME"]}` | Index_worker container healthcheck (readinessProbe is defined using `toYaml` so it is possible to override it completely). Uses `celery inspect ping` since Celery workers don't expose an HTTP endpoint. It runs in a shell so that $HOSTNAME is the pod's real hostname (Kubernetes only expands `$(VAR)` for variables declared in the pod spec). |
| index_worker.probes.readinessProbe.failureThreshold | int | `2` | Minimum consecutive failures for the probe to be considered failed after having succeeded. |
| index_worker.probes.readinessProbe.initialDelaySeconds | int | `10` | Number of seconds after the container has started before probe is initiated. |
| index_worker.probes.readinessProbe.periodSeconds | int | `10` | How often (in seconds) to perform the probe. |
| index_worker.probes.readinessProbe.successThreshold | int | `2` | Minimum consecutive successes for the probe to be considered successful after having failed. |
| index_worker.probes.readinessProbe.timeoutSeconds | int | `10` | Number of seconds after which the probe times out. |
| index_worker.probes.startupProbe.exec | object | `{"command":["sh","-c","celery -A app.celery_app inspect ping -d celery@$HOSTNAME"]}` | Index_worker container healthcheck (startupProbe is defined using `toYaml` so it is possible to override it completely). Uses `celery inspect ping` since Celery workers don't expose an HTTP endpoint. It runs in a shell so that $HOSTNAME is the pod's real hostname (Kubernetes only expands `$(VAR)` for variables declared in the pod spec). |
| index_worker.probes.startupProbe.failureThreshold | int | `10` | Minimum consecutive failures for the probe to be considered failed after having succeeded. |
| index_worker.probes.startupProbe.initialDelaySeconds | int | `0` | Number of seconds after the container has started before probe is initiated. |
| index_worker.probes.startupProbe.periodSeconds | int | `10` | How often (in seconds) to perform the probe. |
| index_worker.probes.startupProbe.successThreshold | int | `1` | Minimum consecutive successes for the probe to be considered successful after having failed. |
| index_worker.probes.startupProbe.timeoutSeconds | int | `10` | Number of seconds after which the probe times out. |

#### Resources

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| index_worker.resources.limits.cpu | string | `"500m"` | CPU limit for the app. |
| index_worker.resources.limits.memory | string | `"2Gi"` | Memory limit for the app. |
| index_worker.resources.requests.cpu | string | `"100m"` | CPU request for the app. |
| index_worker.resources.requests.memory | string | `"256Mi"` | Memory request for the app. |

#### Service

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| index_worker.service.enabled | bool | `false` | Whether or not to create a Service for the app. Set to `false` for components that don't accept traffic (e.g. a queue consumer with no `containerPort`). |
| index_worker.service.extraPorts | list | `[]` | Extra service ports. |
| index_worker.service.nodePort | int | `null` (allocated by Kubernetes) | Port used when type is `NodePort` to expose the service on the given node port. Left empty, Kubernetes allocates one from the configured node-port range, which avoids two releases of this chart colliding on the same hardcoded port. |
| index_worker.service.port | int | `80` | Port used by the service. |
| index_worker.service.portName | string | `"http"` | Port name used by the service. |
| index_worker.service.protocol | string | `"TCP"` | Protocol used by the service. |
| index_worker.service.type | string | `"ClusterIP"` | Type of service to create for the app. |

#### ServiceAccount

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| index_worker.serviceAccount.annotations | object | `{}` | Annotations applied to created service account. |
| index_worker.serviceAccount.automountServiceAccountToken | bool | `false` | Should the service account access token be automount in the pod. |
| index_worker.serviceAccount.clusterRole.create | bool | `false` | Should the clusterRole be created. |
| index_worker.serviceAccount.clusterRole.rules | list | `[]` | ClusterRole rules associated with the service account. |
| index_worker.serviceAccount.create | bool | `false` | Create a service account. |
| index_worker.serviceAccount.enabled | bool | `false` | Enable the service account. |
| index_worker.serviceAccount.name | string | `""` | Service account name. |
| index_worker.serviceAccount.role.create | bool | `false` | Should the role be created. |
| index_worker.serviceAccount.role.rules | list | `[]` | Role rules associated with the service account. |

#### Strategy

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| index_worker.strategy.rollingUpdate.maxSurge | int | `1` | The maximum number of pods that can be scheduled above the desired number of pods. |
| index_worker.strategy.rollingUpdate.maxUnavailable | int | `1` | The maximum number of pods that can be unavailable during the update process. |
| index_worker.strategy.type | string | `"RollingUpdate"` | Strategy type used to replace old Pods by new ones, can be `Recreate` or `RollingUpdate`. Only applied when `deploymentType` is "Deployment". |

### QueryWorker

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| query_worker.affinity | object | `{}` | Affinity used for app pod. |
| query_worker.args | list | `[]` | Query_worker container command args. |
| query_worker.automountServiceAccountToken | bool | `false` | Mount the ServiceAccount token into the app pods. Defaults to false so a compromised container holds no API credentials; the API server does not need the token unless the app actually talks to the Kubernetes API. Applied at pod level so it holds even when `serviceAccount.name` points at an SA that automounts. |
| query_worker.command | list | `[]` | Query_worker container command. |
| query_worker.containerPort | string | `nil` | Query_worker container port number. Set to `null`/`0` (and disable `service`/probes) for components that don't listen on any port (e.g. a queue consumer). |
| query_worker.containerPortName | string | `"http"` | Query_worker container port name. |
| query_worker.deploymentType | string | `"Deployment"` | Workload kind to deploy the app as. One of "Deployment", "StatefulSet" or "DaemonSet" (validated at render time - an unknown value fails instead of producing a release with no workload). Use the top-level `jobs` / `cronjobs` maps for one-off or scheduled workloads. Some values only apply to certain kinds: `replicaCount`/`autoscaling` and `strategy` are Deployment-only (`autoscaling` also works on a StatefulSet), `volumeClaims`/`extraVolumeClaims` are StatefulSet-only, and `updateStrategy` covers StatefulSet and DaemonSet. |
| query_worker.dnsConfig | object | `{}` | Pod DNS configuration, merged with `dnsPolicy` by the kubelet. |
| query_worker.dnsPolicy | string | `""` (`ClusterFirstWithHostNet` when `hostNetwork` is true) | Pod DNS policy. Left empty, it defaults to `ClusterFirstWithHostNet` when `hostNetwork` is true (otherwise a hostNetwork pod silently stops resolving cluster DNS) and to the Kubernetes default `ClusterFirst` when it isn't. |
| query_worker.enableServiceLinks | bool | `false` | Inject the legacy `{SVC}_SERVICE_HOST`/`_PORT` environment variables for every Service in the namespace. Defaults to false: the variables are rarely used, leak the namespace's topology into every container, and can collide with the app's own configuration. Set to true only for an app that genuinely reads them. |
| query_worker.env | object | `{}` | Map or array of environment variables to inject into the app container (`valueFrom` supported). |
| query_worker.envCm | object | `{}` | Map of environment variables to inject into a configmap loaded by the app container (`valueFrom` not supported). |
| query_worker.envFrom | list | `[]` | Query_worker container env variables loaded from configmap or secret reference. List or map (merged with `global.envFrom` above, global entries first); see `global.envFrom` for both forms. |
| query_worker.envSecret | object | `{}` | Map of environment variables to inject into a secret loaded by the app container (`valueFrom` not supported). Values placed here are stored in plain text in the values file AND in the Helm release secret, so use it for non-sensitive-but-secret-shaped config only. For real credentials prefer referencing a Secret you manage elsewhere via `envFrom`, or have an operator materialise it (see the `VaultStaticSecret` example under `extraObjects`). |
| query_worker.extraContainers | list | `[]` | Extra containers to add to the app pod as sidecars. |
| query_worker.extraPorts | list | `[]` | Query_worker extra container ports. |
| query_worker.extraVolumeClaims | list | `[]` | Additional volumeClaims to add, concatenated with `volumeClaims` above at render time. |
| query_worker.extraVolumeMounts | list | `[]` | Additional volumeMounts to add, concatenated with `volumeMounts` above at render time. |
| query_worker.extraVolumes | list | `[]` | Additional volumes to add, concatenated with `volumes` above at render time (e.g. to mount a cert or config from a values override without repeating the chart's own volumes). |
| query_worker.hostAliases | list | `[]` | Host aliases that will be injected at pod-level into /etc/hosts. |
| query_worker.hostNetwork | bool | `false` | Share the host network namespace. Container ports then bind directly on the node, so they must not collide with anything else running there. |
| query_worker.hostPID | bool | `false` | Share the host PID namespace (lets the container see and signal host processes). |
| query_worker.imagePullSecrets | list | `[]` | Image credentials configuration. |
| query_worker.initContainers | list | `[]` | Init containers to add to the app pod. |
| query_worker.nodeSelector | object | `{}` | Default node selector for app. |
| query_worker.podAnnotations | object | `{}` | Annotations for the app deployed pods. |
| query_worker.podLabels | object | `{}` | Labels for the app deployed pods. |
| query_worker.podSecurityContext | object | `{"fsGroup":1000,"fsGroupChangePolicy":"OnRootMismatch","runAsGroup":1000,"runAsNonRoot":true,"runAsUser":1000,"seccompProfile":{"type":"RuntimeDefault"}}` | Pod-level security context. Defaults to a hardened baseline that satisfies the `restricted` Pod Security Standard. Rendered via `toYaml`, so any `PodSecurityContext` field is accepted. Adjust the UID/GID to whatever your image actually ships with - `runAsNonRoot` makes the kubelet refuse to start a container that would run as root, which is the intended failure mode rather than something to switch off. Set to `null` to omit the block entirely. |
| query_worker.priorityClassName | string | `""` | PriorityClass to schedule the pods with (e.g. `system-node-critical` for a node agent that must not be evicted under pressure). |
| query_worker.replicaCount | int | `1` | The number of application controller pods to run. Ignored when `deploymentType` is "DaemonSet" (one pod per node) or when `autoscaling.enabled` is true. |
| query_worker.revisionHistoryLimit | int | `10` | Revision history limit for the app. |
| query_worker.securityContext | object | `{"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]},"privileged":false,"readOnlyRootFilesystem":true,"runAsGroup":1000,"runAsNonRoot":true,"runAsUser":1000}` | Container-level security context. Defaults to a hardened baseline that satisfies the `restricted` Pod Security Standard: no privilege escalation, no capabilities, immutable root filesystem. Rendered via `toYaml`, so any `SecurityContext` field is accepted. Note `readOnlyRootFilesystem` requires the app to write only to mounted volumes - the default `volumes`/`volumeMounts` below provide an `emptyDir` on /tmp for that reason. Set to `null` to omit the block entirely. |
| query_worker.terminationGracePeriodSeconds | int | `null` (Kubernetes default of 30) | Grace period, in seconds, given to the pod to shut down cleanly before it is killed. |
| query_worker.tolerations | list | `[]` | Default tolerations for app. |
| query_worker.topologySpreadConstraints | list | `[]` | Topology spread constraints used to spread the pods across failure domains. |
| query_worker.updateStrategy | object | `{}` | Update strategy applied when `deploymentType` is "StatefulSet" or "DaemonSet" (ignored for a Deployment, which uses `strategy` above). Rendered verbatim via `toYaml`, so it takes the native `StatefulSetUpdateStrategy`/`DaemonSetUpdateStrategy` shape of the selected kind; left empty, Kubernetes applies its own default (`RollingUpdate` for both). |
| query_worker.volumeClaims | list | `[]` | List of volumeClaims to add, rendered as the StatefulSet's `volumeClaimTemplates`. Requires `deploymentType: "StatefulSet"` - setting it on a Deployment or DaemonSet fails at render time rather than being silently dropped (use `volumes`/`extraVolumes` there instead). |
| query_worker.volumeMounts | list | `[{"mountPath":"/tmp","name":"tmp"}]` | List of mounts to add (normally used with `volumes` or `volumeClaims`). Prefer this for mounts the chart itself always needs; use `extraVolumeMounts` below for anything you add on top, so overriding one doesn't require repeating the other. Defaults to the `/tmp` mount backing the hardened `readOnlyRootFilesystem` default (see `volumes` above). |
| query_worker.volumes | list | `[{"emptyDir":{},"name":"tmp"}]` | List of volumes to add. Prefer this for volumes the chart itself always needs (e.g. security-hardening `emptyDir`s); use `extraVolumes` below for anything you add on top, so overriding one doesn't require repeating the other. Defaults to a `/tmp` `emptyDir`, which is what makes the default `securityContext.readOnlyRootFilesystem: true` usable - drop it only if you also relax that. Helm replaces lists wholesale rather than merging them, so overriding this key means restating the entries you want to keep. |

#### Autoscaling

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| query_worker.autoscaling.enabled | bool | `false` | Enable Horizontal Pod Autoscaler for the app. |
| query_worker.autoscaling.maxReplicas | int | `3` | Maximum number of replicas for the app. |
| query_worker.autoscaling.minReplicas | int | `1` | Minimum number of replicas for the app. |
| query_worker.autoscaling.targetCPUUtilizationPercentage | int | `80` | Average CPU utilization percentage for the app. |
| query_worker.autoscaling.targetMemoryUtilizationPercentage | int | `80` | Average memory utilization percentage for the app. |

#### GrpcRoute

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| query_worker.grpcRoute.annotations | object | `{}` | Additional GRPCRoute annotations. |
| query_worker.grpcRoute.enabled | bool | `false` | Enable a GRPCRoute resource for this service. |
| query_worker.grpcRoute.hostnames | list | `[]` | Hostnames for the GRPCRoute to match. |
| query_worker.grpcRoute.labels | object | `{}` | Additional GRPCRoute labels. |
| query_worker.grpcRoute.parentRefs | list | `[]` | Parent references (Gateways) to attach the GRPCRoute to. |
| query_worker.grpcRoute.rules | list | `[]` | Routing rules for the GRPCRoute. |

#### HttpRoute

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| query_worker.httpRoute.annotations | object | `{}` | Additional HTTPRoute annotations. |
| query_worker.httpRoute.enabled | bool | `false` | Enable an HTTPRoute resource for this service. |
| query_worker.httpRoute.hostnames | list | `[]` | Hostnames for the HTTPRoute to match. |
| query_worker.httpRoute.labels | object | `{}` | Additional HTTPRoute labels. |
| query_worker.httpRoute.parentRefs | list | `[]` | Parent references (Gateways) to attach the HTTPRoute to. |
| query_worker.httpRoute.rules | list | `[]` | Routing rules for the HTTPRoute. |

#### Image

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| query_worker.image.digest | string | `""` | Image digest (`sha256:...`). When set it takes precedence over `tag`, pinning the exact image content so the same release can never resolve to a different build - preferred over a mutable tag for anything you deploy to production. |
| query_worker.image.pullPolicy | string | `"IfNotPresent"` | Image pull policy for the app. |
| query_worker.image.registry | string | `"ghcr.io"` | Registry to use for the app. |
| query_worker.image.repository | string | `"mitchou10/spreadsheet-analyser/analysis-worker"` | Repository to use for the app. |
| query_worker.image.tag | string | `""` | Tag to use for the app. Overrides the image tag whose default is the chart appVersion. |

#### Ingress

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| query_worker.ingress.annotations | object | `{}` | Additional ingress annotations. |
| query_worker.ingress.className | string | `""` | Defines which ingress controller will implement the resource. |
| query_worker.ingress.enabled | bool | `false` | Whether or not ingress should be enabled. |
| query_worker.ingress.hosts[0].name | string | `"domain.local"` | Name of the host record. |
| query_worker.ingress.hosts[0].paths | list | `[{"backend":{"portNumber":null,"serviceName":""},"path":"/","pathType":"Prefix"}]` | Paths of the host record to manage routing (avoids repeating the same host for multiple paths/backends). |
| query_worker.ingress.hosts[0].paths[0].backend.portNumber | string | `nil` | Port used by the backend service linked to the path (leave null to use the app service port). |
| query_worker.ingress.hosts[0].paths[0].backend.serviceName | string | `""` | Name of the backend service linked to the path (leave empty to use the app service). |
| query_worker.ingress.hosts[0].paths[0].path | string | `"/"` | Path of the host record to manage routing. |
| query_worker.ingress.hosts[0].paths[0].pathType | string | `"Prefix"` | Path type of the host record. |
| query_worker.ingress.labels | object | `{}` | Additional ingress labels. |
| query_worker.ingress.tls | list | `[]` | Enable TLS configuration. |

#### Metrics

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| query_worker.metrics.enabled | bool | `false` | Deploy metrics service. |
| query_worker.metrics.service.annotations | object | `{}` | Metrics service annotations. |
| query_worker.metrics.service.labels | object | `{}` | Metrics service labels. |
| query_worker.metrics.service.port | int | `9000` | Metrics service port. |
| query_worker.metrics.service.portName | string | `"metrics"` | Metrics service port name. |
| query_worker.metrics.service.targetPort | int | `9000` | Metrics service target port. |
| query_worker.metrics.service.type | string | `"ClusterIP"` | Type of metrics service to create. |
| query_worker.metrics.serviceMonitor.annotations | object | `{}` | Prometheus ServiceMonitor annotations. |
| query_worker.metrics.serviceMonitor.enabled | bool | `false` | Enable a prometheus ServiceMonitor. |
| query_worker.metrics.serviceMonitor.endpoints[0].basicAuth.password | string | `""` | The secret in the service monitor namespace that contains the password for authentication. |
| query_worker.metrics.serviceMonitor.endpoints[0].basicAuth.username | string | `""` | The secret in the service monitor namespace that contains the username for authentication. |
| query_worker.metrics.serviceMonitor.endpoints[0].bearerTokenSecret.key | string | `""` | Secret key to mount to read bearer token for scraping targets. The secret needs to be in the same namespace as the service monitor and accessible by the Prometheus Operator. |
| query_worker.metrics.serviceMonitor.endpoints[0].bearerTokenSecret.name | string | `""` | Secret name to mount to read bearer token for scraping targets. The secret needs to be in the same namespace as the service monitor and accessible by the Prometheus Operator. |
| query_worker.metrics.serviceMonitor.endpoints[0].honorLabels | bool | `false` | When true, honorLabels preserves the metric’s labels when they collide with the target’s labels. |
| query_worker.metrics.serviceMonitor.endpoints[0].interval | string | `"30s"` | Prometheus ServiceMonitor interval. |
| query_worker.metrics.serviceMonitor.endpoints[0].metricRelabelings | list | `[]` | Prometheus MetricRelabelConfigs to apply to samples before ingestion. |
| query_worker.metrics.serviceMonitor.endpoints[0].path | string | `"/metrics"` | Path used by the Prometheus ServiceMonitor to scrape metrics. |
| query_worker.metrics.serviceMonitor.endpoints[0].relabelings | list | `[]` | Prometheus RelabelConfigs to apply to samples before scraping. |
| query_worker.metrics.serviceMonitor.endpoints[0].scheme | string | `""` | Prometheus ServiceMonitor scheme. |
| query_worker.metrics.serviceMonitor.endpoints[0].scrapeTimeout | string | `"10s"` | Prometheus ServiceMonitor scrapeTimeout. If empty, Prometheus uses the global scrape timeout unless it is less than the target's scrape interval value in which the latter is used. |
| query_worker.metrics.serviceMonitor.endpoints[0].selector | object | `{}` | Prometheus ServiceMonitor selector. |
| query_worker.metrics.serviceMonitor.endpoints[0].tlsConfig | object | `{}` | Prometheus ServiceMonitor tlsConfig. |
| query_worker.metrics.serviceMonitor.labels | object | `{}` | Prometheus ServiceMonitor labels. |

#### NetworkPolicy

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| query_worker.networkPolicy.annotations | object | `{}` | Annotations to be added to the app NetworkPolicy. |
| query_worker.networkPolicy.create | bool | `false` | Create NetworkPolicy object for the app. The policy always selects this component's pods only (via its selector labels), never the whole namespace. |
| query_worker.networkPolicy.egress | list | `[]` | Egress rules for the NetworkPolicy object. |
| query_worker.networkPolicy.ingress | list | `[]` | Ingress rules for the NetworkPolicy object. |
| query_worker.networkPolicy.labels | object | `{}` | Labels to be added to the app NetworkPolicy. |
| query_worker.networkPolicy.policyTypes | list | `["Ingress"]` | Policy types used in the NetworkPolicy object. |

#### Pdb

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| query_worker.pdb.annotations | object | `{}` | Annotations to be added to app pdb. |
| query_worker.pdb.enabled | bool | `false` | Deploy a PodDisruptionBudget for the app |
| query_worker.pdb.labels | object | `{}` | Labels to be added to app pdb. |
| query_worker.pdb.maxUnavailable | string | `""` | Number of pods that are unavailable after eviction as number or percentage (eg.: 50%). Has higher precedence over `query_worker.pdb.minAvailable`. |
| query_worker.pdb.minAvailable | string | `""` | Number of pods that are available after eviction as number or percentage (eg.: 50%). One of `minAvailable` / `maxUnavailable` must be set when `pdb.enabled` is true - a budget of 0 is the same as having no budget at all, so leaving both empty fails at render time. |

#### Probes

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| query_worker.probes.livenessProbe.exec | object | `{"command":["sh","-c","celery -A app.celery_app inspect ping -d celery@$HOSTNAME"]}` | Query_worker container healthcheck (livenessProbe is defined using `toYaml` so it is possible to override it completely). Uses `celery inspect ping` since Celery workers don't expose an HTTP endpoint. It runs in a shell so that $HOSTNAME is the pod's real hostname (Kubernetes only expands `$(VAR)` for variables declared in the pod spec). |
| query_worker.probes.livenessProbe.failureThreshold | int | `3` | Minimum consecutive failures for the probe to be considered failed after having succeeded. |
| query_worker.probes.livenessProbe.initialDelaySeconds | int | `30` | Number of seconds after the container has started before probe is initiated. |
| query_worker.probes.livenessProbe.periodSeconds | int | `30` | How often (in seconds) to perform the probe. |
| query_worker.probes.livenessProbe.successThreshold | int | `1` | Minimum consecutive successes for the probe to be considered successful after having failed. |
| query_worker.probes.livenessProbe.timeoutSeconds | int | `10` | Number of seconds after which the probe times out. |
| query_worker.probes.readinessProbe.exec | object | `{"command":["sh","-c","celery -A app.celery_app inspect ping -d celery@$HOSTNAME"]}` | Query_worker container healthcheck (readinessProbe is defined using `toYaml` so it is possible to override it completely). Uses `celery inspect ping` since Celery workers don't expose an HTTP endpoint. It runs in a shell so that $HOSTNAME is the pod's real hostname (Kubernetes only expands `$(VAR)` for variables declared in the pod spec). |
| query_worker.probes.readinessProbe.failureThreshold | int | `2` | Minimum consecutive failures for the probe to be considered failed after having succeeded. |
| query_worker.probes.readinessProbe.initialDelaySeconds | int | `10` | Number of seconds after the container has started before probe is initiated. |
| query_worker.probes.readinessProbe.periodSeconds | int | `10` | How often (in seconds) to perform the probe. |
| query_worker.probes.readinessProbe.successThreshold | int | `2` | Minimum consecutive successes for the probe to be considered successful after having failed. |
| query_worker.probes.readinessProbe.timeoutSeconds | int | `10` | Number of seconds after which the probe times out. |
| query_worker.probes.startupProbe.exec | object | `{"command":["sh","-c","celery -A app.celery_app inspect ping -d celery@$HOSTNAME"]}` | Query_worker container healthcheck (startupProbe is defined using `toYaml` so it is possible to override it completely). Uses `celery inspect ping` since Celery workers don't expose an HTTP endpoint. It runs in a shell so that $HOSTNAME is the pod's real hostname (Kubernetes only expands `$(VAR)` for variables declared in the pod spec). |
| query_worker.probes.startupProbe.failureThreshold | int | `10` | Minimum consecutive failures for the probe to be considered failed after having succeeded. |
| query_worker.probes.startupProbe.initialDelaySeconds | int | `0` | Number of seconds after the container has started before probe is initiated. |
| query_worker.probes.startupProbe.periodSeconds | int | `10` | How often (in seconds) to perform the probe. |
| query_worker.probes.startupProbe.successThreshold | int | `1` | Minimum consecutive successes for the probe to be considered successful after having failed. |
| query_worker.probes.startupProbe.timeoutSeconds | int | `10` | Number of seconds after which the probe times out. |

#### Resources

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| query_worker.resources.limits.cpu | string | `"500m"` | CPU limit for the app. |
| query_worker.resources.limits.memory | string | `"2Gi"` | Memory limit for the app. |
| query_worker.resources.requests.cpu | string | `"100m"` | CPU request for the app. |
| query_worker.resources.requests.memory | string | `"256Mi"` | Memory request for the app. |

#### Service

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| query_worker.service.enabled | bool | `false` | Whether or not to create a Service for the app. Set to `false` for components that don't accept traffic (e.g. a queue consumer with no `containerPort`). |
| query_worker.service.extraPorts | list | `[]` | Extra service ports. |
| query_worker.service.nodePort | int | `null` (allocated by Kubernetes) | Port used when type is `NodePort` to expose the service on the given node port. Left empty, Kubernetes allocates one from the configured node-port range, which avoids two releases of this chart colliding on the same hardcoded port. |
| query_worker.service.port | int | `80` | Port used by the service. |
| query_worker.service.portName | string | `"http"` | Port name used by the service. |
| query_worker.service.protocol | string | `"TCP"` | Protocol used by the service. |
| query_worker.service.type | string | `"ClusterIP"` | Type of service to create for the app. |

#### ServiceAccount

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| query_worker.serviceAccount.annotations | object | `{}` | Annotations applied to created service account. |
| query_worker.serviceAccount.automountServiceAccountToken | bool | `false` | Should the service account access token be automount in the pod. |
| query_worker.serviceAccount.clusterRole.create | bool | `false` | Should the clusterRole be created. |
| query_worker.serviceAccount.clusterRole.rules | list | `[]` | ClusterRole rules associated with the service account. |
| query_worker.serviceAccount.create | bool | `false` | Create a service account. |
| query_worker.serviceAccount.enabled | bool | `false` | Enable the service account. |
| query_worker.serviceAccount.name | string | `""` | Service account name. |
| query_worker.serviceAccount.role.create | bool | `false` | Should the role be created. |
| query_worker.serviceAccount.role.rules | list | `[]` | Role rules associated with the service account. |

#### Strategy

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| query_worker.strategy.rollingUpdate.maxSurge | int | `1` | The maximum number of pods that can be scheduled above the desired number of pods. |
| query_worker.strategy.rollingUpdate.maxUnavailable | int | `1` | The maximum number of pods that can be unavailable during the update process. |
| query_worker.strategy.type | string | `"RollingUpdate"` | Strategy type used to replace old Pods by new ones, can be `Recreate` or `RollingUpdate`. Only applied when `deploymentType` is "Deployment". |

### Redis

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| redis.enabled | bool | `false` |  |

## Sources

**Source code:**

* <https://github.com/mitchou10/spreadsheet-analyser>
* <https://github.com/this-is-tobi/helm-charts>

----------------------------------------------
Autogenerated from chart metadata using [helm-docs v1.14.2](https://github.com/norwoodj/helm-docs/releases/v1.14.2)
