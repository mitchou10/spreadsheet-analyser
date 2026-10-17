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
    """Authenticated HTTP client for the backend's internal API (`/api/internal/*`), analysis endpoints.

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

    # --- SQL queries (agent -> backend -> this worker) ---

    def query_context(self, query_id: str) -> dict:
        """{query_id, sql, tables: [{ref, file_id, file_name, result_key}]}: the files the query may read."""
        return self._request("GET", f"/queries/{query_id}/context")

    def query_start(self, query_id: str) -> dict:
        return self._request("POST", f"/queries/{query_id}/start")

    def query_complete(self, query_id: str, result: dict) -> dict:
        return self._request("POST", f"/queries/{query_id}/complete", result)

    def query_fail(self, query_id: str, error: str, tables: list[dict] | None = None) -> dict:
        """`tables` lists what could be queried (as the SQL must name it), so that the author can correct itself."""
        return self._request("POST", f"/queries/{query_id}/fail", {"error": error, "tables": tables or []})

    # --- Charts (agent -> backend -> this worker) ---

    def chart_context(self, chart_id: str) -> dict:
        """{chart_id, spec, sql, tables, s3_key}: what to draw, from which query, and where to write the PNG."""
        return self._request("GET", f"/charts/{chart_id}/context")

    def chart_start(self, chart_id: str) -> dict:
        return self._request("POST", f"/charts/{chart_id}/start")

    def chart_complete(self, chart_id: str, s3_key: str, width: int, height: int) -> dict:
        return self._request(
            "POST", f"/charts/{chart_id}/complete", {"s3_key": s3_key, "width": width, "height": height}
        )

    def chart_fail(self, chart_id: str, error: str, columns: list[dict] | None = None) -> dict:
        """`columns` is what the query returns ([{name, type}]), so that the author can correct its request."""
        return self._request("POST", f"/charts/{chart_id}/fail", {"error": error, "columns": columns or []})
