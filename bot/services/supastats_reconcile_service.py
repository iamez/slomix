"""Compare a parsed supastats sheet against our own database.

The sheet is an independent measurement of the same night, so every number that
disagrees is either a bug in our pipeline or a bug in the reader — and the point
of this service is to say which, loudly, the morning it happens rather than
months later. It reports, never writes.

Tolerances are empirical, measured on session 144 (2026-08-11) against the
sheet:

* kills — EXACT. All 42 per-map values matched, so any difference is real.
* round durations — EXACT (5:40 = 340s, 12:00 = 720s ...).
* map winners — EXACT.
* DPM — +/- DPM_TOLERANCE. Ours ran 1-4 below the sheet's, consistently: the
  same damage over a slightly different time base, not a data error.

EFFORT is supastats' own metric with no counterpart here; it is ignored.
"""

from __future__ import annotations

import difflib
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from bot.core.utils import normalize_player_name
from bot.services.supastats_image_reader import ParsedSheet

logger = logging.getLogger(__name__)

DPM_TOLERANCE = 5           # per-map DPM difference we accept without reporting
NAME_MATCH_CUTOFF = 0.6     # difflib ratio below which we refuse to link names


@dataclass
class ReconcileReport:
    session_date: str | None = None
    gaming_session_id: int | None = None
    notes: list[str] = field(default_factory=list)       # progress / context
    mismatches: list[str] = field(default_factory=list)  # real disagreements
    unmatched: list[str] = field(default_factory=list)   # could not be compared

    @property
    def ok(self) -> bool:
        return not self.mismatches

    def summary(self) -> str:
        if self.mismatches:
            return f"{len(self.mismatches)} discrepancies"
        if self.unmatched:
            return f"everything comparable matches ({len(self.unmatched)} not compared)"
        return "everything matches"


def _canonical(name: str | None) -> str:
    """Strip ET colour codes, case and punctuation for name comparison."""
    return re.sub(r"[^a-z0-9]", "", normalize_player_name(name or "").lower())


def _link_players(sheet_rows, our_players: dict[str, list[int]]):
    """Map sheet rows to our player names.

    Names alone are unreliable (the sheet shows "carni laptop" for the player
    our data calls "ownator", and "squaze" for "SQUUAZE"), so the kill vector —
    which is close to unique per player over a night — decides, and the name is
    used to break ties. A row that cannot be linked confidently is reported as
    "not compared" rather than guessed at.
    """
    remaining = dict(our_players)
    links: list[tuple[int, str | None]] = []
    for index, row in enumerate(sheet_rows):
        best_name, best_cost = None, None
        for name, ours in remaining.items():
            if len(ours) != len(row.values):
                continue
            cost = sum(
                abs((a or 0) - b) for a, b in zip(row.values, ours)
            )
            # Prefer an exact kill-vector match; fall back to the closest.
            if best_cost is None or cost < best_cost:
                best_name, best_cost = name, cost
        if best_name is not None and best_cost is not None and best_cost <= 3:
            links.append((index, best_name))
            remaining.pop(best_name, None)
            continue
        # No convincing numeric link — try the name if the sheet gave us one.
        if row.name:
            match = difflib.get_close_matches(
                _canonical(row.name), [_canonical(n) for n in remaining], n=1,
                cutoff=NAME_MATCH_CUTOFF,
            )
            if match:
                for name in list(remaining):
                    if _canonical(name) == match[0]:
                        links.append((index, name))
                        remaining.pop(name)
                        break
                else:
                    links.append((index, None))
                continue
        links.append((index, None))
    return links


