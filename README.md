# spreadsheet-analyser

Monorepo with `frontend` (Vite + React), `backend` (FastAPI), and two Celery workers (`agent-worker`, `analysis-worker`), bootstrapped with the same CI/CD setup as [Muffin](https://github.com/mitchou10) (GitHub Actions, release-please, Docker/GHCR, Helm, Trivy/Gitleaks scans).

## Authentication (BFF + Keycloak)

The backend acts as a Backend-For-Frontend: the browser never sees an access/refresh token.

- `GET /api/auth/login` redirects to Keycloak (Authorization Code + PKCE)
- `GET /api/auth/callback` exchanges the code, stores the session server-side in Redis, and sets an httponly session cookie
- `GET /api/auth/me` returns the current identity (used by the frontend's `AuthProvider`)
- `POST /api/auth/logout` clears the session and returns Keycloak's end-session URL
- `POST /api/auth/token` / `POST /api/auth/refresh` are password/refresh grants for non-browser clients

Dev realm/client/user are imported from `docker/keycloak/realm-spreadsheet-analyser.json` when running `make up` (Keycloak admin console on http://localhost:8080, user `dev` / `dev-password`).

Tests run with `VERIFY_TOKEN_MODEL=full-access` (see `backend/tests/.env.testing`), which bypasses Keycloak entirely with a fixed dev identity.

## Development

```sh
make install   # install all service dependencies
make lint       # lint every service
make test       # run every service's test suite
make up         # start the local stack (docker compose)
```

## CI/CD

- `.github/workflows/ci.yml` — lint, unit tests, Docker builds, Trivy/Gitleaks scans, Helm lint (pull requests)
- `.github/workflows/cd.yml` — release-please, Docker publish to GHCR, Helm chart release (`dev`/`main`)
- `.github/workflows/lint.yml`, `unit-tests.yml` — reusable workflows called by `ci.yml`
- `.github/workflows/clean-cache.yml` — daily cache/image cleanup
