# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project
COPY app ./app
RUN uv sync --no-dev

FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 1000 worker
WORKDIR /app
COPY --from=builder --chown=worker:worker /app/.venv /app/.venv
COPY --from=builder --chown=worker:worker /app/app /app/app
USER worker
ENV PATH="/app/.venv/bin:$PATH"
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD celery -A app.celery_app inspect ping -d celery@$$HOSTNAME || exit 1
# Two processes at most, and a child that grows past ~600 MB is recycled after its task: a pathological
# spreadsheet can only ever cost this container (and the orchestrator's memory limit backs that up).
CMD ["celery", "-A", "app.celery_app", "worker", "--loglevel=info", "-Q", "analysis", "--concurrency=2", "--max-memory-per-child=600000"]
