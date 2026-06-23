import logging
import re

from playwright.async_api import Page

from hh_mcp_server.exceptions import AuthenticationError, ScrapingError
from hh_mcp_server.scraping.vpn import handle_vpn_warning, is_vpn_blocked, raise_access_blocked_error

logger = logging.getLogger(__name__)


async def navigate_and_wait(page: Page, url: str, wait_selector: str | None = None, timeout: int = 15000) -> None:
    await page.goto(url, wait_until="domcontentloaded", timeout=timeout)

    if "/account/login" in page.url:
        raise AuthenticationError()

    if await is_vpn_blocked(page):
        if not await handle_vpn_warning(page):
            raise_access_blocked_error()

    if "captcha" in page.url.lower():
        raise ScrapingError("Captcha detected. Please solve it manually and retry.")

    if wait_selector:
        try:
            await page.wait_for_selector(wait_selector, timeout=timeout)
        except Exception:
            logger.warning("Selector %s not found on %s", wait_selector, url)


async def extract_text(page: Page, selector: str) -> str | None:
    el = await page.query_selector(selector)
    if el:
        text = await el.inner_text()
        return text.strip() if text else None
    return None


async def extract_all_texts(page: Page, selector: str) -> list[str]:
    elements = await page.query_selector_all(selector)
    results = []
    for el in elements:
        text = await el.inner_text()
        if text and text.strip():
            results.append(text.strip())
    return results


async def extract_href(page: Page, selector: str) -> str | None:
    el = await page.query_selector(selector)
    if el:
        return await el.get_attribute("href")
    return None


async def extract_inner_html(page: Page, selector: str) -> str | None:
    el = await page.query_selector(selector)
    if el:
        html = await el.inner_html()
        return html_to_text(html) if html else None
    return None


def html_to_text(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html)
    text = re.sub(r"<li>", "\n- ", text)
    text = re.sub(r"</?(ul|ol|p|div|h[1-6])[^>]*>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_vacancy_id(url: str) -> str | None:
    match = re.search(r"/vacancy/(\d+)", url)
    return match.group(1) if match else None


def extract_employer_id(url: str) -> str | None:
    match = re.search(r"/employer/(\d+)", url)
    return match.group(1) if match else None


def extract_resume_id(url: str) -> str | None:
    match = re.search(r"/resume/([a-f0-9]+)", url)
    return match.group(1) if match else None
