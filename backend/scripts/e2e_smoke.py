"""End-to-end smoke test of the running docker compose stack, as the browser would drive it.

Logs in through the real BFF + Keycloak flow (PKCE, session cookie), then exercises collections, upload,
sharing, conversations and messages over HTTP with the CORS origin of the dockerized frontend.

Usage (stack up via `make up`): uv run python scripts/e2e_smoke.py
"""

import os
import re
import sys
from html import unescape

import httpx

BACKEND = os.environ.get("BACKEND_URL", "http://localhost:8000")
# Origin the backend is configured for (FRONTEND_URL of the stack: 8081 dockerized, 5173 with `pnpm dev`).
FRONTEND = os.environ.get("FRONTEND_URL", "http://localhost:8081")
# Where the dockerized frontend is actually served, for the SPA deep-link check.
FRONTEND_SERVE = os.environ.get("FRONTEND_SERVE_URL", "http://localhost:8081")
USERNAME = os.environ.get("E2E_USERNAME", "dev")
PASSWORD = os.environ.get("E2E_PASSWORD", "dev-password")

failures: list[str] = []


class InsecureCookieTransport(httpx.HTTPTransport):
    """Keycloak marks its cookies Secure even over plain http://localhost; browsers still send them to
    localhost, httpx's cookie jar does not - so drop the flag, like a browser effectively does."""

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = super().handle_request(request)
        headers = [
            (name, re.sub(rb";\s*Secure", b"", value, flags=re.IGNORECASE) if name.lower() == b"set-cookie" else value)
            for name, value in response.headers.raw
        ]
        response.headers = httpx.Headers(headers)
        return response


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {label}" + ("" if condition else f"  -> {detail}"))
    if not condition:
        failures.append(label)


def login(client: httpx.Client) -> None:
    response = client.get(f"{BACKEND}/api/auth/login", params={"redirect": "/collections"}, follow_redirects=True)
    form = re.search(r'<form[^>]*id="kc-form-login"[^>]*action="([^"]+)"', response.text)
    assert form, f"Keycloak login form not found (status {response.status_code})"
    response = client.post(
        unescape(form.group(1)),
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    # Keycloak -> backend /api/auth/callback (sets the session cookie) -> frontend.
    while response.is_redirect:
        target = str(response.next_request.url) if response.next_request else ""
        check_target = target.startswith(FRONTEND)
        if check_target:
            check(
                "login redirects back to the frontend at the requested path",
                target == f"{FRONTEND}/collections",
                target,
            )
            return
        response = client.send(response.next_request, follow_redirects=False)
    check("login redirects back to the frontend", False, response.status_code)


def main() -> int:
    with httpx.Client(timeout=30, headers={"Origin": FRONTEND}, transport=InsecureCookieTransport()) as client:
        api = f"{BACKEND}/api"

        check("unauthenticated /collections is 401", client.get(f"{api}/collections").status_code == 401)
        login(client)

        me = client.get(f"{api}/auth/me")
        check("session cookie authenticates /auth/me", me.status_code == 200 and me.json()["email"], me.text)
        check(
            "CORS allows the frontend origin with credentials",
            me.headers.get("access-control-allow-origin") == FRONTEND
            and me.headers.get("access-control-allow-credentials") == "true",
            dict(me.headers),
        )
        preflight = client.options(
            f"{api}/collections",
            headers={
                "Origin": FRONTEND,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        check("CORS preflight for POST /collections", preflight.status_code == 200, preflight.status_code)

        health = client.get(f"{api}/health")
        check("health", health.status_code == 200, health.text)

        # --- Collections + upload ---
        collection = client.post(f"{api}/collections", json={"name": "E2E", "description": "smoke"}).json()
        cid = collection["id"]
        check("create collection", collection["is_owner"] and collection["file_count"] == 0, collection)

        uploaded = client.post(
            f"{api}/collections/{cid}/files",
            files=[
                ("files", ("ventes.csv", b"a,b\n1,2\n", "text/csv")),
                ("files", ("b.xlsx", b"PK-fake", "application/octet-stream")),
            ],
        )
        check("upload 2 files (real RustFS)", uploaded.status_code == 201 and len(uploaded.json()) == 2, uploaded.text)
        files = client.get(f"{api}/collections/{cid}/files").json()
        check("files listed as pending", {f["status"] for f in files} == {"pending"}, files)
        file_id = next(f["id"] for f in files if f["name"] == "ventes.csv")
        download = client.get(f"{api}/files/{file_id}/download")
        check("download returns the uploaded bytes", download.content == b"a,b\n1,2\n", download.content)
        check("collection file_count updated", client.get(f"{api}/collections/{cid}").json()["file_count"] == 2)
        check(
            "unsupported extension rejected",
            client.post(f"{api}/collections/{cid}/files", files=[("files", ("x.exe", b"x"))]).status_code == 415,
        )

        # --- Analysis control ---
        check("stop analysis", client.post(f"{api}/files/{file_id}/analysis/stop").json()["status"] == "stopped")
        check("retry analysis", client.post(f"{api}/files/{file_id}/analysis").json()["status"] == "pending")

        # --- Sharing ---
        share = client.post(f"{api}/collections/{cid}/access", json={"email": "Someone@Example.com"})
        check("share by email", share.status_code == 201 and share.json()["email"] == "someone@example.com", share.text)
        check("revoke access", client.delete(f"{api}/collections/{cid}/access/someone@example.com").status_code == 204)

        # --- Conversations ---
        conversation = client.post(f"{api}/conversations", json={}).json()
        message = client.post(
            f"{api}/conversations/{conversation['id']}/messages",
            json={"content": "Résume ventes.csv", "collection_ids": [cid], "file_ids": [file_id]},
        )
        check("send message scoped to collection + file", message.status_code == 201, message.text)
        messages = client.get(f"{api}/conversations/{conversation['id']}/messages").json()
        check("message persisted with its scope", messages[0]["file_ids"] == [file_id], messages)
        titles = [c["title"] for c in client.get(f"{api}/conversations").json()]
        check("conversation titled from first message", "Résume ventes.csv" in titles, titles)
        check("delete conversation", client.delete(f"{api}/conversations/{conversation['id']}").status_code == 204)

        # --- Cleanup ---
        check("delete file", client.delete(f"{api}/files/{file_id}").status_code == 204)
        check("delete collection", client.delete(f"{api}/collections/{cid}").status_code == 204)
        check("collection gone", client.get(f"{api}/collections/{cid}").status_code == 404)

        # --- Logout ---
        out = client.post(f"{api}/auth/logout")
        check("logout", out.status_code == 200 and "redirectUrl" in out.json(), out.text)
        check("session is gone after logout", client.get(f"{api}/collections").status_code == 401)

        frontend = client.get(f"{FRONTEND_SERVE}/collections")
        check(
            "frontend serves the SPA on deep links",
            frontend.status_code == 200 and '<div id="root">' in frontend.text,
            frontend.status_code,
        )

    print(f"\n{len(failures)} failure(s)" if failures else "\nAll good")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
