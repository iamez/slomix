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

Exit code = number of per-row rules with at least one LIVE violation, plus
the number of trend rules carrying a distribution shift nobody has explained
(0 = clean). This is deliberately a shell-guard-friendly number, not a total
violation count: one rule firing 500 times is still "one broken sensor", not
500, and a metric that moved in three consecutive months is one thing to look
at, not three.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared.round_time import MMSS_SQL_REGEX, round_duration_sql  # noqa: E402 (needs the sys.path bootstrap above)

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

# The day the game server's Lua stopped double-counting limbo time. It armed
# the two dead-time rules while their 80 + 43 historical rows still stood; the
# 2026-09-03 reconstruction repaired every one of them, so both rules are
# unarmed again and this date is kept only as the documented boundary between
# the inflated era and the measured one.
DEAD_TIME_FIX = "2026-04-01"

# The day #885 reached main and the bot was restarted, so the live import
# began writing time_played_percent again. What is left before it is a finite,
# named backlog of 16 rows in three rounds: 14 whose capture files no longer
# parse (te_escape2 2026-08-20 R2, supply 2026-08-26 R1) and 2 whose engine
# value reads 101.2%, which the backfill refuses on purpose. #886's backfill
# has done everything it can -- re-run on 2026-09-03: 0 resolvable rows left.
TPP_WRITTEN_ARMED_FROM = "2026-09-03"

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
_ACTUAL_TIME_LOOKS_VALID = f"r.actual_time ~ '{MMSS_SQL_REGEX}'"
# PostgreSQL does NOT guarantee left-to-right short-circuit evaluation of AND/OR
# operands, so pairing the regex guard and the cast as separate conjuncts is not
# actually safe — the planner may evaluate the cast first and raise on a
# malformed value. The CASE expression makes the guard part of the expression
# itself: a non-matching actual_time yields NULL instead of a cast error.
_ACTUAL_TIME_SECONDS = (
    f"(CASE WHEN r.actual_time ~ '{MMSS_SQL_REGEX}' "
    "THEN split_part(r.actual_time, ':', 1)::int * 60 + split_part(r.actual_time, ':', 2)::int "
    "END)"
)
# The DURATION of a round is NOT actual_time (that is the stopwatch TARGET,
# g_nextTimeLimit — inflated on ~15% of rounds, RCA 2026-08-18 / PR #770).
# Any rule that means "how long did this round last" must go through the one
# shared helper, exactly like the bot and the website do.
_ROUND_DURATION_SECONDS = round_duration_sql("r")


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
    # Non-empty = this rule is EXPECTED to fire right now, for a reason that is
    # written down here and already being fixed. Such a rule still runs, still
    # counts, and still appears in the report -- it just does not colour the
    # sensor red or wake the daily alert, because a permanently red sensor
    # stops being read and then the NEXT problem hides behind it.
    #
    # The string must name the reason AND what closes it. An acknowledgement
    # with no exit is a mute, and a mute is how five months go by.
    acknowledged: str = ""
    # The day this rule became responsible for what it finds. Rows BEFORE it
    # are still counted and still shown -- they move into their own `pre-arming`
    # column, not out of the report -- but they no longer reach the exit code
    # or the daily alert.
    #
    # This is the honest alternative to an acknowledgement for a defect whose
    # cause is already fixed: the acknowledgement mutes the WHOLE rule, so a
    # fresh occurrence of the same breakage is swallowed alongside the history
    # it was meant to excuse. An arming date mutes only the past. A rule with
    # a known, finite backlog and a landed fix should be armed, not muted.
    #
    # (The orphan-R2 rule predates this field and bakes its date into the
    # predicate instead, which hides the backlog entirely rather than parking
    # it in a column. Arming is the better half of that idea.)
    armed_from: str = ""


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
        name="pcs_time_played_percent_is_zero",
        table="player_comprehensive_stats",
        tier="T1",
        severity="critical",
        # Zero is INSIDE the range the rule above checks, which is exactly why
        # this went unseen: `out_of_range` asks whether the value is possible,
        # never whether it was written at all. The live import path
        # (postgresql_database_manager) omitted the column from its INSERT, so
        # every row it created took the schema DEFAULT 0 -- 100% of rows from
        # the 2026-03-24 session onward.
        #
        # The damage is downstream: sessions_router computes survival_rate
        # engine-first from this field, so survivability, consistency,
        # aggression, discipline_score and alive_pct all silently fell back to
        # dead-time. And alive_pct_drift -- the check that compares the two
        # sources -- can only fire when both exist, so the one guard that
        # would have reported this was disabled by the omission itself.
        predicate="pcs.time_played_percent = 0",
        note="time_played_percent (TAB[8], engine alive%) is zero on a row with playtime. "
             "Zero is in range, so the range rule cannot see it: this asks whether the "
             "value was WRITTEN, not whether it is possible.",
        # Armed rather than acknowledged: the live import writes the column
        # again as of this date, so a zero from here on is a NEW break and has
        # to be loud. What sits before it is a finite, named backlog (see
        # TPP_WRITTEN_ARMED_FROM), still counted and still shown.
        armed_from=TPP_WRITTEN_ARMED_FROM,
        extra_cols=("pcs.time_played_percent", "pcs.time_played_seconds"),
        order_by="pcs.time_played_seconds DESC",
    ),
    Rule(
        name="pcs_time_dead_exceeds_time_played",
        table="player_comprehensive_stats",
        tier="T1",
        severity="critical",
        # A player cannot be dead longer than they were in the round. Read-time
        # LEAST(dead, played) hides this in session views, but season leaders
        # and every all-time ranking read the raw column -- which is how a row
        # claiming 580 minutes dead in a 7-minute round ends up at the top.
        predicate="pcs.time_dead_minutes > pcs.time_played_seconds / 60.0 + 0.05",
        note="time_dead_minutes cannot exceed the player's own time in the round "
             "(0.05 min of slack for rounding). Caused by the pre-2026-03-20 "
             "c0rnp0rn8 accumulator, which re-added the running limbo time every "
             "5s without resetting it.",
        # Armed on 2026-04-01 while 80 historical rows still broke this; the
        # reconstruction (scripts/repair_dead_time_reconstruction.py, run
        # 2026-09-03) repaired all 80, so the arming date now carves out
        # nothing and the rule stands on its own -- which is what the
        # arming stale-check demanded the moment the count reached zero.
        extra_cols=("pcs.time_dead_minutes", "pcs.time_played_seconds"),
        order_by="(pcs.time_dead_minutes - pcs.time_played_seconds / 60.0) DESC",
    ),
    Rule(
        name="pcs_time_dead_ratio_out_of_range",
        table="player_comprehensive_stats",
        tier="T1",
        severity="critical",
        predicate="pcs.time_dead_ratio < 0 OR pcs.time_dead_ratio > 100.5",
        note="time_dead_ratio is a percentage of time played; 0.5pp of slack for "
             "rounding. Same accumulator as the rule above -- the worst stored "
             "value is 3690%.",
        # Same accumulator, same fix, same history: 43 rows, all repaired by
        # the 2026-09-03 reconstruction. Unarmed for the same reason as the
        # rule above.
        extra_cols=("pcs.time_dead_ratio",),
        order_by="pcs.time_dead_ratio DESC",
    ),
    Rule(
        name="pcs_time_dead_inconsistent_with_ratio",
        table="player_comprehensive_stats",
        tier="T1",
        severity="high",
        # R1 ONLY, and the threshold is measured rather than guessed.
        #
        # R2 is excluded because the two fields legitimately diverge there: the
        # parser recomputes time_dead_ratio after the differential while
        # time_dead_minutes is taken raw (it is in R2_ONLY_FIELDS). That is
        # ~8% of live R2 rows behaving as designed -- a blanket rule would
        # report 263 correct rows as broken.
        #
        # On live R1 rows (n=3,488) the deviation runs p99 = 0.300 min,
        # p99.9 = 1.212, max = 1.70, and NOTHING exceeds 2.0. The threshold sits
        # above the measured noise floor, so this rule lands green and only
        # lights up on a genuinely new way the two fields disagree.
        predicate=(
            "pcs.round_number = 1 AND pcs.time_played_seconds > 60 "
            "AND abs(pcs.time_dead_minutes "
            "        - (pcs.time_played_seconds / 60.0) * pcs.time_dead_ratio / 100.0) > 2.0"
        ),
        note="R1 only: time_dead_minutes and time_dead_ratio describe the same "
             "quantity and must agree within 2 minutes. Threshold measured against "
             "live R1 data (p99 = 0.3 min, max = 1.7, none above 2.0). R2 is "
             "excluded: the ratio is recomputed post-differential there while the "
             "minutes are taken raw, so ~8% diverge by design.",
        extra_cols=("pcs.time_dead_minutes", "pcs.time_dead_ratio", "pcs.time_played_seconds"),
        order_by=("abs(pcs.time_dead_minutes "
                  "- (pcs.time_played_seconds / 60.0) * pcs.time_dead_ratio / 100.0) DESC"),
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
            f"{_ROUND_DURATION_SECONDS} > 0 "
            f"AND pcs.time_played_seconds > ({_ROUND_DURATION_SECONDS} + 60)"
        ),
        note=(
            "time_played_seconds cannot exceed the round's own MEASURED duration "
            "(shared.round_time: lua actual_duration_seconds, falling back to parsed "
            "actual_time) by more than a 60s slack (covers halftime/pause quirks). A round "
            "whose duration is unknown — no measurement and an absent or zero actual_time — "
            "is skipped: 'played 720s in a 0s round' says the CLOCK is missing, which the "
            "rounds-table actual_time rule already reports, and counting it here would bill "
            "one broken round to two sensors (measured 2026-08-19: every backfill hit of this "
            "rule was exactly such a 0:00 round)."
        ),
        needs_round_join=True,
        extra_cols=(
            "pcs.time_played_seconds",
            # The duration the predicate actually used, spelled out: with only
            # the two raw sources on show, a reader has to redo the COALESCE in
            # their head to see which one decided the row (coderabbit, PR #779).
            f"{_ROUND_DURATION_SECONDS} AS round_duration_seconds",
            "r.actual_duration_seconds",
            "r.actual_time",
            "pcs.player_guid",
        ),
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


