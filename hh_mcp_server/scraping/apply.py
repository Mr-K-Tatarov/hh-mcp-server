import logging

from playwright.async_api import Page

from hh_mcp_server.constants import BASE_URL
from hh_mcp_server.scraping import selectors as S
from hh_mcp_server.scraping.extractor import navigate_and_wait
from hh_mcp_server.exceptions import ApplyError

logger = logging.getLogger(__name__)


async def detect_questions(page: Page) -> list[dict]:
    """Detect employer questions in the apply form.

    Works for both popup and full-page response forms.
    Questions are textareas with name='task_*_text'.
    """
    questions = []

    result = await page.evaluate("""() => {
        const textareas = document.querySelectorAll('textarea[name^="task_"]');
        const out = [];
        for (const ta of textareas) {
            const name = ta.getAttribute('name') || '';
            // Walk up to find the question container and extract label
            let el = ta;
            let labelText = '';
            for (let i = 0; i < 8 && el.parentElement; i++) {
                el = el.parentElement;
                // Look for text nodes that are the question label
                const children = el.children;
                for (const child of children) {
                    // Skip the textarea wrapper itself
                    if (child.querySelector('textarea')) continue;
                    const t = child.textContent.trim();
                    if (t && t.length > 3 && t.length < 500
                        && !t.includes('Писать тут')
                        && !t.includes('0/')
                        && t !== 'Ответьте на вопросы') {
                        labelText = t;
                        break;
                    }
                }
                if (labelText) break;
            }
            out.push({name: name, label: labelText});
        }
        return out;
    }""")

    for item in result:
        questions.append({
            "label": item["label"],
            "type": "textarea",
            "name": item["name"],
        })

    return questions


async def fill_questions(page: Page, questions: list[dict], answers: dict[str, str]) -> None:
    """Fill in question answers by matching label text or name to textarea."""
    for q in questions:
        label = q["label"]
        name = q["name"]
        # Try matching by label first, then by name
        answer = answers.get(label) or answers.get(name)
        if not answer:
            # Try fuzzy match - strip whitespace and compare
            for key, val in answers.items():
                if key.strip() == label.strip():
                    answer = val
                    break
        if not answer:
            logger.warning("No answer found for question: %s (name=%s)", label, name)
            continue

        textarea = await page.query_selector(f'textarea[name="{name}"]')
        if textarea:
            await textarea.fill(answer)
            logger.info("Filled question '%s' with answer", label[:50])


async def dismiss_cookie_banner(page: Page) -> None:
    """Dismiss cookie consent banner if present."""
    try:
        btn = await page.query_selector("[data-qa='cookies-policy-informer-accept']")
        if btn:
            await btn.click()
            await page.wait_for_timeout(500)
    except Exception:
        pass


async def _fill_cover_letter(page: Page, cover_letter: str) -> None:
    """Fill cover letter on the page (works for both popup and full-page forms)."""
    toggle = await page.query_selector(S.COVER_LETTER_TOGGLE)
    if toggle:
        await toggle.click()
        await page.wait_for_timeout(1000)

    letter_input = await page.query_selector(S.COVER_LETTER_INPUT)
    if letter_input:
        await letter_input.fill(cover_letter)
        logger.info("Cover letter filled")
    else:
        logger.warning("Cover letter input not found")


async def apply_to_vacancy(
    page: Page,
    vacancy_id: str,
    resume_id: str | None = None,
    cover_letter: str | None = None,
    question_answers: dict[str, str] | None = None,
) -> dict:
    url = f"{BASE_URL}/vacancy/{vacancy_id}"
    await navigate_and_wait(page, url)

    await dismiss_cookie_banner(page)

    # Check if already applied
    already = await page.query_selector(S.ALREADY_APPLIED)
    if already:
        return {"status": "already_applied", "message": "You have already applied to this vacancy."}

    # Click apply button
    apply_btn = await page.query_selector(S.APPLY_BUTTON)
    if not apply_btn:
        return {"status": "error", "message": "Apply button not found. Vacancy may be closed."}

    await apply_btn.click()
    await page.wait_for_timeout(2000)

    # Handle relocation warning popup if it appears
    relocation_confirm = await page.query_selector("[data-qa='relocation-warning-confirm']")
    if relocation_confirm:
        await relocation_confirm.click()
        await page.wait_for_timeout(2000)

    # Check if redirected to full-page response form
    is_response_page = "vacancy_response" in page.url

    # Check if a popup form appeared
    form = await page.query_selector(S.APPLY_FORM)

    if not form and not is_response_page:
        # Maybe it applied directly (one-click apply)
        if "negotiations" in page.url:
            return {"status": "success", "message": "Applied successfully (direct apply)."}

        # Re-check if already applied (button click may have triggered a quick-apply)
        already_after_click = await page.query_selector(S.ALREADY_APPLIED)
        if already_after_click:
            return {"status": "already_applied", "message": "You have already applied to this vacancy."}

        return {"status": "error", "message": "Apply form did not appear."}

    # Detect questions
    questions = await detect_questions(page)
    if questions and not question_answers:
        return {
            "status": "questions_required",
            "message": "This vacancy has questions that need to be answered. Call again with question_answers.",
            "questions": questions,
        }

    # Fill questions if provided
    if question_answers and questions:
        await fill_questions(page, questions, question_answers)

    # Fill cover letter
    if cover_letter:
        await _fill_cover_letter(page, cover_letter)

    # Submit
    submit_btn = await page.query_selector(S.SUBMIT_BUTTON)
    if not submit_btn:
        return {"status": "error", "message": "Submit button not found."}

    await submit_btn.click()
    await page.wait_for_timeout(3000)

    # Check if still on response page (submit failed due to validation)
    if "vacancy_response" in page.url:
        # Check for validation errors
        error_text = await page.evaluate("""() => {
            const el = document.querySelector('[data-qa="vacancy-response-popup-error"]');
            if (el) return el.textContent.trim();
            // Check if questions are still shown (not answered)
            const q = document.querySelector('textarea[name^="task_"]');
            if (q) return 'Required questions were not answered.';
            return '';
        }""")
        if error_text:
            return {"status": "error", "message": error_text}

    # Check for error in popup form
    error_el = await page.query_selector("[data-qa='vacancy-response-popup-error']")
    if error_el:
        error_text = await error_el.inner_text()
        return {"status": "error", "message": error_text.strip()}

    return {"status": "success", "message": f"Applied to vacancy {vacancy_id} successfully."}
