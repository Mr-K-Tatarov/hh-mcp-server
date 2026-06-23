import json
import logging
from typing import Any

from playwright.async_api import Page

from hh_mcp_server.constants import BASE_URL
from hh_mcp_server.exceptions import AuthenticationError, ScrapingError
from hh_mcp_server.scraping import selectors as S
from hh_mcp_server.scraping.apply import dismiss_cookie_banner
from hh_mcp_server.scraping.extractor import extract_resume_id, navigate_and_wait
from hh_mcp_server.scraping.resume_parser import (
    parse_applicant_resumes_payload,
    parse_initial_state_json,
)
from hh_mcp_server.scraping.vpn import handle_vpn_warning, is_vpn_blocked, raise_access_blocked_error

logger = logging.getLogger(__name__)

RESUMES_PAGE_URL = f"{BASE_URL}/applicant/resumes?role=applicant"
SHARDS_RESUMES_URL = f"{BASE_URL}/shards/applicant/resumes"

_BROWSER_FETCH_JS = """async ([url, xsrf, referer]) => {
    const headers = {
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': referer,
    };
    if (xsrf) {
        headers['X-Xsrf-Token'] = xsrf;
        headers['X-XSRFToken'] = xsrf;
    }
    const response = await fetch(url, {
        method: 'GET',
        credentials: 'include',
        headers,
    });
    const text = await response.text();
    return { status: response.status, text };
}"""

_DOM_INITIAL_STATE_JS = """() => {
    const tpl = document.getElementById('HH-Lux-InitialState');
    if (!tpl) return null;
    if (tpl.tagName === 'TEMPLATE') {
        return tpl.innerHTML.trim();
    }
    return (tpl.textContent || '').trim();
}"""

_DOM_RESUME_LINKS_JS = """() => {
    const out = [];
    const seen = new Set();
    for (const anchor of document.querySelectorAll('a[href*="/resume/"]')) {
        const match = anchor.href.match(/\\/resume\\/([a-f0-9]{10,})/);
        if (!match || seen.has(match[1])) continue;
        const title = (anchor.textContent || '').trim().replace(/\\s+/g, ' ');
        if (!title || title.length > 200) continue;
        seen.add(match[1]);
        out.push({
            id: match[1],
            title,
            url: anchor.href,
        });
    }
    return out;
}"""


async def _get_xsrf_token(page: Page) -> str | None:
    """Возвращает XSRF-токен из cookies или meta-тега страницы."""
    cookies = await page.context.cookies(BASE_URL)
    for cookie in cookies:
        if cookie["name"] in {"_xsrf", "XSRF-TOKEN"}:
            return cookie["value"]

    return await page.evaluate("""() => {
        const meta = document.querySelector('meta[name="csrf-token"], meta[name="xsrf-token"]');
        return meta ? meta.getAttribute('content') : null;
    }""")


async def _prepare_resumes_page(page: Page) -> None:
    """Открывает страницу резюме и дожидается загрузки клиентских запросов."""
    if RESUMES_PAGE_URL not in page.url or await is_vpn_blocked(page):
        await page.goto(RESUMES_PAGE_URL, wait_until="domcontentloaded", timeout=30000)

    await dismiss_cookie_banner(page)

    if "/account/login" in page.url:
        raise AuthenticationError()

    if await is_vpn_blocked(page):
        if not await handle_vpn_warning(page):
            raise_access_blocked_error()

    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        logger.debug("networkidle timeout on resumes page, continuing")

    await page.wait_for_timeout(1500)

    if await is_vpn_blocked(page):
        raise_access_blocked_error()


async def _browser_fetch_json(page: Page, url: str) -> tuple[int, Any | None]:
    """Выполняет fetch в контексте браузера с cookies сессии."""
    xsrf = await _get_xsrf_token(page)
    result = await page.evaluate(
        _BROWSER_FETCH_JS,
        [url, xsrf, RESUMES_PAGE_URL],
    )

    status = int(result.get("status", 0))
    text = result.get("text", "")
    if not text:
        return status, None

    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Browser fetch returned non-JSON for %s", url)
        return status, None