# ── Distribution shifts: the class a per-row predicate cannot see ───────────
#
# Every rule above is a per-row predicate, so it can only see a row that is
# individually impossible. The defect this section was written for is not of
# that kind. Around 2026-03-20 a fix on the game server changed how the Lua
# accumulates dead time; the median dead-time share of a round fell from
# ~0.35 to ~0.19 overnight and stayed there — with every single row still
# comfortably inside every bound the audit checks. Twenty-three rules saw
# nothing, the sensor stayed green, and for five months the two halves of the
# table were compared to each other under one column name.
#
# A trend rule watches a monthly statistic instead of a row: it fires when a
# month departs from the median of the months before it. Three design points,
# each measured on this database rather than assumed:
#
#  * The statistic is a MEDIAN of per-row values, never a ratio of sums. On
#    the same data the ratio of sums calls 2025-12 a +96% move; the median
#    calls it +14%. The difference is a handful of impossible rows (largest
#    time_dead_minutes that month: 580, in a round that lasted seven). Those
#    rows are the per-row rules' job — a trend rule they can move is
#    measuring somebody else's subject.
#
#  * Each threshold sits above that metric's OWN measured noise. Over the
#    full history the largest quiet month-over-month move is 4.5% for
#    damage/min and 14.0% for dead share; a single shared threshold would
#    either miss real moves in the quiet metrics or fire monthly on the noisy
#    one. The quiet metrics are not filler: they are the controls that say a
#    firing is about ITS metric and not about the month (in 2026-04, dead
#    share moved -45% while damage/min moved -0.5%).
#
#  * A month below `min_rows` is not measured and does not feed a baseline.
#    The month in progress therefore stays silent until it has enough rows to
#    be a measurement (monthly volume here runs 214–1632 rows), which costs a
#    few days of detection latency and buys back every false alarm that a
#    two-session sample would have produced.