def reconcile(
    sheet: ParsedSheet,
    *,
    session_date: str,
    gaming_session_id: int | None,
    our_kills: dict[str, list[int]],
    our_dpm: dict[str, list[int]],
    our_durations: tuple[list[int], list[int]],
    our_map_winners: list[str],
    our_teams: dict[str, list[str]],
) -> ReconcileReport:
    """Compare one parsed sheet with the numbers we hold for that session.

    All "our" inputs are per-map lists in play order, keyed by player name, so
    this stays a pure function that unit tests can drive without a database.
    ``our_map_winners`` holds our team NAME per map; the sheet only knows RED
    and BLUE, so the colours are bound to our teams through the players whose
    rows we managed to link.
    """
    report = ReconcileReport(session_date=session_date, gaming_session_id=gaming_session_id)

    if not sheet.kills_checksum_ok:
        report.unmatched.append(
            "sheet kills failed their own checksum — the screenshot was not read "
            "reliably, so no numbers were compared"
        )
        return report

    our_map_count = len(next(iter(our_kills.values()), []))
    if sheet.map_count != our_map_count:
        report.mismatches.append(
            f"map count: supastats {sheet.map_count}, we have {our_map_count}"
        )
        return report
    report.notes.append(f"{sheet.map_count} maps on both sides")

    # --- players -----------------------------------------------------------
    links = _link_players(sheet.kills, our_kills)
    linked = {i: name for i, name in links if name}
    report.unmatched.extend(
        f"sheet row {index + 1} ({sheet.kills[index].team}) could not be "
        "linked to one of our players"
        for index, name in links if not name
    )
    if linked:
        report.notes.append(f"{len(linked)}/{len(sheet.kills)} players linked")

    for index, name in linked.items():
        row = sheet.kills[index]
        for map_index, (theirs, ours) in enumerate(zip(row.values, our_kills[name]), start=1):
            if theirs is not None and theirs != ours:
                report.mismatches.append(
                    f"kills — {name}, map {map_index}: supastats {theirs}, we have {ours}"
                )

    # The DPM block is only row-aligned with the kills block when both hold the
    # same players in the same order; comparing across a size mismatch would
    # attribute one player's DPM to another and invent mismatches.
    dpm_aligned = len(sheet.dpm) == len(sheet.kills) and all(
        d.team == k.team for d, k in zip(sheet.dpm, sheet.kills)
    )
    if sheet.dpm and not dpm_aligned:
        report.unmatched.append("DPM block does not line up with the kills block — DPM not compared")
    dpm_rows = dict(enumerate(sheet.dpm)) if dpm_aligned else {}
    for index, name in linked.items():
        row = dpm_rows.get(index)
        if row is None or name not in our_dpm:
            continue
        for map_index, (theirs, ours) in enumerate(zip(row.values, our_dpm[name]), start=1):
            if theirs is None:
                continue
            if abs(theirs - ours) > DPM_TOLERANCE:
                report.mismatches.append(
                    f"DPM — {name}, map {map_index}: supastats {theirs}, we have {ours}"
                )

    # --- map winners -------------------------------------------------------
    # Bind RED/BLUE to our team names via the linked players' team membership.
    colour_to_team: dict[str, str] = {}
    for index, name in linked.items():
        colour = sheet.kills[index].team
        for team_name, members in our_teams.items():
            if name in members:
                colour_to_team.setdefault(colour, team_name)
    if len(colour_to_team) == 2:
        report.notes.append(
            "teams: " + ", ".join(f"{c} = {t}" for c, t in sorted(colour_to_team.items()))
        )
        for map_index, (colour, ours) in enumerate(zip(sheet.winners, our_map_winners), start=1):
            theirs = colour_to_team.get(colour) if colour else None
            if theirs and ours and theirs != ours:
                report.mismatches.append(
                    f"map {map_index} winner: supastats {theirs} ({colour}), we have {ours}"
                )
    else:
        report.unmatched.append("could not bind the sheet's RED/BLUE to our teams")

    # --- round durations ---------------------------------------------------
    our_r1, our_r2 = our_durations
    for label, theirs_list, ours_list in (
        ("R1", sheet.round1_seconds, our_r1),
        ("R2", sheet.round2_seconds, our_r2),
    ):
        if not theirs_list:
            continue
        for map_index, (theirs, ours) in enumerate(zip(theirs_list, ours_list), start=1):
            if theirs is None or ours is None:
                continue
            if theirs != ours:
                report.mismatches.append(
                    f"{label} duration — map {map_index}: supastats {theirs}s, we have {ours}s"
                )
        report.notes.append(f"{label} durations compared")

    return report


