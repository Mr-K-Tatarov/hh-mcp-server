"""Парсинг списка резюме из shards API и SSR-состояния hh.ru."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from hh_mcp_server.constants import BASE_URL

logger = logging.getLogger(__name__)

_INITIAL_STATE_RE = re.compile(
    r'<template[^>]+id=["\']HH-Lux-InitialState["\'][^>]*>(.*?)</template>',
    re.DOTALL | re.IGNORECASE,
)
_RESUME_HASH_RE = re.compile(r"/resume/([a-f0-9]{10,})")


def _extract_title(raw: dict[str, Any]) -> str:
    """Извлекает название резюме из объекта hh.ru."""
    title = raw.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()

    if isinstance(title, list):
        parts: list[str] = []
        for item in title:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
            elif isinstance(item, dict):
                value = item.get("string") or item.get("data") or item.get("text")
                if isinstance(value, str) and value.strip():
                    parts.append(value.strip())
        if parts:
            return "; ".join(parts)

    for key in ("name", "profession", "position"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def _extract_resume_id(raw: dict[str, Any]) -> str | None:
    """Извлекает hash/id резюме из объекта hh.ru."""
    attributes = raw.get("_attributes")
    if isinstance(attributes, dict):
        for key in ("hash", "resumeHash", "id"):
            value = attributes.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    for key in ("hash", "resumeHash", "id"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    alternate_url = raw.get("alternate_url") or raw.get("url")
    if isinstance(alternate_url, str):
        match = _RESUME_HASH_RE.search(alternate_url)
        if match:
            return match.group(1)

    return None


def resume_item_from_raw(raw: dict[str, Any]) -> dict[str, str] | None:
    """Преобразует сырой объект резюме hh.ru в формат MCP-инструмента."""
    resume_id = _extract_resume_id(raw)
    if not resume_id:
        return None

    title = _extract_title(raw) or "Без названия"
    return {
        "id": resume_id,
        "title": title,
        "url": f"{BASE_URL}/resume/{resume_id}",
    }


def _find_applicant_resumes_nested(data: Any) -> list[dict[str, Any]]:
    """Рекурсивно ищет массив applicantResumes в произвольной структуре JSON."""
    if isinstance(data, dict):
        value = data.get("applicantResumes")
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        for nested in data.values():
            found = _find_applicant_resumes_nested(nested)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _find_applicant_resumes_nested(item)
            if found:
                return found
    return []


def _collect_resume_objects(data: Any) -> list[dict[str, Any]]:
    """Собирает список объектов резюме из разных форматов ответа hh.ru."""
    nested = _find_applicant_resumes_nested(data)
    if nested:
        return nested

    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    if not isinstance(data, dict):
        return []

    for key in ("resumes", "items", "resumeList"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    if any(key in data for key in ("_attributes", "hash", "title")):
        return [data]

    return []


def parse_applicant_resumes_payload(data: Any) -> list[dict[str, str]]:
    """Парсит JSON shards API или SSR initial state в список резюме."""
    resumes: list[dict[str, str]] = []
    seen: set[str] = set()

    for raw in _collect_resume_objects(data):
        item = resume_item_from_raw(raw)
        if item is None or item["id"] in seen:
            continue
        seen.add(item["id"])
        resumes.append(item)

    return resumes


def parse_initial_state_json(raw_json: str) -> list[dict[str, str]]:
    """Парсит JSON из HH-Lux-InitialState."""
    if not raw_json.strip():
        return []

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        logger.warning("Failed to parse HH-Lux-InitialState JSON")
        return []

    return parse_applicant_resumes_payload(data)


def parse_initial_state_html(html: str) -> list[dict[str, str]]:
    """Извлекает резюме из `<template id=\"HH-Lux-InitialState\">`."""
    match = _INITIAL_STATE_RE.search(html)
    if not match:
        logger.warning("HH-Lux-InitialState not found in HTML")
        return []

    return parse_initial_state_json(match.group(1))