@dataclass(frozen=True)
class TrendRule:
    name: str  # unique, snake_case
    statistic: str  # SQL aggregate over `pcs`, producing one value per month
    threshold_pct: float  # |move| against the baseline that counts as a shift
    note: str
    lookback: int = 3  # months of history the baseline median is taken from
    min_rows: int = 200  # a month below this is neither measured nor a baseline
    # Months this rule is KNOWN to fire on, each with the explanation that
    # accounts for it. Same contract as Rule.acknowledged: a shift nobody has
    # named keeps the sensor red, and a permanently red sensor stops being
    # read. The difference is expiry — an acknowledgement ends when its repair
    # lands, while a past month's statistic does not change on its own. It
    # changes when WE rewrite that history, which is precisely when these
    # entries must be revisited, and precisely what the stale test checks.
    known_shifts: tuple[tuple[str, str], ...] = ()
    # As Rule.acknowledged: the whole rule is expected to fire right now, for
    # a written-down reason that is already being fixed.
    acknowledged: str = ""


_MEDIAN_OF = "percentile_cont(0.5) WITHIN GROUP (ORDER BY {expr})"

TREND_RULES: list[TrendRule] = [
    TrendRule(
        name="pcs_dead_time_share_monthly",
        statistic=_MEDIAN_OF.format(expr="pcs.time_dead_minutes / (pcs.time_played_seconds / 60.0)"),
        threshold_pct=25.0,
        note=(
            "Median share of a round spent dead. The metric the 2026-03 Lua "
            "fix moved, and the reason this rule class exists.\n"
            "It carried three explained shifts until 2026-09-03 -- 2025-05 "
            "(+46.5%), 2026-04 (-53.1%) and its echo 2026-05 (-41.4%) -- and "
            "carries none now. The reconstruction "
            "(scripts/repair_dead_time_reconstruction.py) rewrote 8,721 "
            "pre-fix rows from the engine's own alive%, and the series went "
            "flat: 0.19-0.23 across all twenty months, where it used to step "
            "from ~0.35 to ~0.19. That is this rule reporting on its own "
            "repair -- a detector built and calibrated on the broken data, "
            "finding nothing left to report."
        ),
    ),
    TrendRule(
        name="pcs_damage_per_minute_monthly",
        statistic=_MEDIAN_OF.format(expr="pcs.damage_given / (pcs.time_played_seconds / 60.0)"),
        threshold_pct=20.0,
        note=(
            "Median damage per minute played. A control: it has never moved "
            "more than 4.5% in 15 months, including across both dead-time "
            "regime changes, so a firing here means the capture itself moved."
        ),
    ),
    TrendRule(
        name="pcs_kills_per_minute_monthly",
        statistic=_MEDIAN_OF.format(expr="pcs.kills / (pcs.time_played_seconds / 60.0)"),
        threshold_pct=20.0,
        note="Median kills per minute played. Control metric; quiet max 5.8%.",
    ),
    TrendRule(
        name="pcs_deaths_per_minute_monthly",
        statistic=_MEDIAN_OF.format(expr="pcs.deaths / (pcs.time_played_seconds / 60.0)"),
        threshold_pct=20.0,
        note=(
            "Median deaths per minute played. Control metric (quiet max "
            "5.2%), and the one that separates 'people died more' from 'we "
            "measured dying differently': in 2026-04 dead share fell 45% "
            "while this stayed flat."
        ),
    ),
    TrendRule(
        name="pcs_headshots_per_kill_monthly",
        statistic=_MEDIAN_OF.format(expr="pcs.headshots::float / NULLIF(pcs.kills, 0)"),
        threshold_pct=25.0,
        note=(
            "Median headshots per kill. Watches the pair of fields most often "
            "confused for each other (headshots != headshot_kills); quiet max "
            "7.1%."
        ),
    ),
    TrendRule(
        name="pcs_revives_per_minute_monthly",
        statistic=_MEDIAN_OF.format(expr="pcs.revives_given / (pcs.time_played_seconds / 60.0)"),
        threshold_pct=25.0,
        note="Median revives given per minute played. Quiet max 11.4%.",
        known_shifts=(
            (
                "2025-12",
                "revives_given is 0 on all 5,538 rows before this month and "
                "non-zero on 653 of 982 rows in it: the field was not "
                "captured, then it was. Consequence worth keeping in view — "
                "every all-time revive total silently begins in 2025-12.",
            ),
            (
                "2026-01",
                "Same appearance as 2025-12: with only one month of non-zero "
                "history the baseline median is still 0, so the arrival is "
                "reported again.",
            ),
        ),
    ),
    TrendRule(
        name="pcs_time_played_percent_written_monthly",
        statistic="AVG(CASE WHEN pcs.time_played_percent > 0 THEN 1.0 ELSE 0.0 END)",
        threshold_pct=10.0,
        note=(
            "Share of rows carrying an engine alive% at all. The aggregate "
            "form of 'a field stopped being written' — the per-row rule can "
            "only say a zero is present, this says how the population of "
            "zeros moved. Quiet max 1.3%.\n"
            "Deliberately NOT acknowledged, even though a firing is "
            "foreseeable: the live import writes 0 here until #885 is "
            "deployed, so a month imported in between can drop below the "
            "threshold. That firing would be TRUE — the field really is not "
            "being written — and the fix is to deploy #885 and re-run #886's "
            "backfill. Muting it in advance would buy silence about a "
            "different, unrelated break of the same field."
        ),
    ),
]


