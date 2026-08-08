"""Guard tests for the objective live-ping feature in stats_discord_webhook.lua.

Mirrors the pattern in test_proximity_lua_v7_guard.py: pin the source-text
contract for a feature the repo cannot execute directly (no Lua-Python
bridge here) rather than leaving it unguarded. The actual detection LOGIC
(pattern matching, color-code stripping, JSON escaping) was verified
separately with lua5.4 during development — see
docs/research/ENVIRONMENT_IDENTITY_RCA_2026-08-08.md's sibling workstream-D
notes. This file pins the two properties that matter for safety:

1. Dormant by default (objective_live_ping_enabled = false) — a fresh
   deploy/reload must not start pinging Discord unannounced.
2. The new payload must never collide with the STATS_READY dispatch key
   bot/services/webhook_handler_mixin.py:214 checks for — that would make
   the bot try to process a live ping as a finished round.
"""
import re
from pathlib import Path

import pytest


def _lua_source() -> str:
    root = Path(__file__).resolve().parents[2]
    lua_path = root / "vps_scripts" / "stats_discord_webhook.lua"
    return lua_path.read_text(encoding="utf-8")


def test_objective_live_ping_default_off() -> None:
    source = _lua_source()
    assert "objective_live_ping_enabled = false" in source, (
        "objective_live_ping_enabled must ship default-OFF — a fresh deploy "
        "or map reload must not start posting to Discord unannounced"
    )


def test_et_print_is_defined_and_gated_on_the_feature_flag() -> None:
    source = _lua_source()
    assert "function et_Print(text)" in source, (
        "the live-ping handler must be defined as a top-level et_Print "
        "callback for the engine to call it"
    )
    # The gate check must be the first thing the function does (before any
    # pattern matching), so a disabled flag costs one boolean read per
    # console line, not a wasted string search.
    print_idx = source.index("function et_Print(text)")
    gate_idx = source.index("if not configuration.objective_live_ping_enabled then return end")
    assert gate_idx > print_idx, "the feature-flag gate must be inside et_Print"
    assert gate_idx - print_idx < 200, (
        "the feature-flag gate should be the first check in et_Print, not "
        "buried after other logic"
    )


def test_live_ping_payload_never_sets_stats_ready_content() -> None:
    """The one real safety property: this payload must not be mistaken for
    a round-completion webhook by the bot's dispatch logic.

    bot/services/webhook_handler_mixin.py:214 dispatches on
    `message.content.strip() == "STATS_READY"`. The round-end embed
    (existing, unrelated code) legitimately sets that. The live-ping embed
    must not — extract just the live-ping payload block and confirm.
    """
    source = _lua_source()
    start = source.index("function et_Print(text)")
    end = source.index("function et_ShutdownGame")
    live_ping_block = source[start:end]
    assert '"content": "STATS_READY"' not in live_ping_block, (
        "the live-ping payload must never set content=STATS_READY — that "
        "string is the bot's dispatch key for a finished round "
        "(webhook_handler_mixin.py:214); reusing it here would make the "
        "bot try to process a live ping as a completed round"
    )


_KEYWORD_CALL_RE = re.compile(r'string\.find\(lower,\s*"([^"]+)"\)')


def test_live_ping_reuses_the_proven_carrier_detection_pattern() -> None:
    """The detection pattern (legacy announce: + secured/transmitted/
    delivered/escaped) must match proximity_tracker.lua's own carrier-event
    detection **exactly** — it's copied from there deliberately, not
    reinvented. A drift between the two (either file gaining or losing a
    keyword in its actual `string.find(lower, ...)` condition) would mean
    one file considers an event an objective capture and the other doesn't.

    Extracts the literal keyword SET each file's detection condition
    actually checks — not just "does this word appear somewhere in the
    file" (a word could survive in a comment, or in the unrelated
    round-end embed further down, while the real condition drifted).
    (CodeRabbit + Copilot review on #624.)
    """
    live_source = _lua_source()
    tracker_path = (
        Path(__file__).resolve().parents[2]
        / "proximity"
        / "lua"
        / "proximity_tracker.lua"
    )
    tracker_source = tracker_path.read_text(encoding="utf-8")

    live_start = live_source.index("function et_Print(text)")
    live_end = live_source.index("function et_ShutdownGame")
    live_block = live_source[live_start:live_end]

    tracker_start = tracker_source.index("-- Secure detection via announce")
    tracker_end = tracker_source.index("-- v6 Phase 1.5: Flag return detection")
    tracker_block = tracker_source[tracker_start:tracker_end]

    live_keywords = set(_KEYWORD_CALL_RE.findall(live_block))
    tracker_keywords = set(_KEYWORD_CALL_RE.findall(tracker_block))

    expected = {"secured", "transmitted", "delivered", "escaped"}
    assert live_keywords == expected, (
        f"live-ping's actual string.find(lower, ...) keyword set is "
        f"{live_keywords}, expected {expected}"
    )
    assert tracker_keywords == expected, (
        f"proximity_tracker.lua's carrier-detection keyword set drifted to "
        f"{tracker_keywords}, live-ping was copied from {expected}"
    )
    assert live_keywords == tracker_keywords, (
        "keyword sets differ between the two files: "
        f"live-ping has {live_keywords}, proximity_tracker.lua has {tracker_keywords}"
    )

    assert '"legacy announce:"' in live_block
    assert "legacy announce:" in tracker_block


@pytest.mark.parametrize("helper", ["strip_color_codes", "json_escape", "execute_curl_async"])
def test_live_ping_reuses_existing_helpers_not_new_ones(helper: str) -> None:
    """The whole point of extending this file (not writing a new transport)
    is reusing its already-proven helpers. Confirm et_Print actually calls
    them rather than duplicating logic inline."""
    source = _lua_source()
    start = source.index("function et_Print(text)")
    end = source.index("function et_ShutdownGame")
    live_ping_block = source[start:end]
    assert helper in live_ping_block, (
        f"et_Print should call the existing {helper}() helper, not "
        "reimplement equivalent logic"
    )
