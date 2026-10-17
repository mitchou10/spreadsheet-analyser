# spreadsheet-analyser

Monorepo with `frontend` (Vite + React), `backend` (FastAPI), and `worker` (Celery), bootstrapped with the same CI/CD setup as [Muffin](https://github.com/mitchou10) (GitHub Actions, release-please, Docker/GHCR, Helm, Trivy/Gitleaks scans).

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
