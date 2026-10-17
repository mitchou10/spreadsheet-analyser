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
    """Authenticated HTTP client for the backend's internal API (`/api/internal/*`), index endpoints.

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

    def _request(self, method: str, path: str, json: dict | None = None, params: dict | None = None):
        try:
            response = self._client.request(method, path, json=json, params=params)
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

    # --- What the indexes are built from ---

    def analysis_context(self, analysis_id: str) -> dict:
        """{analysis_id, file_id, file_name, collection_id, collection_name, file_version, result_key...}"""
        return self._request("GET", f"/analyses/{analysis_id}/context")

    def collection_analyses(self, collection_id: str) -> list[dict]:
        """Files of a collection whose latest analysis is ready: [{file_id, file_name, collection_name, version,
        result_key}]. The input of a full rebuild of the collection's index."""
        return self._request("GET", f"/collections/{collection_id}/analyses")

    def collection_audience(self, collection_id: str) -> dict:
        """Who can read a collection: {collection_id, owner_email, emails} (emails: the people it is shared with)."""
        return self._request("GET", f"/collections/{collection_id}/audience")

    def user_collections(self, email: str) -> list[str]:
        """Ids of the collections a person can read (owned or shared with their email)."""
        return self._request("GET", "/users/collections", params={"email": email})["collection_ids"]
