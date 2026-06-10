"""Guard tests for the v7 draft (Lua 6.10) — dormancy is the contract.

The four v7 features MUST stay default-OFF in the repo (reproducible fresh
installs, owner-gated live enablement), their sections must exist behind
isFeatureEnabled gates, and the comm callback must not intercept commands.
"""
from pathlib import Path

import pytest


def _lua_source() -> str:
    root = Path(__file__).resolve().parents[2]
    lua_path = root / "proximity" / "lua" / "proximity_tracker.lua"
    return lua_path.read_text(encoding="utf-8")


V7_FLAGS = ("aim_lock", "spawn_select", "skill_snapshot", "comm_events")
V7_SECTIONS = ("# AIM_LOCK", "# SPAWN_SELECT", "# SKILL_SNAPSHOT", "# COMM_EVENTS")


@pytest.mark.parametrize("flag", V7_FLAGS)
def test_v7_flags_default_off(flag: str) -> None:
    source = _lua_source()
    assert f"{flag} = false" in source, (
        f"features.{flag} must ship default-OFF (dormant v7 contract; "
        "enable only via the owner-gated testmode probe)"
    )


@pytest.mark.parametrize("section", V7_SECTIONS)
def test_v7_section_headers_present(section: str) -> None:
    assert section in _lua_source()


@pytest.mark.parametrize("flag", V7_FLAGS)
def test_v7_sections_are_feature_gated(flag: str) -> None:
    assert f'isFeatureEnabled("{flag}")' in _lua_source()


def test_comm_callback_never_intercepts_commands() -> None:
    """et_ClientCommand must return 0 on every path — a non-zero return
    would swallow the player's command and break gameplay."""
    source = _lua_source()
    start = source.index("function et_ClientCommand(")
    end = source.index("\nend", start)
    body = source[start:end]
    returns = [line.strip() for line in body.splitlines() if line.strip().startswith("return")]
    assert returns, "et_ClientCommand must return explicitly"
    assert all(r == "return 0" for r in returns), f"non-zero return found: {returns}"


def test_version_is_v7_draft() -> None:
    assert 'local version = "6.10"' in _lua_source()
