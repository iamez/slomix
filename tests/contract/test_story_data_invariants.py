"""CI gate for the Smart Stats data-trust invariants (tests/contract/story_invariants.py).

Two layers, mirroring how the invariants ship:

  * TestInvariantLogic — feeds synthetic SessionContexts to evaluate() and pins
    that a CLEAN context passes every invariant while a context seeded with each
    past bug (wrong header total, a bot row, an off-roster player, a negative
    count, a NaN) trips exactly the invariant that locks that bug down. This is
    the metamorphic-gate logic itself; it needs no database and always runs.

  * TestTotalKillsConservationSQL — seeds a real, isolated PostgreSQL schema with
    a session whose rounds include a CANCELLED round and an INVALID round plus a
    bot player, then runs the same validity-gated SUM(pcs.kills) the storytelling
    header uses (#709) and asserts it equals only the non-bot kills from valid
    rounds. This is the ground-truth conservation the on-demand
    scripts/data_trust_check.py checks against live, pinned in CI. Skips when the
    test database is unavailable.

The pair is deliberately NOT a full endpoint-seeding test: driving every
storytelling panel (KIS cache, skill composite, win-contribution) from a seeded
schema would be large and brittle, and the live endpoint layer is already
covered by data_trust_check.py. Here we lock the invariant logic and the one SQL
relation the header bug turned on.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.contract.story_invariants import (  # noqa: E402
    GroundTruth,
    SessionContext,
    evaluate,
)


def _results_by_key(ctx: SessionContext) -> dict:
    return {r.invariant.key: r for r in evaluate(ctx)}


def _clean_context() -> SessionContext:
    """A trustworthy session: header matches DB, no bots, everyone on roster."""
    return SessionContext(
        gaming_session_id=1,
        panels={
            "kill_impact": {
                "total_kills": 507,
                "players": [
                    {"guid": "D8423F90F045D9D3", "name": "vid", "kills": 12},
                    {"guid": "3C0354D3AABBCCDD", "name": "SQUUAZE", "kills": 9},
                ],
            },
            "composite": {
                "players": [
                    {"player_guid": "D8423F90", "player_name": "vid", "kills": 121, "kpi": 2.5},
                    {"player_guid": "3C0354D3", "player_name": "SQUUAZE", "kills": 84, "kpi": 1.1},
                ],
            },
        },
        truth=GroundTruth(total_kills=507, roster_guids={"D8423F90", "3C0354D3"}),
    )


class TestInvariantLogic:
    def test_clean_context_passes_every_invariant(self):
        for res in evaluate(_clean_context()):
            assert res.passed, f"{res.invariant.key} unexpectedly failed: {res.violations}"

    def test_wrong_header_total_trips_conservation(self):
        ctx = _clean_context()
        ctx.panels["kill_impact"]["total_kills"] = 61  # the hero-KILLS bug
        results = _results_by_key(ctx)
        assert not results["conservation_total_kills"].passed
        # Nothing else should react to a wrong header.
        assert results["exclusion_no_bots"].passed
        assert results["scope_roster_subset"].passed

    def test_bot_row_trips_exclusion(self):
        ctx = _clean_context()
        ctx.panels["composite"]["players"].append(
            {"player_guid": "OMNIBOT01", "player_name": "[BOT] Rambo", "kills": 5}
        )
        results = _results_by_key(ctx)
        assert not results["exclusion_no_bots"].passed
        # A bot is excused from the roster-subset check (its own invariant owns it).
        assert results["scope_roster_subset"].passed

    def test_off_roster_player_trips_scope(self):
        ctx = _clean_context()
        ctx.panels["composite"]["players"].append(
            {"player_guid": "FEEDFACE", "player_name": "stranger", "kills": 7}
        )
        results = _results_by_key(ctx)
        assert not results["scope_roster_subset"].passed

    def test_negative_and_nan_trip_bounds(self):
        ctx = _clean_context()
        ctx.panels["composite"]["players"][0]["kills"] = -3
        ctx.panels["composite"]["players"][1]["kpi"] = float("nan")
        results = _results_by_key(ctx)
        assert not results["bounds_finite_nonneg"].passed
        assert len(results["bounds_finite_nonneg"].violations) == 2

    def test_tracked_exceeding_total_trips_cross_panel(self):
        ctx = _clean_context()
        # tracked KIS kills (12+9=21) must not exceed the header total.
        ctx.panels["kill_impact"]["total_kills"] = 20
        results = _results_by_key(ctx)
        assert not results["cross_panel_tracked_le_total"].passed

    def test_missing_panel_skips_not_fails(self):
        """A partial context (panel fetch failed) must not invent violations."""
        ctx = SessionContext(
            gaming_session_id=1,
            panels={"kill_impact": None},
            truth=GroundTruth(total_kills=507, roster_guids=set()),
        )
        for res in evaluate(ctx):
            assert res.passed, f"{res.invariant.key} fired on an empty context"


# ── Real-PostgreSQL conservation of the gated total_kills (#709) ───────────────

asyncpg = pytest.importorskip("asyncpg")

_TEST_DB = {
    "host": os.getenv("POSTGRES_TEST_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_TEST_PORT", "5432")),
    "database": os.getenv("POSTGRES_TEST_DATABASE", "etlegacy_test"),
    "user": os.getenv("POSTGRES_TEST_USER", "etlegacy_user"),
    "password": os.getenv("POSTGRES_TEST_PASSWORD", "etlegacy_test_password"),
}

# The exact validity gate the storytelling header + GamingSessionScope apply,
# in asyncpg ($1) paramstyle.
_GATED_TOTAL_KILLS_SQL = """
    SELECT COALESCE(SUM(pcs.kills), 0)
    FROM player_comprehensive_stats pcs
    JOIN rounds r ON r.id = pcs.round_id
    WHERE r.gaming_session_id = $1
      AND r.round_number IN (1, 2)
      AND r.is_valid IS DISTINCT FROM FALSE
      AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
      AND UPPER(pcs.player_guid) NOT LIKE 'OMNIBOT%'
      AND pcs.player_name NOT LIKE '%[BOT]%'