def validate_trend_rules(rules: list[TrendRule]) -> None:
    """Structural sanity for the aggregate rules, mirroring validate_rules."""
    names = [r.name for r in rules]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise ValueError(f"Duplicate trend rule names: {sorted(dupes)}")
    for r in rules:
        if not r.statistic.strip():
            raise ValueError(f"{r.name}: empty statistic")
        if r.threshold_pct <= 0:
            raise ValueError(f"{r.name}: threshold_pct must be > 0")
        if r.lookback < 1:
            raise ValueError(f"{r.name}: lookback must be >= 1")
        if r.min_rows < 1:
            raise ValueError(f"{r.name}: min_rows must be >= 1")
        months = [m for m, _ in r.known_shifts]
        if len(months) != len(set(months)):
            raise ValueError(f"{r.name}: duplicate month in known_shifts")
        for month, why in r.known_shifts:
            if len(month) != 7 or month[4] != "-":
                raise ValueError(f"{r.name}: known_shifts month {month!r} is not YYYY-MM")
            if not why.strip():
                raise ValueError(f"{r.name}: known shift {month} has no explanation")


@dataclass(frozen=True)
class MonthlyPoint:
    """One month of a trend rule's statistic, as the database reports it."""

    month: str  # YYYY-MM
    rows: int
    value: float | None  # None = the statistic is undefined for that month


