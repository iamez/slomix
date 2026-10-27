"""Discord link migration must not silently navigate to the wrong frontend."""

from types import SimpleNamespace

import pytest

from bot.website_links import validate_ui_mode, website_url


@pytest.mark.parametrize("route", [
    "/session-detail/date/2026-10-09", "/session-detail/123",
    "/profile/ABCD1234", "/record-book", "/story", "/leaderboards", "/availability",
])
@pytest.mark.parametrize("mode,prefix", [("legacy", "/#"), ("app", "/app")])
def test_public_links_preserve_origin_and_select_frontend(route, mode, prefix):
    config = SimpleNamespace(website_public_base="https://dev.example/", website_ui_mode=mode)
    assert website_url(config, route) == f"https://dev.example{prefix}{route}"


def test_missing_mode_preserves_existing_legacy_links():
    assert website_url(SimpleNamespace(), "/record-book") == "https://www.slomix.fyi/#/record-book"


@pytest.mark.parametrize("mode", ["spa", "APP", "", None])
def test_unknown_frontend_refused(mode):
    with pytest.raises(ValueError, match="WEBSITE_UI_MODE"):
        validate_ui_mode(mode)


@pytest.mark.parametrize("base", [
    "https://dev.example/app", "https://dev.example?x=y", "https://dev.example/#/",
    "https://user:pass@dev.example", "//dev.example", "javascript:alert(1)",
    "http://dev.example:99999", "https://dev.example\n", "https://dev.example\\evil",
])
def test_ambiguous_public_base_refused(base):
    with pytest.raises(ValueError):
        website_url(SimpleNamespace(website_public_base=base), "/record-book")


@pytest.mark.parametrize("route", ["//evil.example", "https://evil.example", "/../admin", "/app/./x", "/x\n", "/x\\y"])
def test_external_or_ambiguous_route_refused(route):
    with pytest.raises(ValueError):
        website_url(SimpleNamespace(), route)


def test_route_values_cannot_inject_a_fragment_or_markdown_link():
    assert website_url(SimpleNamespace(), "/profile/A)#B") == "https://www.slomix.fyi/#/profile/A%29%23B"


def test_local_ipv6_origin_with_port_supported():
    config = SimpleNamespace(website_public_base="http://[::1]:8000", website_ui_mode="app")
    assert website_url(config, "/record-book") == "http://[::1]:8000/app/record-book"
