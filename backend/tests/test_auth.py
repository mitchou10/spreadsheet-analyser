from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_me_full_access_mode() -> None:
    """VERIFY_TOKEN_MODEL=full-access (tests/.env.testing) always authenticates as dev-user,
    with no Keycloak/session cookie needed."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == "dev-user"
    assert body["is_admin"] is True