"""


async def _connect_or_skip():
    try:
        return await asyncpg.connect(timeout=5, **_TEST_DB)
    except (TimeoutError, OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"test PostgreSQL unavailable: {exc}")


@pytest.fixture
async def seeded_pg():
    """Isolated schema with a session that has valid, cancelled and invalid rounds
    plus a bot player — the exact adversaries the gate must exclude."""
    conn = await _connect_or_skip()
    ns = f"datatrust_{uuid.uuid4().hex[:8]}"
    await conn.execute(f"CREATE SCHEMA {ns}")
    await conn.execute(f"SET search_path TO {ns}")
    await conn.execute(
        """
        CREATE TABLE rounds (
            id INTEGER PRIMARY KEY,
            gaming_session_id INTEGER,
            round_number INTEGER,
            is_valid BOOLEAN,
            round_status VARCHAR
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE player_comprehensive_stats (
            id BIGSERIAL PRIMARY KEY,
            round_id INTEGER NOT NULL,
            player_guid TEXT NOT NULL,
            player_name TEXT NOT NULL,
            kills INTEGER
        )
        """
    )
    gsid = 9001
    # Rounds: 1&2 count; 3 cancelled, 4 invalid, 5 wrong round_number → excluded.
    await conn.executemany(
        "INSERT INTO rounds (id, gaming_session_id, round_number, is_valid, round_status)"
        " VALUES ($1, $2, $3, $4, $5)",
        [
            (1, gsid, 1, True, "completed"),
            (2, gsid, 2, True, None),           # NULL status is admitted
            (3, gsid, 1, True, "cancelled"),    # cancelled → excluded
            (4, gsid, 2, False, "completed"),   # is_valid FALSE → excluded
            (5, gsid, 3, True, "completed"),    # round_number 3 → excluded
        ],
    )
    await conn.executemany(
        "INSERT INTO player_comprehensive_stats (round_id, player_guid, player_name, kills)"
        " VALUES ($1, $2, $3, $4)",
        [
            # Real players in valid rounds — these are the ONLY kills that count.
            (1, "D8423F90", "vid", 20),
            (1, "3C0354D3", "SQUUAZE", 15),
            (2, "D8423F90", "vid", 18),
            (2, "3C0354D3", "SQUUAZE", 12),      # valid total = 65
            # Adversaries that must NOT count:
            (1, "OMNIBOT0A", "bot_axis", 40),    # bot by guid
            (2, "AAAAAAAA", "[BOT] sniper", 30),  # bot by name
            (3, "D8423F90", "vid", 99),          # cancelled round
            (4, "3C0354D3", "SQUUAZE", 99),      # invalid round
            (5, "D8423F90", "vid", 99),          # wrong round_number
        ],
    )
    try:
        yield conn, gsid
    finally:
        await conn.execute(f"DROP SCHEMA {ns} CASCADE")
        await conn.close()


@pytest.mark.asyncio
async def test_gated_total_kills_excludes_bots_cancelled_and_invalid(seeded_pg):
    conn, gsid = seeded_pg
    total = await conn.fetchval(_GATED_TOTAL_KILLS_SQL, gsid)
    # Only the 4 real-player rows in rounds 1&2: 20+15+18+12 = 65. Every bot,
    # cancelled, invalid and wrong-round row (each worth 30–99) is excluded.
    assert total == 65, (
        f"gated total_kills={total}, expected 65 — a bot/cancelled/invalid row "
        "leaked into the session header (the #709 / brewdog-miscount class)."
    )


@pytest.mark.asyncio
async def test_gate_removal_would_change_the_number(seeded_pg):
    """Guard the guard: without the validity/bot gate the number inflates, proving
    the gate is what holds conservation (a mutation test on the SQL itself)."""
    conn, gsid = seeded_pg
    ungated = await conn.fetchval(
        "SELECT COALESCE(SUM(kills), 0) FROM player_comprehensive_stats pcs "
        "JOIN rounds r ON r.id = pcs.round_id WHERE r.gaming_session_id = $1",
        gsid,
    )
    assert ungated > 65, "fixture should have excluded rows worth more than the valid total"
