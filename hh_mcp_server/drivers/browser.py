import asyncio
import logging
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from hh_mcp_server.constants import PROFILE_DIR, STATE_FILE

logger = logging.getLogger(__name__)

_playwright = None
_browser: Optional[Browser] = None
_context: Optional[BrowserContext] = None
_headless: bool = True


def set_headless(value: bool) -> None:
    global _headless
    _headless = value


async def get_or_create_context() -> BrowserContext:
    global _playwright, _browser, _context

    if _context is not None:
        return _context

    _playwright = await async_playwright().start()

    _browser = await _playwright.chromium.launch(
        headless=_headless,
        args=["--disable-blink-features=AutomationControlled"],
    )

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    kwargs = {
        "viewport": {"width": 1280, "height": 720},
        "user_agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
    }

    if STATE_FILE.exists():
        kwargs["storage_state"] = str(STATE_FILE)
        logger.info("Restoring session from %s", STATE_FILE)

    _context = await _browser.new_context(**kwargs)
    return _context


async def get_page() -> Page:
    ctx = await get_or_create_context()
    pages = ctx.pages
    if pages:
        return pages[0]
    return await ctx.new_page()


async def save_state() -> None:
    if _context is not None:
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        await _context.storage_state(path=str(STATE_FILE))
        logger.info("Session saved to %s", STATE_FILE)


async def close_browser() -> None:
    global _playwright, _browser, _context

    if _context is not None:
        await save_state()
        await _context.close()
        _context = None

    if _browser is not None:
        await _browser.close()
        _browser = None

    if _playwright is not None:
        await _playwright.stop()
        _playwright = None
