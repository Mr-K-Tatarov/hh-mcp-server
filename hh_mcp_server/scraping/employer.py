import logging

from playwright.async_api import Page

from hh_mcp_server.constants import BASE_URL
from hh_mcp_server.scraping.extractor import navigate_and_wait

logger = logging.getLogger(__name__)


async def parse_employer_page(page: Page, employer_id: str) -> dict:
    url = f"{BASE_URL}/employer/{employer_id}"
    await navigate_and_wait(page, url)

    await page.wait_for_timeout(2000)
    text = await page.inner_text("body")

    return {
        "id": employer_id,
        "url": url,
        "raw_text": text,
    }
