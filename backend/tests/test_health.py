from httpx import ASGITransport, AsyncClient

from app.connectors import StorageConnector
from app.main import app


async def test_health() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


class _BrokenStorage:
    bucket = "bucket"
    endpoint = "https://s3.example.org"

    async def check_bucket(self) -> None:
        raise ConnectionError("no route to host")


async def test_storage_connector_reports_why_s3_is_unhealthy() -> None:
    health = await StorageConnector(_BrokenStorage()).get_health()  # type: ignore[arg-type]
    assert health["status"] == "unhealthy"
    assert health["critical"] is False
    assert health["extras"] == {
        "bucket": "bucket",
        "endpoint": "https://s3.example.org",
        "error": "ConnectionError: no route to host",
    }


async def test_version_is_the_one_of_the_package() -> None:
    from importlib.metadata import version

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/version")

    assert response.status_code == 200
    assert response.json() == {"version": version("backend")}


async def test_the_mcp_guide_is_served_as_markdown_with_the_real_address() -> None:
    from app.mcp.server import MCP_RESOURCE_URL

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/help/mcp")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert MCP_RESOURCE_URL in response.text and "{{MCP_URL}}" not in response.text
    assert "analyze_files" in response.text and "ask_known_files" in response.text
