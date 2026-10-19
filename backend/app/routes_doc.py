"""docs/api.md, the list of the routes, generated from the OpenAPI document so that it cannot drift from the code.

    uv run python -m app.routes_doc ../docs/api.md

A test fails when the file is out of date: run the command above and commit the result."""

import sys
from pathlib import Path

from app.main import app

PUBLIC = {
    ("GET", "/api/health"),
    ("GET", "/api/help/mcp"),
    ("GET", "/api/auth/login"),
    ("GET", "/api/auth/callback"),
    ("POST", "/api/auth/token"),
    ("POST", "/api/auth/refresh"),
}
METHODS = ("get", "post", "put", "patch", "delete")

HEADER = """# Routes de l'API

Liste des routes du backend, générée depuis le document OpenAPI (`/api/openapi.json`, aussi lisible dans Swagger à
`/api/docs`). **Ne pas modifier à la main** : `cd backend && uv run python -m app.routes_doc ../docs/api.md`, un test
vérifie que ce fichier est à jour.

Accès : *public* (sans connexion), *connecté* (session Keycloak du navigateur, ou `Authorization: Bearer <jeton
Keycloak>`), *administrateur* (rôle `admin`), *jeton interne* (les workers, `INTERNAL_API_TOKEN`).
"""

FOOTER = """
## Hors OpenAPI

| Route | Description | Accès |
|---|---|---|
| `/mcp` | serveur MCP (Streamable HTTP), voir [mcp.md](mcp.md) | connecté (jeton Keycloak) |
| `GET /.well-known/oauth-protected-resource/mcp` | où se connecter pour utiliser le serveur MCP (RFC 9728) | public |

Guides : [analyse éphémère](ephemeral-analysis.md), [serveur MCP](mcp.md), [graphiques](charts.md),
[requêtes SQL](sql-queries.md), [index de recherche](search-index.md), [`analyse.json`](analyse-json.md).
"""


def _access(method: str, path: str, tags: list[str]) -> str:
    if path.startswith("/api/internal"):
        return "jeton interne"
    if "Admin" in tags:
        return "administrateur"
    return "public" if (method, path) in PUBLIC else "connecté"


def render() -> str:
    schema = app.openapi()
    order = [tag["name"] for tag in schema.get("tags", [])]
    descriptions = {tag["name"]: tag.get("description", "") for tag in schema.get("tags", [])}
    groups: dict[str, list[tuple[str, str, str, str]]] = {}
    for path, operations in schema["paths"].items():
        for method in METHODS:
            operation = operations.get(method)
            if operation is None:
                continue
            tag = (operation.get("tags") or ["Autres"])[0]
            summary = " ".join((operation.get("summary") or "").split()).replace("|", "\\|")
            groups.setdefault(tag, []).append((method.upper(), path, summary, _access(method.upper(), path, [tag])))

    lines = [HEADER]
    for tag in [t for t in order if t in groups] + sorted(t for t in groups if t not in order):
        lines.append(f"\n## {tag}\n")
        if descriptions.get(tag):
            lines.append(f"{descriptions[tag]}\n")
        lines.append("| Méthode | Route | Description | Accès |\n|---|---|---|---|")
        lines += [f"| {m} | `{p}` | {s} | {a} |" for m, p, s, a in groups[tag]]
    lines.append(FOOTER)
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if target is None:
        sys.stdout.write(render())
    else:
        target.write_text(render(), encoding="utf-8")