@dataclass(frozen=True)
class Shift:
    month: str
    kind: str  # "moved" | "appeared" | "vanished"
    value: float | None
    baseline: float | None
    change_pct: float | None  # None where a percentage would be meaningless
    explanation: str  # "" = nobody has accounted for this one

    def to_dict(self) -> dict[str, Any]:
        return {
            "month": self.month,
            "kind": self.kind,
            "value": self.value,
            "baseline": self.baseline,
            "change_pct": self.change_pct,
            "explanation": self.explanation,
        }


def _classify_move(baseline: float, value: float | None, threshold_pct: float) -> tuple[str, float | None]:
    """Name what happened between a baseline and a month, or "" for nothing.

    Absent, zero and present are three different states here, and a single
    percentage cannot carry all three: 0 -> 0.18 is not "+inf%", it is a
    field that started being written.
    """
    if value is None:
        return "vanished", None
    if baseline == 0:
        return ("appeared", None) if value != 0 else ("", None)
    change = (value - baseline) / baseline * 100.0
    if abs(change) >= threshold_pct:
        return "moved", change
    return "", change


def find_shifts(rule: TrendRule, series: list[MonthlyPoint]) -> list[Shift]:
    """The whole detector, as a pure function over a monthly series.

    Kept free of psycopg2 so its behaviour can be tested on hand-built series
    — including the ones this database does not contain (a metric vanishing,
    a month too small to measure) and the one it no longer contains, since
    the #886 backfill repaired it.
    """
    known = dict(rule.known_shifts)
    history: list[float] = []
    shifts: list[Shift] = []
    for point in series:
        if point.rows < rule.min_rows:
            # Too small to be a measurement, and therefore too small to be
            # somebody else's baseline.
            continue
        if len(history) >= rule.lookback:
            baseline = statistics.median(history[-rule.lookback:])
            kind, change = _classify_move(baseline, point.value, rule.threshold_pct)
            if kind:
                shifts.append(
                    Shift(
                        month=point.month,
                        kind=kind,
                        value=point.value,
                        baseline=baseline,
                        change_pct=change,
                        explanation=known.get(point.month, ""),
                    )
                )
        if point.value is not None:
            history.append(point.value)
    return shifts


