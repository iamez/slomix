"""The manifest's two load-bearing claims, checked against the tracker itself.

1. `SECTION_GATES` really is what the Lua does. The table is the only place
   where a wrong entry produces a manifest that is confidently, silently wrong
   — it would report `enabled` for a capability that was never on. So the test
   re-derives the gates from `proximity_tracker.lua` and fails on any drift,
   rather than restating what a human once read.

   ⚠️ Writing that derivation caught two mistakes in the table's first draft:
   a naive backwards scan attributed REVIVES and WEAPON_ACCURACY to
   `trade_kills`, because it stopped at the previous sibling block instead of
   the enclosing one. The scan below rewinds past closed siblings for exactly
   that reason.

2. A historical round never yields `disabled`. Section absence is not evidence
   (see the module docstring), so the inference path may only ever answer
   `enabled` or `unknown`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from proximity.parser.capability_manifest import (
    DISABLED,
    ENABLED,
    FEATURE_FLAGS,
    SECTION_GATES,
    UNKNOWN,
    build_manifest,
    is_declared,
    parse_declaration,
)

TRACKER = Path(__file__).resolve().parents[2] / "proximity" / "lua" / "proximity_tracker.lua"

#: Sections whose OUTPUT carries no `isFeatureEnabled` check, because the flag
#: gates the collection that fills them instead. Named here so the derivation
#: below can tell a documented case apart from a regression.
COLLECTION_GATED = {
    # `engagement_tracking` guards et_Obituary/et_Damage recording; the section
    # header itself is written unconditionally.
    "ENGAGEMENTS": "engagement_tracking",
    # `heatmap_generation` guards every recordHeatmap call; headers likewise.
    "KILL_HEATMAP": "heatmap_generation",
    "MOVEMENT_HEATMAP": "heatmap_generation",
    # Output checks only the row count; `kill_outcome_tracking` decides whether
    # outcomes are ever collected.
    "KILL_OUTCOME": "kill_outcome_tracking",
}

_HDR = re.compile(r'"(?:\\n)?# ([A-Z_]+)\\n')
_GUARD = re.compile(r'isFeatureEnabled\("([a-z_]+)"\)')
_OPENS = re.compile(r"\b(then|do)\s*$")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _derive_output_gates(source: str) -> dict[str, str | None]:
    """For each section header write, the feature flag enclosing it, if any."""
    lines = source.splitlines()
    gates: dict[str, str | None] = {}
    for i, line in enumerate(lines):
        match = _HDR.search(line)
        if not match:
            continue
        section = match.group(1)
        current = _indent(line)
        found: str | None = None
        j = i - 1
        while j >= 0:
            candidate = lines[j]
            if not candidate.strip() or _indent(candidate) >= current:
                j -= 1
                continue
            indent = _indent(candidate)
            body = candidate.strip()
            if body.startswith("end"):
                # A sibling block that already closed. Rewind past its opener,
                # otherwise its guard reads as an enclosing one — the exact bug
                # this test exists to prevent.
                depth = 1
                j -= 1
                while j >= 0 and depth:
                    other = lines[j]
                    if other.strip() and _indent(other) == indent:
                        if other.strip().startswith("end"):
                            depth += 1
                        elif _OPENS.search(other):
                            depth -= 1
                    j -= 1
                continue
            if _OPENS.search(body):
                guard = _GUARD.search(body)
                if guard and found is None:
                    found = guard.group(1)
                current = indent
            j -= 1
        gates.setdefault(section, found)
    return gates


@pytest.fixture(scope="module")
def output_gates() -> dict[str, str | None]:
    return _derive_output_gates(TRACKER.read_text())


def test_every_section_the_tracker_writes_is_in_the_table(output_gates) -> None:
    assert set(output_gates) - set(SECTION_GATES) == set(), (
        "the tracker writes a section the manifest does not classify"
    )


def test_gates_match_the_tracker(output_gates) -> None:
    """No entry may claim a flag the tracker does not actually check."""
    for section, derived in output_gates.items():
        declared = SECTION_GATES[section]
        if derived is not None:
            assert derived == declared, (
                f"{section}: tracker gates on {derived!r}, table says {declared!r}"
            )
        elif declared is not None:
            assert COLLECTION_GATED.get(section) == declared, (
                f"{section}: table claims gate {declared!r} but the tracker's "
                f"output has no such check and it is not a documented "
                f"collection-gated section"
            )


def test_flag_vocabulary_matches_the_tracker() -> None:
    source = TRACKER.read_text()
    block = source[source.index("    features = {"):]
    block = block[: block.index("\n    },")]
    flags = re.findall(r"^\s{8}([a-z_]+)\s*=\s*(?:true|false)", block, re.M)
    assert tuple(flags) == FEATURE_FLAGS


def test_every_gate_is_a_real_flag() -> None:
    for section, gate in SECTION_GATES.items():
        assert gate is None or gate in FEATURE_FLAGS, f"{section}: unknown flag {gate!r}"


# --- the three states ------------------------------------------------------


def test_inference_never_answers_disabled() -> None:
    """Absence of a section is not evidence, so it may not become `disabled`."""
    manifest = build_manifest(sections_with_rows={"AIM_LOCK"})
    assert manifest["source"] == "sections_observed"
    assert DISABLED not in manifest["capabilities"].values()
    assert manifest["capabilities"]["aim_lock"] == ENABLED
    assert manifest["capabilities"]["shot_fired"] == UNKNOWN


def test_a_present_section_proves_its_flag() -> None:
    manifest = build_manifest(sections_with_rows={"SHOT_FIRED", "COMBAT_POSITIONS"})
    assert manifest["capabilities"]["shot_fired"] == ENABLED
    assert manifest["capabilities"]["combat_positions"] == ENABLED


def test_shared_flag_is_proven_by_either_section() -> None:
    for section in ("CARRIER_EVENTS", "CARRIER_KILLS"):
        manifest = build_manifest(sections_with_rows={section})
        assert manifest["capabilities"]["carrier_tracking"] == ENABLED


def test_declaration_can_say_disabled() -> None:
    manifest = build_manifest(
        sections_with_rows=set(),
        declared={"shot_fired": False, "aim_lock": True},
        test_mode=False,
    )
    assert manifest["source"] == "declared"
    assert manifest["capabilities"]["shot_fired"] == DISABLED
    assert manifest["capabilities"]["aim_lock"] == ENABLED
    # A flag the declaration omits is still unknown, not false.
    assert manifest["capabilities"]["spawn_select"] == UNKNOWN


def test_declaration_wins_over_observation() -> None:
    """A declaration is exact; presence is only a lower bound."""
    manifest = build_manifest(
        sections_with_rows={"SHOT_FIRED"},
        declared={"shot_fired": True},
    )
    assert manifest["capabilities"]["shot_fired"] == ENABLED


def test_unknown_flag_from_a_newer_tracker_survives() -> None:
    manifest = build_manifest(sections_with_rows=set(), declared={"time_travel": True})
    assert manifest["capabilities"]["time_travel"] == ENABLED


def test_test_mode_is_recorded_separately() -> None:
    """test_mode turns every flag off, and must not read as a disabled capture."""
    manifest = build_manifest(
        sections_with_rows=set(),
        declared=dict.fromkeys(FEATURE_FLAGS, False),
        test_mode=True,
    )
    assert manifest["test_mode"] is True
    assert set(manifest["capabilities"].values()) == {DISABLED}


def test_manifest_without_declaration_leaves_test_mode_unknown() -> None:
    assert build_manifest(sections_with_rows={"ENGAGEMENTS"})["test_mode"] is None


# --- wire format -----------------------------------------------------------


def test_parse_declaration_round_trip() -> None:
    parsed = parse_declaration("shot_fired:1,aim_lock:1,spawn_select:0")
    assert parsed == {"shot_fired": True, "aim_lock": True, "spawn_select": False}


def test_parse_declaration_tolerates_whitespace_and_blanks() -> None:
    assert parse_declaration(" shot_fired:1 , ,aim_lock:0 ") == {
        "shot_fired": True,
        "aim_lock": False,
    }


def test_declaration_carries_no_equals_sign() -> None:
    """The header reader splits on '=', so an '=' in the value would truncate it."""
    value = ",".join(f"{flag}:1" for flag in FEATURE_FLAGS)
    assert "=" not in value


def test_is_declared() -> None:
    assert is_declared(build_manifest(sections_with_rows=set(), declared={}))
    assert not is_declared(build_manifest(sections_with_rows=set()))
    assert not is_declared(None)


# --- the tracker's own declaration -----------------------------------------


def test_lua_declares_every_flag_in_the_same_order() -> None:
    """`cap_order` drives the declaration; a flag missing from it reads as
    `unknown` downstream, which hides the omission instead of surfacing it."""
    source = TRACKER.read_text()
    block = source[source.index("local cap_order = {"):]
    block = block[: block.index("\n    }")]
    assert tuple(re.findall(r'"([a-z_]+)"', block)) == FEATURE_FLAGS


def test_lua_declares_effective_state_not_configuration() -> None:
    """test_mode forces every flag off, so the declaration must report
    isFeatureEnabled(), never config.features[] (see line 338 of the tracker)."""
    source = TRACKER.read_text()
    block = source[source.index("local cap_order = {"):]
    block = block[: block.index("et.trap_FS_Write(cap_header")]
    assert 'isFeatureEnabled(name)' in block
    assert 'config.features[name]' not in block


def test_lua_declaration_uses_the_wire_format_the_parser_reads() -> None:
    """`name:0|1` joined by commas, and no '=' inside the value.

    The header reader takes everything after the first '=', so a separator
    containing '=' would truncate the declaration silently — the round would
    then look like it declared only its first few flags, and the rest would read
    as `unknown` rather than as a bug.
    """
    source = TRACKER.read_text()
    block = source[source.index("local cap_order = {"):]
    block = block[: block.index("et.trap_FS_Write(cap_header")]
    assert 'name .. ":" .. (isFeatureEnabled(name) and "1" or "0")' in block
    assert 'table.concat(cap_parts, ",")' in block


# --- executing the declaration, not just reading it ------------------------

LUA = shutil.which("lua5.4") or shutil.which("lua")

LUA_HARNESS = """
local src = io.open(%r):read('a')
local block = src:match('(local cap_order = {.-et%%.trap_FS_Write%%(cap_header, string%%.len%%(cap_header%%), fd%%))')
assert(block, 'declaration block not found')
local config = { test_mode = { enabled = %s }, features = { %s } }
local function isFeatureEnabled(n)
  if config.test_mode.enabled then return false end
  return config.features[n]
