"""Who calls the MCP server: the Keycloak access token of the person (or of a service account) in
`Authorization: Bearer <token>`, checked the same way as for the REST API (userinfo), so the analyses belong to the
same identities everywhere."""

import os

import anyio
from mcp.server.auth.provider import AccessToken

from app.config import KeycloakSettings
from app.core.security.claims import extract_identity
from app.core.security.keycloak_client import keycloak_openid
from app.services.actor import Actor


class KeycloakTokenVerifier:
    """`TokenVerifier` of the MCP SDK: an unknown or expired token gets a 401 with the pointer to Keycloak."""

    def __init__(self) -> None:
        self._settings = KeycloakSettings()

    async def verify_token(self, token: str) -> AccessToken | None:
        if os.environ.get("VERIFY_TOKEN_MODEL") == "full-access":
            # Dev/test mode of the REST API (no Keycloak): every token is the dev user.
            claims = {"sub": "dev-user", "email": "dev@example.com", "resource_access": {}}
        else:
            try:
                # Blocking HTTP call to Keycloak: off the event loop. userinfo, not introspect: the caller is a
                # resource server and is not in the token's audience.
                claims = await anyio.to_thread.run_sync(keycloak_openid.userinfo, token)
            except Exception:
                return None
        if not claims.get("sub"):
            return None
        return AccessToken(
            token=token,
            client_id=self._settings.KEYCLOAK_CLIENT_ID,
            scopes=[],
            subject=claims["sub"],
            claims=claims,
        )


def actor_of(access_token: AccessToken | None) -> Actor:
    """The caller of a tool, from the claims of the verified token."""
    claims = (access_token.claims if access_token else None) or {}
    identity = extract_identity(claims, KeycloakSettings().KEYCLOAK_CLIENT_ID)
    if identity is None:
        raise PermissionError("Not authenticated")
    return Actor(user_id=identity["user_id"], email=identity["email"])