@dataclass
class TrendResult:
    rule: TrendRule
    series: list[MonthlyPoint]
    shifts: list[Shift]

    @property
    def unexplained(self) -> list[Shift]:
        return [s for s in self.shifts if not s.explanation]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.rule.name,
            "note": self.rule.note,
            "threshold_pct": self.rule.threshold_pct,
            "months_measured": sum(1 for p in self.series if p.rows >= self.rule.min_rows),
            "acknowledged": self.rule.acknowledged,
            "shifts": [s.to_dict() for s in self.shifts],
            "unexplained": len(self.unexplained),
        }


def unexplained_shift_count(results: list[TrendResult]) -> int:
    """Trend rules carrying at least one shift nobody has accounted for.

    Counted per RULE, like unacknowledged_live_count above: one metric that
    moved in three consecutive months is one thing to look at, not three.
    """
    return sum(1 for r in results if r.unexplained and not r.rule.acknowledged)


def build_trend_sql(rule: TrendRule) -> str:
    """Monthly series for a trend rule, under the same gate as the per-row rules.

    `round_date` is stored as text, so the month is taken by substring rather
    than to_char — the `::text` keeps that true if the column type ever changes
    under us.
    """
    return (
        "SELECT substring(pcs.round_date::text, 1, 7) AS month, "
        "COUNT(*) AS rows, "
        f"({rule.statistic})::float AS value "  # noqa: S608 # nosec B608 - statistics are hardcoded literals validated at import
        "FROM player_comprehensive_stats pcs "
        f"WHERE {_PCS_BASE_GATE} "
        "GROUP BY 1 ORDER BY 1"
    )


def run_trend_audit(conn, rules: list[TrendRule]) -> list[TrendResult]:
    results: list[TrendResult] = []
    with conn.cursor() as cur:
        for rule in rules:
            cur.execute(_composed(build_trend_sql(rule)))
            series = [
                MonthlyPoint(month=str(m), rows=int(n), value=None if v is None else float(v))
                for m, n, v in cur.fetchall()
            ]
            results.append(TrendResult(rule=rule, series=series, shifts=find_shifts(rule, series)))
    return results


