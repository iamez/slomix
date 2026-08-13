"""story_invariants.py — declarative data-trust invariants for Smart Stats.

Every Smart Stats "weird number" the owner has caught (bot rows in Advanced
Metrics, blank bars, a header reading 61 kills for a 507-kill session, a KIS
modal taller than the viewport) shared one root: no automated contract tied
the DISPLAYED number back to the DATABASE, and each of ~17 panels was hand-built
with its own scope and source, so their numbers silently disagreed.

This module encodes that missing contract as METAMORPHIC / CONSERVATION / BOUNDS
invariants — relations that must hold regardless of which session is scored, so
no golden "expected output" is needed (the Adobe-Analytics metamorphic-testing
approach). Each invariant is a small pure function over a SessionContext that a
runner fills in two ways:

  * tests/contract/test_story_data_invariants.py — seeds a fixture session and
    calls the endpoints in-process (CI gate), and
  * scripts/data_trust_check.py — points at a real live session + DB (on-demand
    "Data Trust report").

Keeping the invariants here — dependency-free (stdlib only) — lets both runners
share the exact same relations. Every invariant's docstring names the past bug
it locks down, so this file doubles as a regression ledger.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ── Context the runners populate ──────────────────────────────────────────────

@dataclass
class GroundTruth:
    """Authoritative values read straight from the database for one session.

    None means "the runner could not/did not compute this" — invariants that
    depend on it then SKIP rather than fail, so a partial context never invents
    a violation.
    """

    total_kills: int | None = None          # gated SUM(pcs.kills), non-bot
    roster_guids: set[str] = field(default_factory=set)  # 8-char UPPER, non-bot


@dataclass
class SessionContext:
    """Everything an invariant needs about one scored session.

    panels maps a stable panel key ("kill_impact", "composite", …) to that
    endpoint's parsed JSON (or None if the fetch failed / was skipped). truth
    holds the DB ground truth. Invariants read only from here.
    """

    gaming_session_id: int
    panels: dict[str, Any] = field(default_factory=dict)
    truth: GroundTruth = field(default_factory=GroundTruth)


# ── Helpers ───────────────────────────────────────────────────────────────────

# A panel's player rows live under one of these keys depending on the endpoint.
_PLAYER_LIST_KEYS = ("players", "entries", "contributions", "leaderboard")

# Fields that count things — a negative value is impossible and signals a bug.
_COUNT_FIELDS = frozenset({
    "kills", "carrier_kills", "push_kills", "total_kills", "deaths",
    "rounds_won", "rounds_lost", "total_rounds", "revives",
})


def _players(panel: Any) -> list[dict]:
    """Extract the list of player rows from a panel response, shape-tolerant."""
    if not isinstance(panel, dict):
        return []
    for key in _PLAYER_LIST_KEYS:
        rows = panel.get(key)
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
    return []


def _guid(row: dict) -> str:
    return str(row.get("guid") or row.get("player_guid") or "")


def _name(row: dict) -> str:
    return str(row.get("name") or row.get("player_name") or "")


def _norm_guid(guid: str) -> str:
    """Normalise to the 8-char UPPER key the DB groups by.

    Panels disagree on GUID width — kill-impact carries the 32-char proximity
    GUID, composite/win-contribution the 8-char stats GUID — so comparisons
    across panels and against the DB roster must normalise first.
    """
    return guid.upper()[:8]


def _is_bot(row: dict) -> bool:
    """A row is a bot iff its GUID is an OMNIBOT id or its name carries [BOT].

    Mirrors the exact filter the endpoints use (UPPER(guid) LIKE 'OMNIBOT%' +
    name LIKE '%[BOT]%'); both are checked because either alone has leaked
    before (guid-only missed colour-coded [BOT] names; name-only missed bots
    whose display name was clean).
    """
    return _guid(row).upper().startswith("OMNIBOT") or "[BOT]" in _name(row)


def _numeric_fields(row: dict):
    """Yield (field, value) for real JSON numbers only (bool is not a number)."""
    for f, v in row.items():
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            yield f, v


# ── Invariant registry ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Invariant:
    key: str
    category: str          # conservation | exclusion | scope | cross_panel | bounds
    description: str       # the past bug this locks down
    check: Callable[[SessionContext], list[str]]  # -> violation messages ([] = pass)


def _inv_conservation_total_kills(ctx: SessionContext) -> list[str]:
    """kill-impact header 'Kills' == SUM(pcs.kills) for the session.

    Locks down the hero-KILLS bug (#709): the header summed the per-player KIS
    row 'kills' (only the proximity-tracked subset that carries an impact score)
    and read 61 for a 507-kill session. The header must equal the real session
    total, gated by the same round-validity filter the scope uses.
    """
    ki = ctx.panels.get("kill_impact")
    if not isinstance(ki, dict) or ctx.truth.total_kills is None:
        return []
    got = ki.get("total_kills")
    if got != ctx.truth.total_kills:
        return [f"kill-impact.total_kills={got} != SUM(pcs.kills)={ctx.truth.total_kills}"]
    return []


def _inv_exclusion_no_bots(ctx: SessionContext) -> list[str]:
    """No OMNIBOT / [BOT] row in ANY panel.

    Locks down the bot-leakage class (Advanced Metrics, Record Book): a panel
    that forgot the bot filter listed OMNIBOT/[BOT] as if a player.
    """
    return [
        f"{key}: bot leaked (guid={_guid(row)[:12]!r} name={_name(row)!r})"
        for key, panel in ctx.panels.items()
        for row in _players(panel)
        if _is_bot(row)
    ]


def _inv_scope_roster_subset(ctx: SessionContext) -> list[str]:
    """Every panel player belongs to the session's DB roster (gsid ⊆ roster).

    Locks down the date-scope leak: a date-scoped panel merged players from
    OTHER same-day gaming sessions, so a face the session never saw appeared in
    the leaderboard. Every GUID a panel shows must be one the DB roster (this
    gsid, gated, non-bot) actually contains.
    """
    roster = ctx.truth.roster_guids
    if not roster:
        return []
    viol: list[str] = []
    for key, panel in ctx.panels.items():
        for row in _players(panel):
            if _is_bot(row):
                continue  # bot leakage is its own invariant
            g = _norm_guid(_guid(row))
            if g and g not in roster:
                viol.append(f"{key}: player {g} ({_name(row)!r}) not in session roster")
    return viol


def _inv_cross_panel_tracked_le_total(ctx: SessionContext) -> list[str]:
    """Sum of per-player KIS-tracked kills ≤ session total kills (tracked ⊆ total).

    Locks down the inverse of the hero-KILLS bug: the impact-scored subset can
    never exceed the real total. If it did, the 'total' would be an undercount
    (the exact 61-vs-507 failure, seen from the other direction).
    """
    ki = ctx.panels.get("kill_impact")
    if not isinstance(ki, dict):
        return []
    total = ki.get("total_kills")
    if not isinstance(total, (int, float)):
        return []
    tracked = sum(int(r.get("kills", 0) or 0) for r in _players(ki))
    if tracked > total:
        return [f"kill-impact tracked kills {tracked} > total_kills {total}"]
    return []


def _inv_conservation_box_score(ctx: SessionContext) -> list[str]:
    """BOX scoreboard totals equal the sum of their own per-map points.

    Locks BOX internal consistency: calculate_session_score adds every map's
    points into alpha_score/beta_score and appends every map, so the header must
    equal the sum of the maps it is built from. A totaling drift (a map's points
    dropped from or double-counted in the total) would desync the scoreboard
    header from its own map breakdown — the same 'header disagrees with its
    parts' family as the hero-KILLS bug, one panel over.
    """
    box = ctx.panels.get("box_score")
    if not isinstance(box, dict):
        return []
    maps = box.get("maps")
    if not isinstance(maps, list) or not maps:
        return []
    viol: list[str] = []
    for side, total_key in (("alpha_points", "alpha_score"), ("beta_points", "beta_score")):
        total = box.get(total_key)
        # The real endpoint always returns numeric totals (default 0), so with
        # maps present a missing/non-numeric total is a malformed payload — flag
        # it rather than skipping (Copilot #716), or the check passes vacuously.
        if not isinstance(total, (int, float)) or isinstance(total, bool):
            viol.append(f"box-score {total_key} missing or non-numeric ({total!r}) with {len(maps)} maps")
            continue
        summed = sum(int(m.get(side, 0) or 0) for m in maps if isinstance(m, dict))
        if summed != total:
            viol.append(f"box-score {total_key}={total} != sum of per-map {side}={summed}")
    return viol


def _inv_bounds_finite_nonneg(ctx: SessionContext) -> list[str]:
    """No NaN/Infinity anywhere; count fields are never negative (dbt-style bounds).

    Locks down the 'NaN'/'undefined'/'-1' render class: a divide-by-zero or a
    differential gone wrong produced a non-finite or negative number that the
    frontend rendered verbatim into a stat card.
    """
    viol: list[str] = []
    for key, panel in ctx.panels.items():
        for row in _players(panel):
            label = _name(row) or _guid(row)[:8]
            for f, v in _numeric_fields(row):
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    viol.append(f"{key}.{f} for {label!r} is non-finite ({v})")
                elif f in _COUNT_FIELDS and v < 0:
                    viol.append(f"{key}.{f} for {label!r} is negative ({v})")
    return viol


# The ledger. Order = report order (conservation first — the loudest failures).
INVARIANTS: list[Invariant] = [
    Invariant(
        "conservation_total_kills", "conservation",
        "kill-impact header Kills == SUM(pcs.kills) (hero-KILLS #709)",
        _inv_conservation_total_kills,
    ),
    Invariant(
        "exclusion_no_bots", "exclusion",
        "no OMNIBOT/[BOT] row in any panel (bot-leakage)",
        _inv_exclusion_no_bots,
    ),
    Invariant(
        "scope_roster_subset", "scope",
        "every panel player is in the session DB roster (date-scope leak)",
        _inv_scope_roster_subset,
    ),
    Invariant(
        "cross_panel_tracked_le_total", "cross_panel",
        "KIS-tracked kills <= total kills (tracked subset of total)",
        _inv_cross_panel_tracked_le_total,
    ),
    Invariant(
        "conservation_box_score", "conservation",
        "BOX totals == sum of per-map points (scoreboard vs its breakdown)",
        _inv_conservation_box_score,
    ),
    Invariant(
        "bounds_finite_nonneg", "bounds",
        "no NaN/Inf anywhere; counts never negative (dbt-style bounds)",
        _inv_bounds_finite_nonneg,
    ),
]


@dataclass
class InvariantResult:
    invariant: Invariant
    violations: list[str]

    @property
    def passed(self) -> bool:
        return not self.violations


def evaluate(ctx: SessionContext) -> list[InvariantResult]:
    """Run every invariant against a context; return one result each, in order."""
    return [InvariantResult(inv, inv.check(ctx)) for inv in INVARIANTS]
