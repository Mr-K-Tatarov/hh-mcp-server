import logging

from playwright.async_api import Page

from hh_mcp_server.constants import BASE_URL
from hh_mcp_server.scraping import selectors as S
from hh_mcp_server.scraping.extractor import extract_resume_id, navigate_and_wait

logger = logging.getLogger(__name__)


async def get_my_resumes(page: Page) -> list[dict]:
    url = f"{BASE_URL}/applicant/resumes"
    await navigate_and_wait(page, url, S.RESUME_CARD)

    cards = await page.query_selector_all(S.RESUME_CARD)
    resumes = []

    for card in cards:
        title_el = await card.query_selector(S.RESUME_TITLE_LINK)
        if not title_el:
            continue

        title = (await title_el.inner_text()).strip()
        href = await title_el.get_attribute("href") or ""
        resume_id = extract_resume_id(href)

        resumes.append({
            "id": resume_id,
            "title": title,
            "url": f"{BASE_URL}/resume/{resume_id}" if resume_id else href,
        })

    return resumes


async def parse_resume_page(page: Page, resume_id: str) -> dict:
    url = f"{BASE_URL}/resume/{resume_id}"
    await navigate_and_wait(page, url)

    await page.wait_for_timeout(2000)
    text = await page.inner_text("body")

    return {
        "id": resume_id,
        "url": url,
        "raw_text": text,
    }
