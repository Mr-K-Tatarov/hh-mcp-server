from typing import Any

from fastmcp import FastMCP

from hh_mcp_server.constants import TOOL_TIMEOUT_SECONDS
from hh_mcp_server.drivers.browser import get_page
from hh_mcp_server.scraping.vacancy_search import search_vacancies as _search
from hh_mcp_server.scraping.vacancy_search import get_recommended_vacancies as _recommended
from hh_mcp_server.scraping.vacancy_detail import parse_vacancy_page
from hh_mcp_server.utils.auth import ensure_authenticated


def register_vacancy_tools(mcp: FastMCP) -> None:

    @mcp.tool(timeout=TOOL_TIMEOUT_SECONDS, title="Search Vacancies")
    async def search_vacancies(
        keywords: str,
        area: str | None = None,
        salary_from: int | None = None,
        salary_to: int | None = None,
        experience: str | None = None,
        schedule: str | None = None,
        max_pages: int = 3,
    ) -> dict[str, Any]:
        """Search for vacancies on hh.ru.

        Args:
            keywords: Search keywords (e.g., "QA Automation Engineer")
            area: Location filter (e.g., "москва", "россия")
            salary_from: Minimum salary
            salary_to: Maximum salary
            experience: Experience level (no_experience, 1-3, 3-6, 6+)
            schedule: Work schedule (remote, office, hybrid, flexible, shift)
            max_pages: Maximum pages to load (1-10, default 3)
        """
        page = await get_page()
        await ensure_authenticated(page)
        return await _search(
            page,
            text=keywords,
            area=area,
            salary_from=salary_from,
            salary_to=salary_to,
            experience=experience,
            schedule=schedule,
            max_pages=min(max_pages, 10),
        )

    @mcp.tool(timeout=TOOL_TIMEOUT_SECONDS, title="Get Recommended Vacancies")
    async def get_recommended_vacancies(
        resume_id: str,
        max_pages: int = 5,
    ) -> dict[str, Any]:
        """Get vacancies recommended by hh.ru for a specific resume.

        Uses hh.ru's matching algorithm to find vacancies that best fit
        the resume. This is equivalent to the "Подходящие вакансии" page.

        Args:
            resume_id: Resume ID from get_my_resumes (e.g., "0fe69243ff063cb4720039ed1f574b71676a55")
            max_pages: Maximum pages to load (1-50, default 5, 20 vacancies per page)
        """
        page = await get_page()
        await ensure_authenticated(page)
        return await _recommended(
            page,
            resume_id=resume_id,
            max_pages=min(max_pages, 50),
        )

    @mcp.tool(timeout=TOOL_TIMEOUT_SECONDS, title="Get Vacancy Details")
    async def get_vacancy_details(vacancy_id: str) -> dict[str, Any]:
        """Get full details of a specific vacancy.

        Args:
            vacancy_id: hh.ru vacancy ID (e.g., "12345678")
        """
        page = await get_page()
        await ensure_authenticated(page)
        return await parse_vacancy_page(page, vacancy_id)
