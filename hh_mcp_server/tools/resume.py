from typing import Any

from fastmcp import FastMCP

from hh_mcp_server.constants import TOOL_TIMEOUT_SECONDS
from hh_mcp_server.drivers.browser import get_page
from hh_mcp_server.scraping.resume import get_my_resumes as _get_resumes, parse_resume_page
from hh_mcp_server.utils.auth import ensure_authenticated


def register_resume_tools(mcp: FastMCP) -> None:

    @mcp.tool(timeout=TOOL_TIMEOUT_SECONDS, title="Get My Resumes")
    async def get_my_resumes() -> list[dict[str, Any]]:
        """Get list of user's resumes on hh.ru."""
        page = await get_page()
        await ensure_authenticated(page)
        return await _get_resumes(page)

    @mcp.tool(timeout=TOOL_TIMEOUT_SECONDS, title="Get Resume")
    async def get_resume(resume_id: str) -> dict[str, Any]:
        """Get full resume content.

        Args:
            resume_id: Resume ID (from get_my_resumes)
        """
        page = await get_page()
        await ensure_authenticated(page)
        return await parse_resume_page(page, resume_id)
