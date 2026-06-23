import asyncio
import logging

from hh_mcp_server.constants import BASE_URL
from hh_mcp_server.drivers.browser import (
    close_browser,
    get_page,
    save_state,
    set_headless,
)
from hh_mcp_server.exceptions import AuthenticationError

logger = logging.getLogger(__name__)

LOGIN_URL = f"{BASE_URL}/account/login"


async def run_login_flow() -> None:
    set_headless(False)
    page = await get_page()

    logger.info("Navigating to %s", LOGIN_URL)
    await page.goto(LOGIN_URL, wait_until="domcontentloaded")

    print("Please log in to hh.ru in the browser window...")
    print("Waiting for authentication...")

    while True:
        url = page.url
        if "/account/login" not in url and "hh.ru" in url:
            break
        await asyncio.sleep(1)

    await page.wait_for_timeout(2000)
    await save_state()
    print("Authentication successful! Session saved.")
    await close_browser()


async def check_authenticated(page) -> bool:
    url = page.url.lower()
    if "/account/login" in url:
        return False
    if "vpncheeck" in url or "captcha" in url:
        return False
    return True


async def ensure_authenticated(page) -> None:
    if not await check_authenticated(page):
        raise AuthenticationError()
