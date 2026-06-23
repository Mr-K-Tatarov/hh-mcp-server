"""Обработка предупреждения hh.ru о VPN/прокси."""

from __future__ import annotations

import logging

from playwright.async_api import Page

from hh_mcp_server.exceptions import ScrapingError

logger = logging.getLogger(__name__)

VPN_URL_FRAGMENT = "vpncheeck"


def is_access_blocked(url: str) -> bool:
    """Проверяет, заблокирован ли доступ (VPN, капча)."""
    lowered = url.lower()
    return VPN_URL_FRAGMENT in lowered or "captcha" in lowered


async def is_vpn_blocked(page: Page) -> bool:
    """Проверяет, показывает ли страница предупреждение VPN."""
    return is_access_blocked(page.url)


async def handle_vpn_warning(page: Page) -> bool:
    """Пытается пройти стандартное предупреждение hh.ru о VPN.

    Returns:
        True, если страница больше не на vpncheeck.
    """
    if not await is_vpn_blocked(page):
        return True

    logger.info("Обнаружено предупреждение VPN на hh.ru, пробуем продолжить")

    for label in ("Попробовать снова", "Я не использую VPN"):
        locator = page.get_by_text(label, exact=False)
        if await locator.count() == 0:
            continue
        try:
            await locator.first.click(timeout=5000)
            await page.wait_for_timeout(2500)
            if not await is_vpn_blocked(page):
                logger.info("Предупреждение VPN пройдено после «%s»", label)
                return True
        except Exception as exc:
            logger.debug("Не удалось нажать «%s»: %s", label, exc)

    return not await is_vpn_blocked(page)


def raise_access_blocked_error() -> None:
    """Пробрасывает понятную ошибку при блокировке доступа."""
    raise ScrapingError(
        "hh.ru заблокировал доступ (предупреждение VPN/прокси). "
        "Отключите VPN, закройте другие прокси и войдите снова через /login."
    )
