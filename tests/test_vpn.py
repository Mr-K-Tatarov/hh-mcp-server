"""Тесты обработки VPN-предупреждения hh.ru."""

from hh_mcp_server.scraping.vpn import is_access_blocked


def test_is_access_blocked_vpn() -> None:
    """vpncheeck считается блокировкой."""
    assert is_access_blocked("https://hh.ru/vpncheeck?backUrl=%2Fapplicant%2Fresumes")


def test_is_access_blocked_captcha() -> None:
    """captcha в URL считается блокировкой."""
    assert is_access_blocked("https://hh.ru/account/captcha")


def test_is_access_blocked_normal() -> None:
    """Обычная страница не считается блокировкой."""
    assert not is_access_blocked("https://hh.ru/applicant/resumes?role=applicant")