def render_trend_markdown(results: list[TrendResult]) -> list[str]:
    lines: list[str] = []
    lines.append("## Distribution shifts (aggregate rules)")
    lines.append("")
    lines.append(
        "A month whose statistic departs from the median of the "
        "months before it. This is the class no per-row predicate can see: "
        "the 2026-03 dead-time fix moved the median dead share by 45% while "
        "every individual row stayed inside every bound."
    )
    lines.append("")
    unexplained = [r for r in results if r.unexplained and not r.rule.acknowledged]
    lines.append(
        f"**{len(unexplained)} of {len(results)} trend rules carry an unexplained shift.**"
    )
    lines.append("")
    lines.append("| Rule | Threshold | Months | Shifts | Unexplained |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in results:
        flag = " ⚠️" if r.unexplained and not r.rule.acknowledged else ""
        months = sum(1 for p in r.series if p.rows >= r.rule.min_rows)
        lines.append(
            f"| `{r.rule.name}`{flag} | ±{r.rule.threshold_pct:.0f}% | {months} | "
            f"{len(r.shifts)} | {len(r.unexplained)} |"
        )
    lines.append("")
    for r in results:
        if not r.shifts:
            continue
        lines.append(f"### `{r.rule.name}`")
        lines.append("")
        lines.append(r.rule.note)
        if r.rule.acknowledged:
            lines.append("")
            lines.append(f"*Acknowledged: {r.rule.acknowledged}*")
        lines.append("")
        for s in r.shifts:
            if s.change_pct is None:
                headline = f"**{s.month}** — {s.kind} (baseline {s.baseline:.4g}, value {s.value if s.value is None else format(s.value, '.4g')})"
            else:
                headline = f"**{s.month}** — {s.change_pct:+.1f}% ({s.baseline:.4g} -> {s.value:.4g})"
            lines.append(f"- {headline}")
            lines.append(f"  - {s.explanation if s.explanation else '**UNEXPLAINED** — nobody has accounted for this month.'}")
        lines.append("")
    return lines


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
        if r.armed_from:
            if len(r.armed_from) != 10 or r.armed_from[4] != "-" or r.armed_from[7] != "-":
                raise ValueError(f"{r.name}: armed_from {r.armed_from!r} is not YYYY-MM-DD")
            if r.acknowledged:
                raise ValueError(
                    f"{r.name}: armed_from and acknowledged do the same job by "
                    f"different means; acknowledged mutes the whole rule, arming "
                    f"mutes only the past. Pick one.")


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


def live_boundary(rule: Rule) -> str:
    """The date from which a rule's findings count as LIVE.

    An arming date earlier than the provenance cutover would carve nothing
    out, so the boundary is whichever of the two comes later. Both are
    ISO dates, and `round_date` is stored as text, so this is a plain string
    comparison in SQL as well as here.
    """
    if not rule.armed_from:
        return PROVENANCE_CUTOFF
    return max(rule.armed_from, PROVENANCE_CUTOFF)


def build_split_sql(rule: Rule) -> str:
    """Three buckets that always sum to the rule's total.

    backfill    -- before the provenance cutover, lossy historical import
    pre_arming  -- live-captured, but before this rule took responsibility
    live        -- what the exit code and the daily alert actually read

    An unarmed rule has an empty middle bucket, so nothing about the existing
    two-way split changes for the twenty-odd rules that do not use arming.
    """
    from_clause, base_gate = _from_clause(rule)
    date_col = _date_col(rule)
    live_from = live_boundary(rule)
    return (
        f"SELECT "
        f"COUNT(*) FILTER (WHERE {date_col} < '{PROVENANCE_CUTOFF}') AS backfill, "
        f"COUNT(*) FILTER (WHERE {date_col} >= '{PROVENANCE_CUTOFF}' "
        f"                   AND {date_col} < '{live_from}') AS pre_arming, "
        f"COUNT(*) FILTER (WHERE {date_col} >= '{live_from}') AS live "
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
    # `table.column` -> `column`, but an aliased expression names itself: a
    # rule may show a computed value (e.g. the duration the predicate used),
    # and splitting that on the first dot would label it with SQL fragments.
    extra_labels = [
        c.rsplit(" AS ", 1)[1].strip() if " AS " in c else c.split(".", 1)[1]
        for c in rule.extra_cols
    ]
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
    pre_arming: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.rule.name,
            "table": self.rule.table,
            "tier": self.rule.tier,
            "severity": self.rule.severity,
            "note": self.rule.note,
            "total": self.total,
            "backfill": self.backfill,
            "pre_arming": self.pre_arming,
            "armed_from": self.rule.armed_from,
            "live": self.live,
            "acknowledged": self.rule.acknowledged,
            "top_rows": self.top_rows,
        }


def unacknowledged_live_count(results: list[RuleResult]) -> int:
    """The exit code: rules firing on live rows that nobody has accounted for.

    An acknowledged rule is a known, tracked problem. Counting it here would
    keep the exit code non-zero for as long as the repair takes, and a code
    that is always non-zero stops meaning "something new broke".
    """
    return sum(1 for r in results if r.live > 0 and not r.rule.acknowledged)


def run_audit(conn, rules: list[Rule], top_n: int = 3) -> list[RuleResult]:
    results: list[RuleResult] = []
    with conn.cursor() as cur:
        for rule in rules:
            cur.execute(_composed(build_count_sql(rule)))
            total = int(cur.fetchone()[0])

            cur.execute(_composed(build_split_sql(rule)))
            row = cur.fetchone()
            if row is None or len(row) != 3:
                raise RuntimeError(f"{rule.name}: split query returned {row!r}, expected 3 counts")
            backfill, pre_arming, live = (int(v) for v in row)

            top_rows: list[dict[str, Any]] = []
            if total > 0:
                sql, labels = build_top_rows_sql(rule, top_n)
                cur.execute(_composed(sql))
                top_rows.extend(dict(zip(labels, row, strict=True)) for row in cur.fetchall())

            results.append(RuleResult(rule=rule, total=total, backfill=backfill,
                                      pre_arming=pre_arming, live=live, top_rows=top_rows))
    return results


# ── Rendering ───────────────────────────────────────────────────────────────


def render_markdown(results: list[RuleResult], generated_at: str,
                    trends: list[TrendResult] | None = None) -> str:
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
    unacknowledged_live = [r for r in rules_with_live if not r.rule.acknowledged]
    acknowledged_live = [r for r in rules_with_live if r.rule.acknowledged]
    lines.append(
        f"**Summary**: {total_rules} rules checked, {rules_with_violations} fired at least once, "
        f"**{len(unacknowledged_live)} fired on LIVE data**"
        + (f" (plus {len(acknowledged_live)} known and under repair)."
           if acknowledged_live else ".")
    )
    if acknowledged_live:
        lines.append("")
        lines.append("### Known, under repair")
        lines.append("")
        lines.append("These fire on purpose. They are listed so the count stays "
                     "visible, and excluded from the exit code so they cannot "
                     "hide a new problem behind a permanently red sensor.")
        lines.append("")
        lines.append("| Rule | Live | Why it is expected, and what closes it |")
        lines.append("|---|---:|---|")
        lines.extend(
            f"| `{r.rule.name}` | {r.live} | {r.rule.acknowledged} |"
            for r in sorted(acknowledged_live, key=lambda r: -r.live)
        )
    lines.append("")

    lines.append("## Rules (by violation count)")
    lines.append("")
    lines.append("| Rule | Table | Severity | Total | Backfill | Pre-arming | Live | Note |")
    lines.append("|---|---|---|---:|---:|---:|---:|---|")
    for r in sorted(results, key=lambda r: r.total, reverse=True):
        flag = " ⚠️" if r.live > 0 else ""
        pre = f"{r.pre_arming} (from {r.rule.armed_from})" if r.rule.armed_from else "—"
        lines.append(
            f"| `{r.rule.name}`{flag} | {r.rule.table} | {r.rule.severity} | {r.total} | {r.backfill} | {pre} | {r.live} | {r.rule.note} |"
        )
    lines.append("")

    lines.append("## Detail")
    lines.append("")
    for r in sorted(results, key=lambda r: r.total, reverse=True):
        lines.append(f"### `{r.rule.name}` ({r.rule.table}, {r.rule.severity}, {r.rule.tier})")
        lines.append("")
        lines.append(r.rule.note)
        lines.append("")
        if r.rule.armed_from:
            lines.append(
                f"- Total violations: **{r.total}** (backfill: {r.backfill}, "
                f"before this rule was armed on {r.rule.armed_from}: {r.pre_arming}, "
                f"live: {r.live})")
        else:
            lines.append(f"- Total violations: **{r.total}** (backfill: {r.backfill}, live: {r.live})")
        if r.top_rows:
            lines.append("- Top offending rows:")
            for row in r.top_rows:
                pairs = ", ".join(f"{k}={v}" for k, v in row.items())
                lines.append(f"  - {pairs}")
        lines.append("")

    if trends:
        lines.extend(render_trend_markdown(trends))

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


def render_json(results: list[RuleResult], generated_at: str,
                trends: list[TrendResult] | None = None) -> str:
    trends = trends or []
    payload = {
        "generated_at": generated_at,
        "provenance_cutoff": PROVENANCE_CUTOFF,
        "rules_checked": len(results),
        "rules_with_live_violations": sum(1 for r in results if r.live > 0),
        "rules": [r.to_dict() for r in results],
        "trend_rules_checked": len(trends),
        "trend_rules_with_unexplained_shifts": unexplained_shift_count(trends),
        "trends": [r.to_dict() for r in trends],
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
    validate_trend_rules(TREND_RULES)

    conn = get_connection()
    try:
        results = run_audit(conn, RULES, top_n=args.top)
        trends = run_trend_audit(conn, TREND_RULES)
    finally:
        conn.close()

    generated_at = datetime.now(timezone.utc).date().isoformat()

    if args.json:
        print(render_json(results, generated_at, trends))
    else:
        report = render_markdown(results, generated_at, trends)
        print(report)
        out_path = args.output or (_REPO_ROOT / "docs" / "research" / f"DATA_PLAUSIBILITY_T1_{generated_at}.md")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"\nReport written to {out_path}", file=sys.stderr)

    return unacknowledged_live_count(results) + unexplained_shift_count(trends)


if __name__ == "__main__":
    sys.exit(main())