async def _fetch_resumes_via_shards(page: Page) -> tuple[list[dict], bool]:
    """Загружает резюме через shards API (перехват ответа или browser fetch)."""
    captured: Any | None = None

    async def on_response(response) -> None:
        nonlocal captured
        if captured is not None:
            return
        if "/shards/applicant/resumes" not in response.url:
            return
        if response.status in {401, 403}:
            raise AuthenticationError()
        if response.ok:
            try:
                captured = await response.json()
            except Exception:
                logger.warning("Failed to parse intercepted shards response")

    page.on("response", on_response)
    try:
        await _prepare_resumes_page(page)

        if captured is not None:
            resumes = parse_applicant_resumes_payload(captured)
            logger.info("Intercepted shards API returned %d resumes", len(resumes))
            return resumes, True

        status, data = await _browser_fetch_json(page, SHARDS_RESUMES_URL)
        if status in {401, 403}:
            raise AuthenticationError()
        if status == 200 and data is not None:
            resumes = parse_applicant_resumes_payload(data)
            logger.info("Browser shards fetch returned %d resumes", len(resumes))
            return resumes, True

        logger.warning("Shards API unavailable: HTTP %s", status)
        return [], False
    finally:
        page.remove_listener("response", on_response)


async def _fetch_resumes_via_dom_initial_state(page: Page) -> list[dict]:
    """Читает HH-Lux-InitialState из DOM после выполнения JS."""
    raw_json = await page.evaluate(_DOM_INITIAL_STATE_JS)
    if not raw_json:
        logger.info("HH-Lux-InitialState not found in DOM")
        return []

    resumes = parse_initial_state_json(raw_json)
    logger.info("DOM initial state returned %d resumes", len(resumes))
    return resumes


async def _fetch_resumes_via_dom_links(page: Page) -> list[dict]:
    """Извлекает резюме из ссылок на странице после гидратации."""
    try:
        await page.wait_for_selector("a[href*='/resume/']", timeout=12000)
    except Exception:
        logger.debug("Resume links not found within timeout")

    resumes = await page.evaluate(_DOM_RESUME_LINKS_JS)
    logger.info("DOM resume links returned %d resumes", len(resumes))
    return resumes


async def _fetch_resumes_via_selectors(page: Page) -> list[dict]:
    """Fallback: парсинг карточек резюме по CSS-селекторам."""
    await navigate_and_wait(page, RESUMES_PAGE_URL, S.RESUME_CARD)
    await dismiss_cookie_banner(page)

    cards = await page.query_selector_all(S.RESUME_CARD)
    resumes: list[dict] = []
    seen: set[str] = set()

    for card in cards:
        title_el = await card.query_selector(S.RESUME_TITLE_LINK)
        if not title_el:
            continue

        title = (await title_el.inner_text()).strip()
        href = await title_el.get_attribute("href") or ""
        resume_id = extract_resume_id(href)
        if not resume_id or resume_id in seen:
            continue

        seen.add(resume_id)
        resumes.append({
            "id": resume_id,
            "title": title or "Без названия",
            "url": f"{BASE_URL}/resume/{resume_id}",
        })

    logger.info("CSS selectors returned %d resumes", len(resumes))
    return resumes


async def get_my_resumes(page: Page) -> list[dict]:
    """Возвращает список резюме пользователя с hh.ru."""
    shards_resumes, shards_ok = await _fetch_resumes_via_shards(page)
    if shards_ok:
        return shards_resumes

    initial_state_resumes = await _fetch_resumes_via_dom_initial_state(page)
    if initial_state_resumes:
        return initial_state_resumes

    dom_link_resumes = await _fetch_resumes_via_dom_links(page)
    if dom_link_resumes:
        return dom_link_resumes

    selector_resumes = await _fetch_resumes_via_selectors(page)
    if selector_resumes:
        return selector_resumes

    raise ScrapingError(
        "Не удалось загрузить список резюме. "
        "Проверьте сессию hh.ru или повторите попытку позже."
    )


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