def format_report(report: ReconcileReport, sheet: ParsedSheet | None = None) -> str:
    """Render a report for Discord/CLI: the process, then the verdict."""
    lines = [f"**supastats check — {report.session_date or 'unknown date'}**"]
    if report.gaming_session_id:
        lines.append(f"session #{report.gaming_session_id}")
    if sheet is not None:
        lines.append(
            f"read: {sheet.map_count} maps, {len(sheet.kills)} players"
            + (", round durations present" if sheet.round1_seconds else "")
        )
    lines.extend(f"• {note}" for note in report.notes)
    if report.mismatches:
        lines.append("")
        lines.append(f"🔴 **{len(report.mismatches)} discrepancies**")
        lines.extend(f"  - {m}" for m in report.mismatches[:25])
        if len(report.mismatches) > 25:
            lines.append(f"  … and {len(report.mismatches) - 25} more")
    else:
        lines.append("")
        lines.append("✅ everything comparable matches")
    if report.unmatched:
        lines.append("")
        lines.append("⚠️ not compared:")
        lines.extend(f"  - {u}" for u in report.unmatched[:10])
    return "\n".join(lines)


# --- database side ----------------------------------------------------------

# Order maps by the COMBINED timestamp, never by MIN(date) and MIN(time)
# separately: a match that crosses midnight has its R1 on one date and its R2
# on the next, so the two minima come from different rounds and the map sorts
# to the wrong place (session 143's 23:57 escape jumped to first because its
# R2 started 00:01). Concatenating keeps one chronological key per match.
_MAP_ORDER_SQL = """
    SELECT match_id,
           ROW_NUMBER() OVER (ORDER BY MIN(round_date || round_time)) AS map_no,
           MIN(map_name) AS map_name
    FROM rounds
    WHERE gaming_session_id = ? AND round_number IN (1, 2) AND is_valid
    GROUP BY match_id
"""


