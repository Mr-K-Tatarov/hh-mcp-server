"""Тесты парсинга списка резюме."""

from __future__ import annotations

import pytest

from hh_mcp_server.scraping.resume_parser import (
    parse_applicant_resumes_payload,
    parse_initial_state_html,
    resume_item_from_raw,
)


def test_resume_item_from_raw_with_attributes() -> None:
    """Парсит резюме из формата shards/SSR с _attributes."""
    raw = {
        "_attributes": {"hash": "abc123def456"},
        "title": [{"string": "Backend Developer"}],
    }
    item = resume_item_from_raw(raw)
    assert item == {
        "id": "abc123def456",
        "title": "Backend Developer",
        "url": "https://hh.ru/resume/abc123def456",
    }


def test_resume_item_from_raw_without_title_uses_fallback() -> None:
    """Использует запасное название, если title отсутствует."""
    raw = {"hash": "deadbeef", "title": []}
    item = resume_item_from_raw(raw)
    assert item is not None
    assert item["id"] == "deadbeef"
    assert item["title"] == "Без названия"


def test_parse_applicant_resumes_payload_from_shards() -> None:
    """Парсит список резюме из shards API."""
    payload = {
        "applicantResumes": [
            {
                "_attributes": {"hash": "111"},
                "title": [{"string": "Python Dev"}],
            },
            {
                "_attributes": {"hash": "222"},
                "title": [{"string": "Go Dev"}],
            },
        ]
    }
    resumes = parse_applicant_resumes_payload(payload)
    assert len(resumes) == 2
    assert resumes[0]["title"] == "Python Dev"
    assert resumes[1]["id"] == "222"


def test_parse_applicant_resumes_payload_empty_list() -> None:
    """Пустой список резюме — валидный ответ."""
    assert parse_applicant_resumes_payload({"applicantResumes": []}) == []


def test_parse_initial_state_html() -> None:
    """Парсит JSON из HH-Lux-InitialState."""
    html = """
    <html>
      <body>
        <template id="HH-Lux-InitialState">
          {"applicantResumes":[{"_attributes":{"hash":"aaa"},"title":[{"string":"QA"}]}]}
        </template>
      </body>
    </html>
    """
    resumes = parse_initial_state_html(html)
    assert len(resumes) == 1
    assert resumes[0]["title"] == "QA"
    assert resumes[0]["id"] == "aaa"


def test_parse_initial_state_html_missing_template() -> None:
    """Возвращает пустой список, если SSR-шаблон не найден."""
    assert parse_initial_state_html("<html><body></body></html>") == []


def test_parse_initial_state_html_invalid_json() -> None:
    """Возвращает пустой список при битом JSON."""
    html = '<template id="HH-Lux-InitialState">{broken</template>'
    assert parse_initial_state_html(html) == []
