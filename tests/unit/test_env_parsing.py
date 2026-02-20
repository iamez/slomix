from bot.config import _strip_inline_env_comment
from website.backend.env_utils import getenv_int, strip_inline_comment


def test_strip_inline_comment_keeps_plain_hash_strings():
    assert strip_inline_comment("abc#123") == "abc#123"
    assert _strip_inline_env_comment("abc#123") == "abc#123"


def test_strip_inline_comment_removes_trailing_comment_text():
    raw = "27960  # ET:Legacy game port"
    assert strip_inline_comment(raw) == "27960"
    assert _strip_inline_env_comment(raw) == "27960"


def test_getenv_int_parses_inline_comment_value(monkeypatch):
    monkeypatch.setenv("TEST_ENV_INT", " 7000  # website port ")
    assert getenv_int("TEST_ENV_INT", 1) == 7000


def test_getenv_int_uses_default_for_missing_or_empty(monkeypatch):
    monkeypatch.delenv("TEST_ENV_INT", raising=False)
    assert getenv_int("TEST_ENV_INT", 42) == 42

    monkeypatch.setenv("TEST_ENV_INT", "   ")
    assert getenv_int("TEST_ENV_INT", 42) == 42
