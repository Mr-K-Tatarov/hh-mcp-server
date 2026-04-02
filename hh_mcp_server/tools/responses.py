from typing import Any

from fastmcp import FastMCP

from hh_mcp_server.constants import TOOL_TIMEOUT_SECONDS
from hh_mcp_server.drivers.browser import get_page
from hh_mcp_server.scraping.responses import get_my_responses
from hh_mcp_server.utils.auth import ensure_authenticated


def register_response_tools(mcp: FastMCP) -> None:

    @mcp.tool(timeout=TOOL_TIMEOUT_SECONDS, title="Get My Responses")
    async def get_responses() -> dict[str, Any]:
        """Get list of user's job applications/responses on hh.ru."""
        page = await get_page()
        await ensure_authenticated(page)
        return await get_my_responses(page)
