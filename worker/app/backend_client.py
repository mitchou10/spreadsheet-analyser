import os

import httpx


class BackendError(Exception):
    """The backend answered with an error (or could not be reached)."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class BackendUnauthorized(BackendError):
    """The internal token was rejected: a configuration problem, retrying will not help."""


class RunConflict(BackendError):
    """The backend refused the transition (e.g. the user cancelled the run): stop quietly."""


class BackendClient:
    """Authenticated HTTP client for the backend's internal API (`/api/internal/*`).

    The workers never touch the database: they read and update everything through this client, which
    sends the shared `INTERNAL_API_TOKEN` as `Authorization: Bearer <token>`. Any worker (agent,
    spreadsheet analysis...) can reuse it."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout: float = 30,
        retries: int = 2,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not token:
            raise ValueError("INTERNAL_API_TOKEN is not set: the worker cannot authenticate to the backend")
        self._client = httpx.Client(
            base_url=f"{base_url.rstrip('/')}/api/internal",
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
            # `retries` only re-attempts failed connections (backend restarting), never an applied request.
            transport=transport or httpx.HTTPTransport(retries=retries),
        )

    @classmethod
    def from_env(cls) -> "BackendClient":
        return cls(os.environ.get("BACKEND_URL", "http://localhost:8000"), os.environ.get("INTERNAL_API_TOKEN", ""))

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BackendClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _request(self, method: str, path: str, json: dict | None = None):
        try:
            response = self._client.request(method, path, json=json)
        except httpx.TransportError as error:
            raise BackendError(f"Backend unreachable: {error}") from error
        if response.is_success:
            return response.json()
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        if response.status_code in (401, 403, 503):
            raise BackendUnauthorized(f"Backend refused the internal token: {detail}", response.status_code)
        if response.status_code == 409:
            raise RunConflict(str(detail), response.status_code)
        raise BackendError(f"{method} {path} -> {response.status_code}: {detail}", response.status_code)

    # --- Runs ---

    def start(self, run_id: str) -> dict:
        return self._request("POST", f"/runs/{run_id}/start")

    def context(self, run_id: str) -> dict:
        return self._request("GET", f"/runs/{run_id}/context")

    def complete(self, run_id: str, content: str) -> dict:
        return self._request("POST", f"/runs/{run_id}/complete", {"content": content})

    def fail(self, run_id: str, error: str) -> dict:
        return self._request("POST", f"/runs/{run_id}/fail", {"error": error})

    def run_files(self, run_id: str) -> list[dict]:
        """Files the run's agent may look at, each with its latest analysis state and the S3 key of
        analyse.json once ready: [{file_id, file_name, collection_name, version, analysis_status, result_key...}]"""
        return self._request("GET", f"/runs/{run_id}/files")

    # --- Conversations ---

    def messages(self, conversation_id: str) -> list[dict]:
        """Full history, oldest first: [{id, role, content, collection_ids, file_ids, created_at}]."""
        return self._request("GET", f"/conversations/{conversation_id}/messages")

    # --- Spreadsheet analyses ---

    def analysis_context(self, analysis_id: str) -> dict:
        """{analysis_id, file_id, file_name, file_version, content_type, size_bytes, source_key, result_key}"""
        return self._request("GET", f"/analyses/{analysis_id}/context")

    def analysis_start(self, analysis_id: str) -> dict:
        return self._request("POST", f"/analyses/{analysis_id}/start")

    def analysis_complete(self, analysis_id: str, s3_key: str) -> dict:
        return self._request("POST", f"/analyses/{analysis_id}/complete", {"s3_key": s3_key})

    def analysis_fail(self, analysis_id: str, error: str) -> dict:
        return self._request("POST", f"/analyses/{analysis_id}/fail", {"error": error})
