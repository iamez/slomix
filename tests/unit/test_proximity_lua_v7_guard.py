"""Guard tests for the v7 draft (Lua 6.10) — dormancy is the contract.

The dormant v7 features MUST stay default-OFF in the repo (reproducible fresh
installs, owner-gated live enablement), their sections must exist behind
isFeatureEnabled gates, and the comm callback must not intercept commands.

`aim_lock` is the one intentionally-ACTIVE exception (activated 2026-06-22 on
the proximity-quick-wins branch); it is still feature-gated and still has a
section header, but it ships ON. The other three remain dormant.
"""
from pathlib import Path

import pytest


def _lua_source() -> str:
    root = Path(__file__).resolve().parents[2]
    lua_path = root / "proximity" / "lua" / "proximity_tracker.lua"
    return lua_path.read_text(encoding="utf-8")


# All four are feature-gated and have section headers; only the dormant three
# must ship default-OFF. aim_lock is intentionally active (see module docstring).
V7_FLAGS = ("aim_lock", "spawn_select", "skill_snapshot", "comm_events")
DORMANT_V7_FLAGS = ("spawn_select", "skill_snapshot", "comm_events")
V7_SECTIONS = ("# AIM_LOCK", "# SPAWN_SELECT", "# SKILL_SNAPSHOT", "# COMM_EVENTS")


@pytest.mark.parametrize("flag", DORMANT_V7_FLAGS)
def test_v7_flags_default_off(flag: str) -> None:
    source = _lua_source()
    assert f"{flag} = false" in source, (
        f"features.{flag} must ship default-OFF (dormant v7 contract; "
        "enable only via the owner-gated testmode probe)"
    )


def test_aim_lock_is_intentionally_active() -> None:
    """aim_lock is the deliberate v7 exception — capture is ON in the repo.

    This guards against an accidental silent flip back to dormant (which would
    quietly stop populating the live aim-lock leaderboard). If aim_lock is ever
    intentionally turned off again, move it back into DORMANT_V7_FLAGS.
    """
    assert "aim_lock = true" in _lua_source(), (
        "features.aim_lock is expected ACTIVE (activated 2026-06-22); "
        "if intentionally disabled, move it to DORMANT_V7_FLAGS"
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
