from typing import Any

from fastmcp import FastMCP

from hh_mcp_server.constants import TOOL_TIMEOUT_SECONDS
from hh_mcp_server.drivers.browser import get_page
from hh_mcp_server.scraping.apply import apply_to_vacancy as _apply
from hh_mcp_server.utils.auth import ensure_authenticated


def register_apply_tools(mcp: FastMCP) -> None:

    @mcp.tool(timeout=TOOL_TIMEOUT_SECONDS, title="Apply to Vacancy")
    async def apply_to_vacancy(
        vacancy_id: str,
        resume_id: str | None = None,
        cover_letter: str | None = None,
        question_answers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Apply to a vacancy on hh.ru.

        Two-pass flow for vacancies with questions:
        1. First call without question_answers -> returns questions list
        2. Second call with question_answers filled -> submits application

        Args:
            vacancy_id: hh.ru vacancy ID
            resume_id: Resume ID to use (from get_my_resumes)
            cover_letter: Cover letter text
            question_answers: Dict mapping question label to answer text
        """
        page = await get_page()
        await ensure_authenticated(page)
        return await _apply(
            page,
            vacancy_id=vacancy_id,
            resume_id=resume_id,
            cover_letter=cover_letter,
            question_answers=question_answers,
        )
