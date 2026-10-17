import os

import httpx


class RunConflict(Exception):
    """The backend refused the transition (e.g. the user cancelled the run): stop quietly."""


class BackendClient:
    """The worker never touches the database: it reads and updates runs through the backend's internal API."""

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._client = httpx.Client(
            base_url=os.environ.get("BACKEND_URL", "http://localhost:8000") + "/api/internal/runs",
            headers={"X-Internal-Token": os.environ.get("INTERNAL_API_TOKEN", "")},
            timeout=30,
            transport=transport,
        )

    def _post(self, path: str, json: dict | None = None) -> dict:
        response = self._client.post(path, json=json)
        if response.status_code == 409:
            raise RunConflict(response.json().get("detail", "conflict"))
        response.raise_for_status()
        return response.json()

    def start(self, run_id: str) -> dict:
        return self._post(f"/{run_id}/start")

    def context(self, run_id: str) -> dict:
        response = self._client.get(f"/{run_id}/context")
        response.raise_for_status()
        return response.json()

    def complete(self, run_id: str, content: str) -> dict:
        return self._post(f"/{run_id}/complete", {"content": content})

    def fail(self, run_id: str, error: str) -> dict:
        return self._post(f"/{run_id}/fail", {"error": error})
