from typing import Any

from fastmcp import FastMCP

from hh_mcp_server.constants import TOOL_TIMEOUT_SECONDS
from hh_mcp_server.drivers.browser import get_page
from hh_mcp_server.scraping.employer import parse_employer_page
from hh_mcp_server.utils.auth import ensure_authenticated


def register_employer_tools(mcp: FastMCP) -> None:

    @mcp.tool(timeout=TOOL_TIMEOUT_SECONDS, title="Get Employer Info")
    async def get_employer_info(employer_id: str) -> dict[str, Any]:
        """Get company/employer information.

        Args:
            employer_id: hh.ru employer ID
        """
        page = await get_page()
        await ensure_authenticated(page)
        return await parse_employer_page(page, employer_id)
