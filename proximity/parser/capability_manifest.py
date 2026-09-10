"""Per-round capability manifest: what the tracker was even ABLE to record.

The rating and the spider web both have to answer a question the raw tables
cannot: when a round shows no gunfire, was there no gunfire, or was the gunfire
capture switched off? Those two look identical in `proximity_shot_fired` — the
table is simply empty — and treating the second as the first invents a fact.
Round 11277 (supply R1, 2026-08-20) is the live example: zero shot rows, 297
aim-lock rows, and the only honest answer about its gunfire is "unknown".

`proximity_processed_files.capabilities` (migration 062) has existed since the
column was added and has been NULL in all 828 rows. This module fills it.

⭐ THE RULE THE WHOLE MANIFEST STANDS ON

Every gated section in the tracker is written as

    if isFeatureEnabled("shot_fired") and #tracker.shot_fired > 0 then

so a section that IS present proves its flag was on, while a section that is
ABSENT proves nothing at all — flag off and flag on with nothing to report
produce byte-identical files. The manifest therefore carries THREE states and
never two: a historical round whose capability cannot be proven is `unknown`,
not `disabled`. Writing `disabled` there would be a lie dressed as caution.

Newer trackers declare their flags outright in the file header, which removes
the ambiguity going forward; `source` says which of the two we had.

⚠️ `isFeatureEnabled` returns false for EVERY flag while `config.test_mode` is
on, so a test-mode round writes almost nothing and looks exactly like a server
with the capture disabled. The declaration records the effective value and
`test_mode` separately, so the reader can tell those apart.
"""

from __future__ import annotations

import re

MANIFEST_VERSION = 1

#: A section header is `# NAME` and nothing else. Column-description lines
#: (`# guid;name;...`) and the version banner do not qualify as sections we
#: track rows for.
#:
#: ⚠️ Recognising a header we do NOT know is as important as recognising one we
#: do: without it, the rows of an unfamiliar section are attributed to whichever
#: section came before, which would report that section's capability as
#: `enabled` on someone else's data (CodeRabbit, PR #795).
SECTION_HEADER_RE = re.compile(r"^# ([A-Z][A-Z0-9_]*)$")

ENABLED = "enabled"
DISABLED = "disabled"
UNKNOWN = "unknown"

#: Every feature flag in the tracker's `config.features` table.
FEATURE_FLAGS: tuple[str, ...] = (
    "engagement_tracking",
    "crossfire_detection",
    "escape_detection",
    "heatmap_generation",
    "reaction_tracking",
    "spawn_timing",
    "team_cohesion",
    "crossfire_opportunities",
    "focus_fire",
    "team_push_detection",
    "trade_kills",
    "kill_outcome_tracking",
    "hit_region_tracking",
    "combat_positions",
    "carrier_tracking",
    "carrier_returns",
    "vehicle_tracking",
    "construction_tracking",
    "objective_run_tracking",
    "shot_fired",
    "aim_lock",
    "spawn_select",
    "skill_snapshot",
    "comm_events",
)

#: Section name in the raw file -> the feature flag that gates the data reaching
#: it, or None where nothing gates it.
#:
#: ⚠️ DERIVED FROM THE TRACKER, NOT FROM THE NAMES. Several entries do not match
#: what the name suggests and a hand-guessed table would be confidently wrong:
#:
#:   * REVIVES and WEAPON_ACCURACY are gated by NOTHING — neither their output
#:     nor their collection consults a flag — so an empty section there is a
#:     true zero, not missing telemetry.
#:   * KILL_OUTCOME's output checks only the row count, but `kill_outcome_
#:     tracking` gates the collection that fills it, so the flag still decides.
#:   * ENGAGEMENTS, PLAYER_TRACKS and both heatmaps write their header
#:     unconditionally; only their ROWS carry evidence about the flag.
#:   * CARRIER_EVENTS and CARRIER_KILLS share one flag; VEHICLE_PROGRESS and
#:     ESCORT_CREDIT share another.
#:
#: `tests/unit/test_capability_manifest.py` re-derives this from the Lua source
#: and fails if the two ever drift apart.
SECTION_GATES: dict[str, str | None] = {
    "ENGAGEMENTS": "engagement_tracking",
    "PLAYER_TRACKS": None,
    "KILL_HEATMAP": "heatmap_generation",
    "MOVEMENT_HEATMAP": "heatmap_generation",
    "OBJECTIVE_FOCUS": None,
    "REACTION_METRICS": "reaction_tracking",
    "SPAWN_TIMING": "spawn_timing",
    "TEAM_COHESION": "team_cohesion",
    "CROSSFIRE_OPPORTUNITIES": "crossfire_opportunities",
    "FOCUS_FIRE": "focus_fire",
    "TEAM_PUSHES": "team_push_detection",
    "TRADE_KILLS": "trade_kills",
    "REVIVES": None,
    "WEAPON_ACCURACY": None,
    "KILL_OUTCOME": "kill_outcome_tracking",
    "HIT_REGIONS": "hit_region_tracking",
    "COMBAT_POSITIONS": "combat_positions",
    "SHOT_FIRED": "shot_fired",
    "AIM_LOCK": "aim_lock",
    "SPAWN_SELECT": "spawn_select",
    "SKILL_SNAPSHOT": "skill_snapshot",
    "COMM_EVENTS": "comm_events",
    "CARRIER_EVENTS": "carrier_tracking",
    "CARRIER_KILLS": "carrier_tracking",
    "CARRIER_RETURNS": "carrier_returns",
    "VEHICLE_PROGRESS": "vehicle_tracking",
    "ESCORT_CREDIT": "vehicle_tracking",
    "VEHICLE_DESTROYED": "vehicle_tracking",
    "CONSTRUCTION_EVENTS": "construction_tracking",
    "OBJECTIVE_RUNS": "objective_run_tracking",
}

