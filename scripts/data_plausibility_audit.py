#!/usr/bin/env python3
"""data_plausibility_audit.py — Data Trust pillar B: permanent implausibility audit.

Hunts for the IMPOSSIBLE, not the merely excellent. Every rule is a physics/
game bound a healthy row cannot break (e.g. more bullets fired than the
weapon's fire rate allows in the time played), an internal-consistency check
between two fields that should agree (e.g. dpm vs damage_given/minutes), or a
hard schema invariant (e.g. headshot_kills <= kills). Rules are generous on
purpose: this is not a "how good was this round" tool, it is a "could this
row have physically happened" tool.

This exists because the all-time accuracy record (2026-08-16, see
docs/research/) stood on a row with bullets_fired=5,523 in a 269s round — 20x
any real fire rate. 7,311 of 9,698 pre-2026 "supastats backfill" rows carry
bullets beyond any fire rate; 2026 live-captured rows carry zero such rows.
That backfill/live split is the entire diagnostic value of this tool: a
violation in backfill data is old, already-known-lossy import noise; the
SAME violation in live data is an active capture bug happening right now.
There is no `data_source` column (yet), so provenance is inferred from
`round_date < 2026-01-01` (the backfill/live cutover date), same as the
accuracy-record fix.

Read-only. Never writes to the database.

Usage:
    python scripts/data_plausibility_audit.py                # markdown, stdout + file
    python scripts/data_plausibility_audit.py --json          # machine-readable, stdout only
    python scripts/data_plausibility_audit.py --top 5         # more offending rows per rule
    python scripts/data_plausibility_audit.py --output PATH   # override report file path

DB connection comes from POSTGRES_* env vars (same names as the bot/.env),
opened READ-ONLY (`SET TRANSACTION READ ONLY`), same convention as
scripts/data_trust_check.py.

Exit code = number of T1 rules with at least one LIVE violation (0 = clean).
This is deliberately a shell-guard-friendly number, not a total violation
count: one rule firing 500 times is still "one broken sensor", not 500.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# The date the backfill import (supastats history) hands off to live capture.
# Every historical row before this date came through the lossy backfill path;
# every row on/after it was captured live by the current pipeline. No
# `data_source` column exists yet — this is the documented proxy used by the
# accuracy-record fix (#755) and repeated here for the same reason.
PROVENANCE_CUTOFF = "2026-01-01"

# First day the orphan-R2 sensor is armed: the whole backlog up to and
# INCLUDING 2026-08-17 was triaged that day (healed from original files or
# stamped round_status='orphan_r2' by
# scripts/repair_inverted_r2_cumulative_rounds.py), so the rule starts at the
# first day whose orphans nobody has hand-checked.
ORPHAN_SENSOR_ARMED_FROM = "2026-08-18"

# ── Env / connection (mirrors scripts/data_trust_check.py) ────────────────────


def _load_dotenv(root: Path) -> None:
    """Best-effort .env loader so POSTGRES_* are present without extra tooling.

    Only sets vars not already in the environment (real env wins).
    """
    env_path = root / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def get_connection():
    """Open a READ-ONLY connection to the PostgreSQL DB using POSTGRES_* env vars."""
    import psycopg2  # imported lazily so --help works without the driver

    _load_dotenv(_REPO_ROOT)
    required = ("POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DATABASE", "POSTGRES_USER", "POSTGRES_PASSWORD")
    missing = [n for n in required if not os.getenv(n)]
    if missing:
        raise SystemExit(f"Missing database env vars: {', '.join(missing)}")

    conn = psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        dbname=os.environ["POSTGRES_DATABASE"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
    conn.set_session(readonly=True, autocommit=True)
    return conn


# ── Rules as data ──────────────────────────────────────────────────────────────

VALID_TIERS = {"T1"}
VALID_SEVERITIES = {"critical", "high", "medium"}
VALID_TABLES = {"player_comprehensive_stats", "rounds"}

# rounds.actual_time is stored as free text "M:SS" (not HH:MM:SS, verified
# against every row in the dev DB on 2026-08-17: 100% match `^[0-9]+:[0-9]{2}$`).
# Guard the regex before the split_part cast so a future malformed value fails
# the *audit rule* (correctly, as "unparseable duration") instead of the query.
_ACTUAL_TIME_LOOKS_VALID = "r.actual_time ~ '^[0-9]+:[0-9]{2}$'"
# PostgreSQL does NOT guarantee left-to-right short-circuit evaluation of AND/OR
# operands, so pairing the regex guard and the cast as separate conjuncts is not
# actually safe — the planner may evaluate the cast first and raise on a
# malformed value. The CASE expression makes the guard part of the expression
# itself: a non-matching actual_time yields NULL instead of a cast error.
_ACTUAL_TIME_SECONDS = (
    "(CASE WHEN r.actual_time ~ '^[0-9]+:[0-9]{2}$' "
    "THEN split_part(r.actual_time, ':', 1)::int * 60 + split_part(r.actual_time, ':', 2)::int "
    "END)"
)


@dataclass(frozen=True)
class Rule:
    name: str  # unique, snake_case
    table: str  # "player_comprehensive_stats" | "rounds"
    tier: str  # "T1" (headroom for a future T2)
    severity: str  # "critical" | "high" | "medium"
    predicate: str  # raw SQL boolean expression, aliased `pcs` / `r`
    note: str
    needs_round_join: bool = False  # pcs rules only: JOIN rounds r ON r.id = pcs.round_id
    extra_cols: tuple[str, ...] = field(default_factory=tuple)  # qualified cols shown in top rows
    order_by: str = ""  # qualified expr to rank "worst offender" first; default = id DESC


# Base gates. Applied to every rule on that table, in addition to the rule's
# own predicate. Kept generous per the audit's mandate: we're excluding rows
# a rule literally cannot evaluate (e.g. tps=0 makes every /tps rate divide
# by zero), not excluding "unusual" rows.
_PCS_BASE_GATE = (
    "pcs.round_number IN (1, 2) AND pcs.time_played_seconds > 0 "
    # Rows from rounds the pipeline itself already excludes (bot/test rounds
    # flagged is_valid = FALSE, orphan R2 cumulatives) are KNOWN exclusions,
    # not plausibility findings — before the 2026-08-18 bot-round backfill
    # they produced most of the audit's live noise (OMNIBOT rows breaking
    # headshot/dpm/revive invariants in test sessions). Same reasoning as
    # _ROUNDS_BASE_GATE below.
    "AND NOT EXISTS (SELECT 1 FROM rounds rr "
    "                WHERE rr.id = pcs.round_id "
    "                  AND (rr.is_valid IS FALSE "
    "                       OR rr.round_status = 'orphan_r2'))"
)
# Rounds-table T1 rules only look at rounds the pipeline itself calls valid —
# a round already flagged is_valid=FALSE or round_status != 'completed' is a
# KNOWN exclusion (filler map, cancelled restart, orphan R2), not a plausibility
# finding. round_number 0 (warmup) is excluded for the same reason PCS rules
# exclude it.
_ROUNDS_BASE_GATE = "r.round_status = 'completed' AND r.is_valid = TRUE AND r.round_number IN (1, 2)"

RULES: list[Rule] = [
    # ── Rates: bound by ET:Legacy weapon/game mechanics, generous on purpose ──
    Rule(
        name="pcs_kills_rate",
        table="player_comprehensive_stats",
        tier="T1",
        severity="critical",
        predicate="pcs.kills > pcs.time_played_seconds / 3.0",
        note="More than 1 kill per 3s sustained for the whole time played — exceeds any realistic engagement cadence.",
        extra_cols=("pcs.kills", "pcs.time_played_seconds"),
        order_by="pcs.kills DESC",
    ),
    Rule(
        name="pcs_deaths_rate",
        table="player_comprehensive_stats",
        tier="T1",
        severity="critical",
        predicate="pcs.deaths > pcs.time_played_seconds / 3.0",
        note="More than 1 death per 3s sustained — exceeds any realistic respawn cadence.",
        extra_cols=("pcs.deaths", "pcs.time_played_seconds"),
        order_by="pcs.deaths DESC",
    ),
    Rule(
        name="pcs_damage_given_rate",
        table="player_comprehensive_stats",
        tier="T1",
        severity="critical",
        predicate="pcs.damage_given > pcs.time_played_seconds * 100",
        note="More than 100 damage/second given sustained — beyond any weapon's max DPS.",
        extra_cols=("pcs.damage_given", "pcs.time_played_seconds"),
        order_by="pcs.damage_given DESC",
    ),
    Rule(
        name="pcs_damage_received_rate",
        table="player_comprehensive_stats",
        tier="T1",
        severity="critical",
        predicate="pcs.damage_received > pcs.time_played_seconds * 100",
        note="More than 100 damage/second received sustained — beyond any weapon's max DPS.",
        extra_cols=("pcs.damage_received", "pcs.time_played_seconds"),
        order_by="pcs.damage_received DESC",
    ),
    Rule(
        name="pcs_revives_given_rate",
        table="player_comprehensive_stats",
        tier="T1",
        severity="critical",
        predicate="pcs.revives_given > pcs.time_played_seconds / 8.0",
        note="More than 1 revive per 8s sustained — exceeds the medic pack-out/animation cadence.",
        extra_cols=("pcs.revives_given", "pcs.time_played_seconds"),
        order_by="pcs.revives_given DESC",
    ),
    Rule(
        name="pcs_gibs_rate",
        table="player_comprehensive_stats",
        tier="T1",
        severity="critical",
        predicate="pcs.gibs > pcs.time_played_seconds / 2.0",
        note="More than 1 gib per 2s sustained — exceeds realistic gib cadence.",
        extra_cols=("pcs.gibs", "pcs.time_played_seconds"),
        order_by="pcs.gibs DESC",
    ),
    Rule(
        name="pcs_dynamites_planted_rate",
        table="player_comprehensive_stats",
        tier="T1",
        severity="critical",
        predicate="pcs.dynamites_planted > pcs.time_played_seconds / 25.0",
        note="More than 1 dynamite planted per 25s sustained — exceeds the arm/plant animation cadence.",
        extra_cols=("pcs.dynamites_planted", "pcs.time_played_seconds"),
        order_by="pcs.dynamites_planted DESC",
    ),
    Rule(
        name="pcs_xp_rate",
        table="player_comprehensive_stats",
        tier="T1",
        severity="critical",
        predicate="pcs.xp > pcs.time_played_seconds * 1.5",
        note="More than 1.5 XP/second sustained — exceeds any realistic XP-earning cadence.",
        extra_cols=("pcs.xp", "pcs.time_played_seconds"),
        order_by="pcs.xp DESC",
    ),
    Rule(
        name="pcs_bullets_fired_rate",
        table="player_comprehensive_stats",
        tier="T1",
        severity="critical",
        predicate="pcs.bullets_fired > pcs.time_played_seconds * 15",
        note=(
            "More than 15 bullets/second sustained — beyond any weapon's max fire rate. THE PROVEN ONE: "
            "the all-time accuracy record (2026-08-16) stood on bullets_fired=5,523 in a 269s round; this "
            "rule is that exact bound, applied permanently."
        ),
        extra_cols=("pcs.bullets_fired", "pcs.time_played_seconds"),
        order_by="pcs.bullets_fired DESC",
    ),
    # ── Hard invariants: schema-level, no tolerance ────────────────────────
    Rule(
        name="pcs_headshot_kills_exceeds_kills",
        table="player_comprehensive_stats",
        tier="T1",
        severity="critical",
        predicate="pcs.headshot_kills > pcs.kills",
        note="A headshot kill IS a kill — headshot_kills can never exceed kills.",
        extra_cols=("pcs.headshot_kills", "pcs.kills"),
        order_by="(pcs.headshot_kills - pcs.kills) DESC",
    ),
    Rule(
        name="pcs_accuracy_out_of_range",
        table="player_comprehensive_stats",
        tier="T1",
        severity="critical",
        predicate="pcs.accuracy < 0 OR pcs.accuracy > 100",
        note="accuracy is a percentage; it cannot be negative or exceed 100.",
        extra_cols=("pcs.accuracy",),
        order_by="pcs.accuracy DESC",
    ),
    Rule(
        name="pcs_time_played_percent_out_of_range",
        table="player_comprehensive_stats",
        tier="T1",
        severity="critical",
        predicate="pcs.time_played_percent < 0 OR pcs.time_played_percent > 105",
        note="time_played_percent is a percentage of round duration; 105 gives 5pp slack for rounding/late joins.",
        extra_cols=("pcs.time_played_percent",),
        order_by="pcs.time_played_percent DESC",
    ),
    Rule(
        name="pcs_times_revived_exceeds_deaths",
        table="player_comprehensive_stats",
        tier="T1",
        severity="critical",
        # 2026-08-18 refinement: a /kill body is revivable but self-kills are
        # counted separately from deaths, so the true bound is
        # deaths + self_kills. The one human "violation" of the stricter form
        # (KaNii, te_escape2, 2026-06-28: revived=3, deaths=2, self_kills=1)
        # is exactly this mechanic — 2 real deaths + 1 selfkill-then-revive.
        predicate="pcs.times_revived > pcs.deaths + pcs.self_kills",
        note=(
            "A revive requires a revivable body: a prior death or a self-kill "
            "(counted separately from deaths in the TAB stats). "
            "times_revived > deaths + self_kills cannot happen in the game."
        ),
        extra_cols=("pcs.times_revived", "pcs.deaths", "pcs.player_guid"),
        order_by="(pcs.times_revived - pcs.deaths) DESC",
    ),
    # ── Round context: needs the round's own duration ──────────────────────
    Rule(
        name="pcs_tps_exceeds_round_duration",
        table="player_comprehensive_stats",
        tier="T1",
        severity="high",
        predicate=(
            f"{_ACTUAL_TIME_LOOKS_VALID} AND pcs.time_played_seconds > ({_ACTUAL_TIME_SECONDS} + 60)"
        ),
        note=(
            "time_played_seconds cannot exceed the round's own actual_time duration by more than a 60s "
            "slack (covers halftime/pause quirks). Rows whose actual_time doesn't parse as M:SS are "
            "excluded here (they're independently caught by the rounds-table actual_time rule)."
        ),
        needs_round_join=True,
        extra_cols=("pcs.time_played_seconds", "r.actual_time", "pcs.player_guid"),
        order_by="pcs.time_played_seconds DESC",
    ),
    # ── Internal consistency: two fields that should agree ─────────────────
    Rule(
        name="pcs_dpm_inconsistent_with_damage",
        table="player_comprehensive_stats",
        tier="T1",
        severity="medium",
        predicate=(
            "pcs.time_played_seconds >= 60 "
            "AND ABS(pcs.dpm - pcs.damage_given / (pcs.time_played_seconds / 60.0)) > 5"
        ),
        note="dpm should equal damage_given / minutes played within 5 (rounding slack); tps<60s excluded (denominator too noisy).",
        extra_cols=("pcs.dpm", "pcs.damage_given", "pcs.time_played_seconds"),
        order_by="ABS(pcs.dpm - pcs.damage_given / (pcs.time_played_seconds / 60.0)) DESC",
    ),
    Rule(
        name="pcs_kd_ratio_inconsistent_with_kills_deaths",
        table="player_comprehensive_stats",
        tier="T1",
        severity="medium",
        predicate="ABS(pcs.kd_ratio - pcs.kills::numeric / GREATEST(pcs.deaths, 1)) > 0.15",
        note="kd_ratio should equal kills/GREATEST(deaths,1) within 0.15 (rounding slack).",
        extra_cols=("pcs.kd_ratio", "pcs.kills", "pcs.deaths"),
        order_by="ABS(pcs.kd_ratio - pcs.kills::numeric / GREATEST(pcs.deaths, 1)) DESC",
    ),
    # ── rounds table (T1): completed+valid rounds should have coherent metadata ──
    Rule(
        name="rounds_actual_time_missing_or_nonpositive",
        table="rounds",
        tier="T1",
        severity="critical",
        predicate=(
            f"r.actual_time IS NULL OR NOT ({_ACTUAL_TIME_LOOKS_VALID}) OR {_ACTUAL_TIME_SECONDS} <= 0"
        ),
        note=(
            "A completed, valid round must have a parseable, positive actual_time. "
            "NB: actual_time is the stopwatch clock (g_nextTimeLimit header field), "
            "NOT a measured duration — the measured value is actual_duration_seconds."
        ),
        extra_cols=("r.actual_time", "r.round_status", "r.is_valid"),
        order_by="r.id DESC",
    ),
    Rule(
        name="rounds_actual_time_diverges_without_surrender",
        table="rounds",
        tier="T1",
        severity="high",
        predicate=(
            f"{_ACTUAL_TIME_LOOKS_VALID} "
            # Measured duration is demo-verified from 2026-05-15 on; before
            # that, 7 known rounds carry a pre-v1.7 webhook warmup artifact
            # (duration > clock on completed R1s) — bounded and documented
            # in the RCA, not an active sensor to alarm on daily.
            "AND r.round_date >= '2026-05-15' "
            "AND COALESCE(r.actual_duration_seconds, 0) > 0 "
            f"AND ABS({_ACTUAL_TIME_SECONDS} - r.actual_duration_seconds) > 5 "
            "AND NOT EXISTS (SELECT 1 FROM lua_round_teams l "
            "WHERE l.round_id = r.id AND COALESCE(l.surrender_team, 0) > 0)"
        ),
        note=(
            "actual_time (the stopwatch target written by c0rnp0rn8's header) may "
            "diverge >5s from the MEASURED actual_duration_seconds only on surrender "
            "rounds, where the attackers never set a time and the Lua fallback writes "
            "the full timelimit (RCA 2026-08-18: 67/67 inflated rounds in the last 3 "
            "months were surrender+Fullhold; 0/370 non-surrender rounds diverged). A "
            "live hit here means a NEW way the two time sources disagree — the exact "
            "class of silent bug that inflated 15% of round durations for months."
        ),
        extra_cols=("r.actual_time", "r.actual_duration_seconds", "r.round_outcome"),
        order_by=f"ABS({_ACTUAL_TIME_SECONDS} - r.actual_duration_seconds) DESC",
    ),
    Rule(
        name="rounds_winner_team_invalid",
        table="rounds",
        tier="T1",
        severity="critical",
        # Scoped: rounds before 2026-02-03 predate lua_round_teams capture,
        # and the ones still holding winner_team=0 (a 2026-01-15 cluster + two
        # singles, verified 2026-08-17) have NO surviving source to attribute
        # from — the #728-#730 winner backfill already healed everything
        # healable. Zero violations exist in the live era, so a firing here
        # means the CURRENT pipeline dropped a winner: a real regression.
        predicate="r.winner_team NOT IN (1, 2) AND r.round_date >= '2026-02-03'",
        note=(
            "ET:Legacy has exactly two teams (Axis=1, Allies=2); a completed "
            "valid round must have a winner in that set. Pre-2026-02-03 rounds "
            "are excluded as unhealable pre-Lua-teams residue (no data to "
            "attribute a winner from)."
        ),
        extra_cols=("r.winner_team", "r.defender_team"),
        order_by="r.id DESC",
    ),
    Rule(
        name="rounds_defender_team_invalid",
        table="rounds",
        tier="T1",
        severity="critical",
        # Same era scope and rationale as rounds_winner_team_invalid.
        predicate="r.defender_team NOT IN (1, 2) AND r.round_date >= '2026-02-03'",
        note=(
            "A completed valid round must have a defending team in {1, 2}. "
            "Pre-2026-02-03 rounds are excluded as unhealable pre-Lua-teams "
            "residue."
        ),
        extra_cols=("r.defender_team", "r.winner_team"),
        order_by="r.id DESC",
    ),
    Rule(
        name="rounds_time_or_date_missing",
        table="rounds",
        tier="T1",
        severity="critical",
        predicate="r.round_time IS NULL OR r.round_date IS NULL",
        note="A completed valid round must carry both its calendar date and time-of-day.",
        extra_cols=("r.round_time", "r.round_date"),
        order_by="r.id DESC",
    ),
    # ── R2-cumulative family (2026-08-17, scripts/repair_inverted_r2_cumulative_rounds.py) ──
    Rule(
        name="rounds_orphan_r2_masquerading_as_completed",
        table="rounds",
        tier="T1",
        severity="critical",
        # Scoped to imports after the 2026-08-17 triage: every orphan R2 up to
        # that day was either healed from its original files (values now true
        # differentials — the round legitimately stays 'completed', only its
        # R1 row is missing, which is a completeness matter, not a
        # plausibility one) or stamped 'orphan_r2'. From that day on the
        # importer stamps orphans at import time, so any new one sitting as
        # 'completed' is a live regression.
        predicate=(
            "r.round_number = 2 AND r.round_date >= '" + ORPHAN_SENSOR_ARMED_FROM + "' "
            "AND NOT EXISTS ("
            "SELECT 1 FROM rounds r1 "
            "WHERE r1.match_id = r.match_id AND r1.round_number = 1)"
        ),
        note=(
            "An R2 with no R1 round for its match went through the parser's "
            "orphan path: its player rows hold raw CUMULATIVE (R1+R2) values. "
            "The importer stamps these round_status='orphan_r2' so consumers "
            "exclude them centrally — one sitting as 'completed' means the "
            "stamp was missed and per-round surfaces are showing doubled "
            "stats (this is how the fake all-time damage record happened). "
            "Pre-2026-08-18 orphans are excluded: that backlog was healed or "
            "stamped by scripts/repair_inverted_r2_cumulative_rounds.py."
        ),
        extra_cols=("r.match_id",),
        order_by="r.id DESC",
    ),
    Rule(
        name="rounds_r2_whole_lobby_outscored_r1",
        table="rounds",
        tier="T1",
        severity="medium",
        predicate=(
            "r.round_number = 2 AND "
            "(SELECT COUNT(*) FROM player_comprehensive_stats p2 "
            " JOIN rounds r1 ON r1.match_id = r.match_id AND r1.round_number = 1 "
            " JOIN player_comprehensive_stats p1 "
            "   ON p1.round_id = r1.id AND p1.player_guid = p2.player_guid "
            " WHERE p2.round_id = r.id) >= 4 AND "
            "NOT EXISTS ("
            "SELECT 1 FROM player_comprehensive_stats p2 "
            "JOIN rounds r1 ON r1.match_id = r.match_id AND r1.round_number = 1 "
            "JOIN player_comprehensive_stats p1 "
            "  ON p1.round_id = r1.id AND p1.player_guid = p2.player_guid "
            "WHERE p2.round_id = r.id "
            "  AND (p2.kills < p1.kills OR p2.damage_given < p1.damage_given))"
        ),
        note=(
            "Every shared player (4+) beat their own R1 on BOTH kills and "
            "damage in R2 — the signature of a raw cumulative R2 row that "
            "slipped past pairing. A nomination, not a verdict: "
            "scripts/repair_inverted_r2_cumulative_rounds.py makes the final "
            "call against the original stats file (a genuine whole-lobby R2 "
            "bloodbath is possible, just rare)."
        ),
        extra_cols=("r.match_id",),
        order_by="r.id DESC",
    ),
]


def validate_rules(rules: list[Rule]) -> None:
    """Structural sanity — same check the unit test runs, exposed for reuse."""
    names = [r.name for r in rules]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise ValueError(f"Duplicate rule names: {sorted(dupes)}")
    for r in rules:
        if r.tier not in VALID_TIERS:
            raise ValueError(f"{r.name}: invalid tier {r.tier!r}")
        if r.severity not in VALID_SEVERITIES:
            raise ValueError(f"{r.name}: invalid severity {r.severity!r}")
        if r.table not in VALID_TABLES:
            raise ValueError(f"{r.name}: invalid table {r.table!r}")
        if r.table == "rounds" and r.needs_round_join:
            raise ValueError(f"{r.name}: needs_round_join is meaningless on the rounds table itself")
        if not r.predicate.strip():
            raise ValueError(f"{r.name}: empty predicate")


# ── SQL builders ────────────────────────────────────────────────────────────


def _from_clause(rule: Rule) -> tuple[str, str]:
    """Returns (from_clause, base_gate) for a rule."""
    if rule.table == "player_comprehensive_stats":
        join = " JOIN rounds r ON r.id = pcs.round_id" if rule.needs_round_join else ""
        return f"player_comprehensive_stats pcs{join}", _PCS_BASE_GATE
    return "rounds r", _ROUNDS_BASE_GATE


def _date_col(rule: Rule) -> str:
    return "pcs.round_date" if rule.table == "player_comprehensive_stats" else "r.round_date"


def build_count_sql(rule: Rule) -> str:
    from_clause, base_gate = _from_clause(rule)
    return f"SELECT COUNT(*) FROM {from_clause} WHERE {base_gate} AND ({rule.predicate})"  # noqa: S608 # nosec B608 - rules are hardcoded literals validated at import


def build_split_sql(rule: Rule) -> str:
    from_clause, base_gate = _from_clause(rule)
    date_col = _date_col(rule)
    return (
        f"SELECT "
        f"COUNT(*) FILTER (WHERE {date_col} < '{PROVENANCE_CUTOFF}') AS backfill, "
        f"COUNT(*) FILTER (WHERE {date_col} >= '{PROVENANCE_CUTOFF}') AS live "
        f"FROM {from_clause} WHERE {base_gate} AND ({rule.predicate})"  # noqa: S608 # nosec B608 - rules are hardcoded literals validated at import
    )


def build_top_rows_sql(rule: Rule, limit: int) -> tuple[str, list[str]]:
    from_clause, base_gate = _from_clause(rule)
    if rule.table == "player_comprehensive_stats":
        identity = "pcs.player_name, pcs.round_date, pcs.map_name, pcs.round_number, pcs.round_id"
        id_labels = ["player", "round_date", "map", "round_number", "round_id"]
    else:
        identity = "r.id, r.round_date, r.map_name, r.round_number"
        id_labels = ["round_id", "round_date", "map", "round_number"]
    extra_labels = [c.split(".", 1)[1] for c in rule.extra_cols]
    cols = identity + ("," if rule.extra_cols else "") + ", ".join(rule.extra_cols)
    order_by = rule.order_by or ("pcs.id DESC" if rule.table == "player_comprehensive_stats" else "r.id DESC")
    sql = f"SELECT {cols} FROM {from_clause} WHERE {base_gate} AND ({rule.predicate}) ORDER BY {order_by} LIMIT {int(limit)}"  # noqa: S608 # nosec B608 - rules are hardcoded literals validated at import
    return sql, id_labels + extra_labels


# ── Execution ───────────────────────────────────────────────────────────────


def _composed(sql_text: str):
    """Wrap rule-built SQL in psycopg2's composition type before execution.

    The builders above assemble their statements exclusively from hardcoded
    literals in the RULES table (validated at import — see validate_rules and
    the structural tests), never from user input. Routing the finished text
    through psycopg2.sql.SQL makes that contract explicit in the type system,
    which is also what static SQL-injection scanners key on.
    """
    from psycopg2 import sql as _psql  # lazy, like the psycopg2 import itself

    return _psql.SQL(sql_text)


@dataclass
class RuleResult:
    rule: Rule
    total: int
    backfill: int
    live: int
    top_rows: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.rule.name,
            "table": self.rule.table,
            "tier": self.rule.tier,
            "severity": self.rule.severity,
            "note": self.rule.note,
            "total": self.total,
            "backfill": self.backfill,
            "live": self.live,
            "top_rows": self.top_rows,
        }


def run_audit(conn, rules: list[Rule], top_n: int = 3) -> list[RuleResult]:
    results: list[RuleResult] = []
    with conn.cursor() as cur:
        for rule in rules:
            cur.execute(_composed(build_count_sql(rule)))
            total = int(cur.fetchone()[0])

            cur.execute(_composed(build_split_sql(rule)))
            backfill, live = (int(v) for v in cur.fetchone())

            top_rows: list[dict[str, Any]] = []
            if total > 0:
                sql, labels = build_top_rows_sql(rule, top_n)
                cur.execute(_composed(sql))
                top_rows.extend(dict(zip(labels, row, strict=True)) for row in cur.fetchall())

            results.append(RuleResult(rule=rule, total=total, backfill=backfill, live=live, top_rows=top_rows))
    return results


# ── Rendering ───────────────────────────────────────────────────────────────


def render_markdown(results: list[RuleResult], generated_at: str) -> str:
    lines: list[str] = []
    lines.append("# Data Plausibility Audit (T1)")
    lines.append("")
    lines.append(f"Generated: {generated_at}")
    lines.append("")
    lines.append(
        f"Provenance split: `round_date < {PROVENANCE_CUTOFF}` = backfill (lossy historical import), "
        f"`>= {PROVENANCE_CUTOFF}` = live (current capture pipeline). No `data_source` column exists yet; "
        "this is the same proxy used to fix the all-time accuracy record (#755)."
    )
    lines.append("")

    total_rules = len(results)
    rules_with_violations = sum(1 for r in results if r.total > 0)
    rules_with_live = [r for r in results if r.live > 0]
    lines.append(
        f"**Summary**: {total_rules} rules checked, {rules_with_violations} fired at least once, "
        f"**{len(rules_with_live)} fired on LIVE data**."
    )
    lines.append("")

    lines.append("## Rules (by violation count)")
    lines.append("")
    lines.append("| Rule | Table | Severity | Total | Backfill | Live | Note |")
    lines.append("|---|---|---|---:|---:|---:|---|")
    for r in sorted(results, key=lambda r: r.total, reverse=True):
        flag = " ⚠️" if r.live > 0 else ""
        lines.append(
            f"| `{r.rule.name}`{flag} | {r.rule.table} | {r.rule.severity} | {r.total} | {r.backfill} | {r.live} | {r.rule.note} |"
        )
    lines.append("")

    lines.append("## Detail")
    lines.append("")
    for r in sorted(results, key=lambda r: r.total, reverse=True):
        lines.append(f"### `{r.rule.name}` ({r.rule.table}, {r.rule.severity}, {r.rule.tier})")
        lines.append("")
        lines.append(r.rule.note)
        lines.append("")
        lines.append(f"- Total violations: **{r.total}** (backfill: {r.backfill}, live: {r.live})")
        if r.top_rows:
            lines.append("- Top offending rows:")
            for row in r.top_rows:
                pairs = ", ".join(f"{k}={v}" for k, v in row.items())
                lines.append(f"  - {pairs}")
        lines.append("")

    live_rules = [r for r in results if r.live > 0]
    lines.append("## LIVE violations (capture bugs — headline section)")
    lines.append("")
    if not live_rules:
        lines.append("None. Every violation found traces to pre-2026 backfill rows only.")
    else:
        lines.append(
            "Every rule below fired on rows captured by the CURRENT live pipeline "
            f"(round_date >= {PROVENANCE_CUTOFF}), not old backfill noise. These are active bugs, not history."
        )
        lines.append("")
        lines.extend(
            f"- `{r.rule.name}` ({r.rule.severity}): **{r.live}** live violations — {r.rule.note}"
            for r in sorted(live_rules, key=lambda r: r.live, reverse=True)
        )
    lines.append("")
    return "\n".join(lines)


def render_json(results: list[RuleResult], generated_at: str) -> str:
    payload = {
        "generated_at": generated_at,
        "provenance_cutoff": PROVENANCE_CUTOFF,
        "rules_checked": len(results),
        "rules_with_live_violations": sum(1 for r in results if r.live > 0),
        "rules": [r.to_dict() for r in results],
    }
    return json.dumps(payload, indent=2, default=str)


# ── CLI ─────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    def _non_negative(value: str) -> int:
        n = int(value)
        if n < 0:
            raise argparse.ArgumentTypeError("--top must be >= 0")
        return n

    parser.add_argument("--top", type=_non_negative, default=3, help="Top offending rows to show per rule (default: 3)")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON to stdout instead of markdown")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Markdown report file path (default: docs/research/DATA_PLAUSIBILITY_T1_<date>.md). Ignored with --json.",
    )
    args = parser.parse_args(argv)

    validate_rules(RULES)

    conn = get_connection()
    try:
        results = run_audit(conn, RULES, top_n=args.top)
    finally:
        conn.close()

    generated_at = datetime.now(timezone.utc).date().isoformat()

    if args.json:
        print(render_json(results, generated_at))
    else:
        report = render_markdown(results, generated_at)
        print(report)
        out_path = args.output or (_REPO_ROOT / "docs" / "research" / f"DATA_PLAUSIBILITY_T1_{generated_at}.md")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"\nReport written to {out_path}", file=sys.stderr)

    return sum(1 for r in results if r.live > 0)


if __name__ == "__main__":
    sys.exit(main())