end
local out = {}
local et = { trap_FS_Write = function(s) out[#out+1] = s end }
local chunk = assert(load('local config, isFeatureEnabled, et, version, fd = ... \\n' .. block))
chunk(config, isFeatureEnabled, et, '6.11', 1)
io.write(table.concat(out))
"""


def _run_declaration(test_mode: bool, features: dict[str, bool]) -> str:
    body = ", ".join(
        f"{name}={'true' if value else 'false'}" for name, value in features.items()
    )
    script = LUA_HARNESS % (str(TRACKER), "true" if test_mode else "false", body)
    result = subprocess.run(
        [LUA, "-"], input=script, capture_output=True, text=True, timeout=30, check=True
    )
    return result.stdout


def _header_value(text: str, key: str) -> str:
    for line in text.splitlines():
        if line.startswith(f"# {key}="):
            return line.split("=", 1)[1]
    raise AssertionError(f"no `{key}` line in:\n{text}")


@pytest.mark.skipif(not LUA, reason="no lua interpreter on this host")
def test_declaration_reports_what_the_flags_actually_are() -> None:
    """Runs the tracker's own declaration block under a real interpreter.

    Reading the source proves the code says the right thing; running it proves
    the code DOES the right thing, and those are different claims.
    """
    features = dict.fromkeys(FEATURE_FLAGS, True)
    features["shot_fired"] = False
    text = _run_declaration(test_mode=False, features=features)

    assert _header_value(text, "tracker_version_full") == "6.11"
    assert _header_value(text, "test_mode") == "0"
    declared = parse_declaration(_header_value(text, "capabilities"))
    assert declared["shot_fired"] is False
    assert declared["aim_lock"] is True
    assert set(declared) == set(FEATURE_FLAGS)


@pytest.mark.skipif(not LUA, reason="no lua interpreter on this host")
def test_test_mode_declares_every_flag_off_and_says_so() -> None:
    """⚠️ The trap this line exists for.

    `isFeatureEnabled` returns false for everything while test mode is on, so a
    test-mode round writes almost nothing and is indistinguishable from a
    server with the capture switched off — unless the file says which it was.
    """
    text = _run_declaration(test_mode=True, features=dict.fromkeys(FEATURE_FLAGS, True))
    assert _header_value(text, "test_mode") == "1"
    declared = parse_declaration(_header_value(text, "capabilities"))
    assert set(declared.values()) == {False}


@pytest.mark.skipif(not LUA, reason="no lua interpreter on this host")
def test_a_flag_missing_from_cap_order_is_still_declared() -> None:
    """A flag added to config.features but not to cap_order would otherwise
    vanish from the declaration, and a missing name reads downstream as
    `unknown` — hiding the omission instead of surfacing it."""
    features = dict.fromkeys(FEATURE_FLAGS, True)
    features["a_brand_new_capture"] = True
    text = _run_declaration(test_mode=False, features=features)
    declared = parse_declaration(_header_value(text, "capabilities"))
    assert declared["a_brand_new_capture"] is True


@pytest.mark.skipif(not LUA, reason="no lua interpreter on this host")
def test_declaration_is_byte_stable_across_rounds() -> None:
    """`pairs()` has no defined order, so an unsorted extras list would make the
    same server write a different line every round."""
    features = dict.fromkeys(FEATURE_FLAGS, True)
    features.update({"zzz_late": True, "aaa_early": False})
    runs = {_run_declaration(test_mode=False, features=features) for _ in range(3)}
    assert len(runs) == 1


@pytest.mark.skipif(not LUA, reason="no lua interpreter on this host")
def test_what_lua_writes_is_what_the_parser_reads() -> None:
    """The round trip, end to end, with no hand-written fixture in between."""
    features = dict.fromkeys(FEATURE_FLAGS, True)
    features["comm_events"] = False
    text = _run_declaration(test_mode=False, features=features)

    manifest = build_manifest(
        sections_with_rows=set(),
        declared=parse_declaration(_header_value(text, "capabilities")),
        test_mode=_header_value(text, "test_mode") == "1",
        tracker_version_full=_header_value(text, "tracker_version_full"),
    )
    assert manifest["source"] == "declared"
    assert manifest["capabilities"]["comm_events"] == DISABLED
    assert manifest["capabilities"]["shot_fired"] == ENABLED
    assert UNKNOWN not in manifest["capabilities"].values()
