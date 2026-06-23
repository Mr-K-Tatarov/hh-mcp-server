import logging

from playwright.async_api import Page

from hh_mcp_server.constants import BASE_URL
from hh_mcp_server.exceptions import AuthenticationError, ScrapingError
from hh_mcp_server.scraping import selectors as S
from hh_mcp_server.scraping.apply import dismiss_cookie_banner
from hh_mcp_server.scraping.extractor import extract_resume_id, navigate_and_wait
from hh_mcp_server.scraping.resume_parser import (
    parse_applicant_resumes_payload,
    parse_initial_state_html,
)

logger = logging.getLogger(__name__)

RESUMES_PAGE_URL = f"{BASE_URL}/applicant/resumes?role=applicant"
SHARDS_RESUMES_URL = f"{BASE_URL}/shards/applicant/resumes"


async def _fetch_resumes_via_shards(page: Page) -> tuple[list[dict], bool]:
    """Загружает резюме через внутренний shards API hh.ru.

    Returns:
        Кортеж (список резюме, успешно ли получен ответ API).
    """
    await page.goto(RESUMES_PAGE_URL, wait_until="domcontentloaded", timeout=15000)
    await dismiss_cookie_banner(page)

    if "/account/login" in page.url:
        raise AuthenticationError()

    response = await page.request.get(
        SHARDS_RESUMES_URL,
        headers={
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": RESUMES_PAGE_URL,
        },
    )

    if response.status in {401, 403}:
        raise AuthenticationError()

    if not response.ok:
        logger.warning("Shards API returned HTTP %s", response.status)
        return [], False

    try:
        data = await response.json()
    except Exception:
        logger.warning("Shards API returned non-JSON response")
        return [], False

    resumes = parse_applicant_resumes_payload(data)
    logger.info("Shards API returned %d resumes", len(resumes))
    return resumes, True


async def _fetch_resumes_via_initial_state(page: Page) -> list[dict]:
    """Загружает резюме из SSR JSON на странице списка резюме."""
    await navigate_and_wait(page, RESUMES_PAGE_URL)
    await dismiss_cookie_banner(page)

    if "/account/login" in page.url:
        raise AuthenticationError()

    html = await page.content()
    resumes = parse_initial_state_html(html)
    logger.info("SSR initial state returned %d resumes", len(resumes))
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

    if not resumes:
        link_elements = await page.query_selector_all("a[href*='/resume/']")
        for link_el in link_elements:
            href = await link_el.get_attribute("href") or ""
            resume_id = extract_resume_id(href)
            if not resume_id or resume_id in seen:
                continue

            title = (await link_el.inner_text()).strip()
            if not title or len(title) > 200:
                continue

            seen.add(resume_id)
            resumes.append({
                "id": resume_id,
                "title": title,
                "url": f"{BASE_URL}/resume/{resume_id}",
            })

    logger.info("CSS selectors returned %d resumes", len(resumes))
    return resumes


async def get_my_resumes(page: Page) -> list[dict]:
    """Возвращает список резюме пользователя с hh.ru."""
    shards_resumes, shards_ok = await _fetch_resumes_via_shards(page)
    if shards_ok:
        return shards_resumes

    initial_state_resumes = await _fetch_resumes_via_initial_state(page)
    if initial_state_resumes:
        return initial_state_resumes

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
