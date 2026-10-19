from pathlib import Path

from fastapi import APIRouter, Response

from app.mcp.server import MCP_RESOURCE_URL

router = APIRouter(prefix="/help", tags=["Help"])

# The guide for the people who connect an agent: one markdown file, shown in the application and served here.
MCP_GUIDE = Path(__file__).resolve().parent.parent / "mcp" / "guide.md"


@router.get(
    "/mcp",
    summary="How to connect an agent to the MCP server (markdown)",
    response_class=Response,
    responses={200: {"content": {"text/markdown": {}}}},
)
async def mcp_guide() -> Response:
    """The guide of `app/mcp/guide.md` with the real address of the server. Public: it says nothing secret, and an
    agent (or the person setting it up) can read it before signing in."""
    text = MCP_GUIDE.read_text(encoding="utf-8").replace("{{MCP_URL}}", MCP_RESOURCE_URL)
    return Response(content=text, media_type="text/markdown; charset=utf-8")
