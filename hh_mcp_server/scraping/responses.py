import logging

from playwright.async_api import Page

from hh_mcp_server.constants import BASE_URL
from hh_mcp_server.scraping.extractor import navigate_and_wait

logger = logging.getLogger(__name__)


async def get_my_responses(page: Page) -> dict:
    url = f"{BASE_URL}/applicant/negotiations"
    await navigate_and_wait(page, url)

    await page.wait_for_timeout(2000)
    text = await page.inner_text("body")

    return {
        "url": url,
        "raw_text": text,
    }