#: Flags that gate behaviour but own no section of their own, so no observation
#: of the file can ever prove them. They are `unknown` unless declared.
UNOBSERVABLE_FLAGS: frozenset[str] = frozenset(
    FEATURE_FLAGS
) - frozenset(gate for gate in SECTION_GATES.values() if gate)


def parse_declaration(raw: str) -> dict[str, bool]:
    """Read a `capabilities=` header value into effective flag states.

    The wire format is `name:0|1` joined by commas. It deliberately avoids `=`
    because the header reader splits on the first one (`line.split('=')[1]`),
    so an `=` inside the value would truncate it.

    Unknown names are kept: a tracker newer than this parser must not have its
    declaration silently narrowed to the flags we happen to know about.
    """
    states: dict[str, bool] = {}
    for part in raw.split(","):
        name, _, value = part.strip().partition(":")
        name = name.strip()
        if not name:
            continue
        states[name] = value.strip() == "1"
    return states


def build_manifest(
    *,
    sections_with_rows: set[str] | frozenset[str],
    declared: dict[str, bool] | None = None,
    test_mode: bool | None = None,
    tracker_version_full: str | None = None,
    position_sample_interval_ms: int | None = None,
) -> dict:
    """Build the manifest stored in `proximity_processed_files.capabilities`.

    `sections_with_rows` must be the sections that carried at least one DATA
    row, not merely a header. Four sections write their header unconditionally,
    so header presence alone would "prove" flags that may well have been off.

    With a declaration the answer is exact. Without one — every file written
    before this contract existed — only presence is evidence, and the result is
    `enabled` or `unknown`. Never `disabled`: see the module docstring.
    """
    observed = {
        gate
        for section, gate in SECTION_GATES.items()
        if gate and section in sections_with_rows
    }

    capabilities: dict[str, str] = {}
    for flag in FEATURE_FLAGS:
        if declared is not None and flag in declared:
            capabilities[flag] = ENABLED if declared[flag] else DISABLED
        elif flag in observed:
            capabilities[flag] = ENABLED
        else:
            capabilities[flag] = UNKNOWN

    # A declaration from a newer tracker may name flags this parser predates.
    for flag, value in (declared or {}).items():
        capabilities.setdefault(flag, ENABLED if value else DISABLED)

    return {
        "manifest_version": MANIFEST_VERSION,
        "source": "declared" if declared is not None else "sections_observed",
        "capabilities": capabilities,
        "sections_with_rows": sorted(sections_with_rows),
        "position_sample_interval_ms": position_sample_interval_ms,
        "tracker_version_full": tracker_version_full,
        "test_mode": test_mode,
    }


def is_declared(manifest: dict | None) -> bool:
    """True when the manifest came from the tracker's own declaration.

    Used to keep a re-import of an old file from downgrading a manifest that a
    newer tracker already stated exactly.
    """
    return bool(manifest) and manifest.get("source") == "declared"


def scan_file(path: str) -> dict:
    """Everything the manifest needs, read straight off a raw file.

    The parser gathers the same facts as a side effect of its full parse. This
    reads them alone, for the backfill, which has no reason to build 800 rounds
    of engagements just to learn which sections had rows.

    ⚠️ Two ways of computing one answer is how they drift apart, so
    `test_scan_file_agrees_with_the_parser` runs both over real files and fails
    if they ever disagree.
    """
    declared: dict[str, bool] | None = None
    test_mode: bool | None = None
    version_full: str | None = None
    interval: int | None = None
    sections_with_rows: set[str] = set()
    current = ""

    with open(path, encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                if line.startswith("# capabilities="):
                    declared = parse_declaration(line.split("=", 1)[1])
                elif line.startswith("# test_mode="):
                    test_mode = line.split("=", 1)[1] == "1"
                elif line.startswith("# tracker_version_full="):
                    version_full = line.split("=", 1)[1]
                elif line.startswith("# position_sample_interval="):
                    try:
                        interval = int(line.split("=", 1)[1])
                    except ValueError:
                        interval = None
                else:
                    header = SECTION_HEADER_RE.match(line)
                    if header:
                        name = header.group(1)
                        # An unknown section clears the label rather than
                        # leaving the previous one in place.
                        current = name if name in SECTION_GATES else ""
                continue
            if current:
                sections_with_rows.add(current)

    return {
        "declared": declared,
        "test_mode": test_mode,
        "tracker_version_full": version_full,
        "position_sample_interval_ms": interval,
        "sections_with_rows": sections_with_rows,
    }