async def load_our_session(db_adapter, gaming_session_id: int) -> dict[str, Any]:
    """Per-map kills, DPM and round durations for one gaming session.

    Maps are numbered by first-round time so the order matches the sheet's
    left-to-right columns. Durations prefer ``actual_duration_seconds``
    (measured; verified 100% against demo times, RCA 2026-08-18) and fall
    back to the ``actual_time`` header text only where the Lua measurement
    is missing — the header value is the stopwatch TARGET and is inflated
    on surrender rounds, which made this reconciler lie on R2.
    """
    rows = await db_adapter.fetch_all(
        f"""
        WITH mapno AS ({_MAP_ORDER_SQL})
        SELECT mn.map_no, p.player_guid, MAX(p.player_name) AS player_name,
               SUM(p.kills) AS kills,
               SUM(p.deaths) AS deaths,
               SUM(p.damage_given) AS damage,
               SUM(p.time_played_seconds) AS seconds
        FROM rounds r
        JOIN mapno mn ON mn.match_id = r.match_id
        JOIN player_comprehensive_stats p ON p.round_id = r.id
        WHERE r.gaming_session_id = ? AND r.round_number IN (1, 2) AND r.is_valid
        -- Group by GUID, never by name (project rule): a rename mid-session
        -- would otherwise split one player into two half kill-vectors, and
        -- _link_players would report both as unlinkable.
        GROUP BY mn.map_no, p.player_guid
        ORDER BY mn.map_no
        """,  # nosec B608 - _MAP_ORDER_SQL is a module constant, parameters are bound
        (gaming_session_id, gaming_session_id),
    )

    # Aggregate per GUID first: MAX(player_name) is per (map_no, guid), so a
    # mid-session rename would otherwise split one player into two partial
    # vectors keyed by two names (coderabbit, PR #771 — our own GROUP BY
    # GUID rule). A single display name per guid is resolved afterwards.
    per_guid: dict[str, dict[str, Any]] = {}
    for map_no, guid, name, k, d, damage, seconds in rows or []:
        entry = per_guid.setdefault(
            guid, {"names": [], "kills": {}, "deaths": {}, "dpm": {}}
        )
        if name:
            entry["names"].append(str(name))
        entry["kills"][int(map_no)] = int(k or 0)
        entry["deaths"][int(map_no)] = int(d or 0)
        per_minute = (float(damage or 0) * 60.0 / float(seconds)) if seconds else 0.0
        entry["dpm"][int(map_no)] = int(round(per_minute))

    kills: dict[str, dict[int, int]] = {}
    deaths: dict[str, dict[int, int]] = {}
    dpm: dict[str, dict[int, int]] = {}
    for guid, entry in per_guid.items():
        display = max(entry["names"], key=len) if entry["names"] else guid[:8]
        if display in kills:
            # Two guids sharing a display name would merge — disambiguate.
            display = f"{display} [{guid[:4]}]"
        kills[display] = entry["kills"]
        deaths[display] = entry["deaths"]
        dpm[display] = entry["dpm"]

    duration_rows = await db_adapter.fetch_all(
        f"""
        WITH mapno AS ({_MAP_ORDER_SQL})
        SELECT mn.map_no, r.round_number, r.actual_time,
               r.actual_duration_seconds
        FROM rounds r JOIN mapno mn ON mn.match_id = r.match_id
        WHERE r.gaming_session_id = ? AND r.round_number IN (1, 2) AND r.is_valid
        ORDER BY mn.map_no, r.round_number
        """,  # nosec B608 - see above
        (gaming_session_id, gaming_session_id),
    )
    r1: dict[int, int | None] = {}
    r2: dict[int, int | None] = {}
    from shared.round_time import round_duration_seconds

    for map_no, round_number, actual, dur_secs in duration_rows or []:
        target = r1 if int(round_number) == 1 else r2
        # round_duration_seconds enforces the full contract (positive
        # measurement first, parsed header text fallback) — an ad-hoc
        # truthiness check here accepted negative corrupt measurements.
        secs = round_duration_seconds(dur_secs, actual)
        target[int(map_no)] = secs if secs is not None else _to_seconds(actual)

    # Explicit list build: the conditional expression binds looser than "+",
    # so the terser form evaluated max() on an empty r1 and raised.
    map_numbers: list[int] = [max(v) for v in kills.values() if v]
    if r1:
        map_numbers.append(max(r1))
    if r2:
        map_numbers.append(max(r2))
    map_count = max(map_numbers) if map_numbers else 0
    order = list(range(1, map_count + 1))
    return {
        "kills": {n: [v.get(i, 0) for i in order] for n, v in kills.items()},
        # Ready for the day supa's sheet carries a Deaths block (his workbook
        # already tracks K/A/D) — the comparison side lights up without a
        # schema change here.
        "deaths": {n: [v.get(i, 0) for i in order] for n, v in deaths.items()},
        "dpm": {n: [v.get(i, 0) for i in order] for n, v in dpm.items()},
        "durations": ([r1.get(i) for i in order], [r2.get(i) for i in order]),
        "map_count": map_count,
    }


async def load_our_teams(
    db_adapter, gaming_session_id: int, rosters: dict[str, list[str]]
) -> dict[str, list[str]]:
    """Team name -> player NAMES, resolved from the roster GUIDs of this session.

    The rosters are keyed by the same team names the scorer reports, so the
    binding between "the sheet's RED" and "our Team A" is derived from one
    source. Pairing the scorer's team_a_name with a roster list from a
    different call is how the colours ended up swapped: nothing guarantees the
    two helpers order the teams the same way.
    """
    rows = await db_adapter.fetch_all(
        """
        SELECT DISTINCT p.player_guid, p.player_name
        FROM rounds r JOIN player_comprehensive_stats p ON p.round_id = r.id
        WHERE r.gaming_session_id = ? AND r.round_number IN (1, 2) AND r.is_valid
        """,
        (gaming_session_id,),
    )
    name_by_guid = {str(guid): name for guid, name in rows or []}
    teams: dict[str, list[str]] = {}
    for team_name, guids in (rosters or {}).items():
        names = [name_by_guid[str(g)] for g in guids if str(g) in name_by_guid]
        if names:
            teams[team_name] = names
    return teams


def _to_seconds(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if ":" not in text:
        return None
    try:
        minutes, seconds = text.split(":")
        return int(minutes) * 60 + int(seconds)
    except ValueError:
        return None
