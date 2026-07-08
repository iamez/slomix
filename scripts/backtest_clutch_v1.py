#!/usr/bin/env python3
"""All-Seeing Eye clutch-v1 backtest (READ-ONLY): adds a DIFFICULTY multiplier
on top of the v0 formula from scripts/backtest_clutch_detector.py, and
documents an own-goal DATA-GAP finding (owner answer A1).

v0 (unchanged, PR #453/K2):
    chain value = KIS_sum x N_mult(1v2 1.3 / 1v3 1.7 / 1v4+ 2.2)
                  x stake_mult (carrier/objective flag, R2 time-to-beat pressure)
                  x outcome_mult (won 1.5 / lost 0.6) x (1.25 if docs returned <=30s)

v1 adds (owner A1, "reward clutches AND other great plays... but I don't know
how" -> evidence first):
    DIFFICULTY multiplier = 1 + min(1, solo_before_first_kill_s / 15) * 0.5
    (solo-duration probe, scripts/backtest_help_harm_ledger.py: median 2.1s,
    p75 4.5s, max 21.6s across 103 chains; 19% instant vs 81% endured-solo —
    an endured, longer-solo clutch is objectively harder than an instant one
    right after the side drops to 1). Range: 1.0x (instant) .. 1.5x (>=15s solo).

Own-goal ("se zgodi, ne-namerno" — accidentally helping the enemy), OWNER
ANSWER A1 PART (c): INVESTIGATED, NOT BUILDABLE YET. proximity_combat_position
logs event_type='kill' for 30,854 rows and NONE have attacker_team =
victim_team — the Lua tracker does not emit team-kill events into the
per-event combat log at all (client-side filtered before it reaches
combat_position). team_kills/team_gibs exist ONLY as per-round aggregate
counts (player_comprehensive_stats), with no timestamp, so a "TK near an
objective-critical moment" detector (the K-B2 case-control pattern) cannot
be built from current data. The aggregate rate IS available and already
surfaced in the help/harm ledger (backtest_help_harm_ledger.py) — that
stays a SESSION-level signal, not a per-clutch-event multiplier, until the
Lua tracker is extended to log TK events with timing.

Golden check: qmr 2026-04-07 R2 te_escape2 was carried forward from an
earlier probe as "3 kills / 13.25s as last man". RE-VERIFIED here against
raw alive-count data and it does NOT reconstruct: qmr's team (AXIS) sits at
axis_alive IN (2, 2, 1, 3) across their four R2 kills that round — only ONE
kill (at 46.9s, axis_alive=1) happens while qmr is genuinely the side's last
man. This is not a join dropout (the earlier K1 note guessed KIS join
failure); it is a real mismatch between the "3 kills in 13.25s" narrative
and what alive-count-based last-man detection actually finds for this date.
Flagged honestly rather than silently declared passing — worth chasing only
if the owner can point at the exact intended clip/timestamp for re-derivation.

Usage: PGPASSWORD=... python3 scripts/backtest_clutch_v1.py
"""
from __future__ import annotations

import asyncio
import os
from collections import defaultdict

import asyncpg

FORMULA_VERSION = "clutch-v1.0"
CHAIN_WINDOW_MS = 20_000
N_MULT = {2: 1.3, 3: 1.7}          # 4+ -> 2.2
OUT_WIN, OUT_LOSS = 1.5, 0.6
RETURN_BONUS = 0.25
DIFFICULTY_SOLO_CAP_S = 15.0
DIFFICULTY_MAX_BONUS = 0.5


def n_mult(enemies: int) -> float:
    return N_MULT.get(enemies, 2.2 if enemies >= 4 else 1.0)


def difficulty_mult(solo_s: float | None) -> float:
    """1.0 (instant clutch) .. 1.5 (endured >=15s solo before first kill)."""
    if solo_s is None:
        return 1.0
    return 1.0 + min(1.0, solo_s / DIFFICULTY_SOLO_CAP_S) * DIFFICULTY_MAX_BONUS


async def main() -> None:
    conn = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DATABASE", "etlegacy"),
        user=os.environ.get("POSTGRES_USER", "etlegacy_user"),
        password=os.environ.get("POSTGRES_PASSWORD") or os.environ.get("PGPASSWORD", ""))
    await conn.execute("SET default_transaction_read_only = on")

    # ---- sanity check the own-goal data gap up front (must be TRUE) ----
    # attacker_team/victim_team can be '' (NOT NULL, empty string default) —
    # an equality check without excluding '' would match empty-vs-empty rows
    # and falsely inflate this count (codex, PR #473).
    tk_check = await conn.fetchval("""
        SELECT COUNT(*) FROM proximity_combat_position
        WHERE event_type = 'kill' AND attacker_team = victim_team
          AND attacker_team IS NOT NULL AND attacker_team != ''
    """)
    print(f"own-goal data-gap check: team-kill events in combat_position = "
          f"{tk_check} (expected 0 — confirms no per-event TK timing exists)")

    # ---- golden-check re-verification (qmr 2026-04-07 R2 te_escape2) ----
    qmr_alive = await conn.fetch("""
        SELECT MAX(cp.axis_alive) AS axis_alive
        FROM storytelling_kill_impact ki
        JOIN proximity_combat_position cp
          ON cp.round_start_unix = ki.round_start_unix
         AND UPPER(LEFT(cp.attacker_guid, 8)) = UPPER(LEFT(ki.killer_guid, 8))
         AND ABS(cp.event_time - ki.kill_time_ms) <= 300
        WHERE ki.session_date = '2026-04-07' AND ki.map_name = 'te_escape2'
          AND ki.round_number = 2 AND ki.killer_name ILIKE '%qmr%'
        GROUP BY ki.kill_time_ms ORDER BY ki.kill_time_ms
    """)
    last_man_kills = sum(1 for r in qmr_alive if r["axis_alive"] == 1)
    print(f"golden-check (qmr 2026-04-07 R2 escape2): {last_man_kills}/"
          f"{len(qmr_alive)} kills at axis_alive=1 — "
          + ("chain confirmed, see docstring" if last_man_kills >= 2 else
             "does NOT reconstruct as a 2+ last-man chain (see docstring)"))

    # Per-kill rows: KIS impact + situational flags + killer side + alive counts.
    #
    # DISTINCT ON (ki.id): a KIS row can match more than one combat_position
    # row inside the +-300ms slack window (bursts / same-tick multi-kills).
    # The old GROUP BY + MAX() aggregation silently blended fields from
    # whichever rows matched instead of picking one deterministically — the
    # SSR clutch query already guards this the same way. Ties broken by
    # closest event-time match (codex, PR #473).
    #
    # is_valid: joined via rounds so filler/orphan/bot-test rounds can't
    # contaminate the sample, matching every other backtest in this family.
    #
    # round_start_unix > 0: rows with the default/unlinked identity would
    # collapse unrelated dates/rounds into one chain-detection bucket.
    #
    # victim bot filter: only the killer side was excluded before — a human
    # killing bot opponents in a mixed round must not score as a human clutch.
    #
    # Enemy alive count: Lua records axis_alive/allies_alive AFTER handling
    # the Obituary (victim already removed), so the raw value is the PRE-kill
    # count MINUS the just-removed victim. Two consequences fixed here:
    #   1. the WHERE clause used to require BOTH sides > 0, which silently
    #      dropped the exact kill that wipes the enemy team to 0 (the actual
    #      clutch payoff!) — now only the KILLER'S OWN side is required > 0
    #      (they're alive, doing the kill; their count is unaffected by it).
    #   2. "enemies faced at this kill" is computed as post_kill_count + 1
    #      in Python below, adding the just-removed victim back — otherwise
    #      every 1vN chain was silently understated by exactly one enemy.
    #
    # Canonical round key: round_start_unix alone is not guaranteed unique
    # repo-wide (documented convention: (round_start_unix, map_name,
    # round_number) is the real identity) — join on map_name too so a KIS
    # row from an invalid/filler map can't validate against an unrelated
    # round that happens to share a start time and round number.
    #
    # Victim match: the combat_position join keyed only on (round, killer,
    # +-300ms) — an attacker with two victims inside that window could match
    # either row nondeterministically. Match victim_guid8 too.
    rows = await conn.fetch("""
        SELECT DISTINCT ON (ki.id)
               ki.session_date, ki.round_start_unix, ki.round_number, ki.map_name,
               UPPER(LEFT(ki.killer_guid, 8)) AS g8, ki.killer_name AS name,
               ki.kill_time_ms, ki.total_impact AS kis,
               ki.is_carrier_kill AS carrier, ki.is_objective_area AS obj_area,
               UPPER(cp.attacker_team) AS team,
               cp.axis_alive AS axis_alive, cp.allies_alive AS allies_alive
        FROM storytelling_kill_impact ki
        JOIN rounds r ON r.round_start_unix = ki.round_start_unix
                     AND r.round_number = ki.round_number
                     AND r.map_name = ki.map_name AND r.is_valid
        JOIN proximity_combat_position cp
          ON cp.round_start_unix = ki.round_start_unix
         AND cp.session_date = ki.session_date
         AND cp.round_number = ki.round_number
         AND cp.map_name = ki.map_name
         AND UPPER(LEFT(cp.attacker_guid, 8)) = UPPER(LEFT(ki.killer_guid, 8))
         AND UPPER(LEFT(cp.victim_guid, 8)) = UPPER(LEFT(ki.victim_guid, 8))
         AND ABS(cp.event_time - ki.kill_time_ms) <= 300
        WHERE ki.session_date >= '2026-04-01'
          AND ki.round_start_unix > 0
          AND ki.killer_guid NOT LIKE 'OMNIBOT%'
          AND ki.killer_name NOT LIKE '[BOT]%'
          AND ki.victim_guid NOT LIKE 'OMNIBOT%'
          AND COALESCE(ki.victim_name, '') NOT LIKE '[BOT]%'
          AND ((cp.attacker_team = 'AXIS' AND cp.axis_alive > 0)
            OR (cp.attacker_team = 'ALLIES' AND cp.allies_alive > 0))
        ORDER BY ki.id, ABS(cp.event_time - ki.kill_time_ms)
    """)
    rows = sorted(rows, key=lambda r: (r["round_start_unix"], r["kill_time_ms"]))

    ttb = {}
    for r in await conn.fetch("""
        SELECT r2.round_start_unix, r1.actual_duration_seconds
        FROM rounds r2 JOIN rounds r1
          ON r1.match_id = r2.match_id AND r1.round_number = 1
        WHERE r2.round_number = 2 AND r2.round_start_unix IS NOT NULL
          AND r1.actual_duration_seconds IS NOT NULL
    """):
        ttb[r[0]] = int(r[1])

    winner = {}
    for r in await conn.fetch("""
        SELECT round_start_unix, winner_team FROM rounds
        WHERE round_start_unix IS NOT NULL AND winner_team IN (1, 2)
    """):
        winner[r[0]] = int(r[1])

    # flag_team is the document COLOR (redflag/blueflag), not a side — it
    # cannot be compared against the clutcher's AXIS/ALLIES team. Capture
    # returner_team (the actual side that performed the return) instead, so
    # the bonus below can require it to match the clutcher's own side
    # (codex, PR #473 — v0 discarded this and awarded the bonus for ANY
    # return in the round, including the opponent's).
    returns = defaultdict(list)
    for r in await conn.fetch("""
        SELECT round_start_unix, UPPER(returner_team) AS returner_team, return_time
        FROM proximity_carrier_return WHERE round_start_unix IS NOT NULL
    """):
        returns[r[0]].append((r[1], int(r[2] or 0)))

    # life windows per (round, side) for the solo-duration difficulty factor
    tracks = await conn.fetch("""
        SELECT pt.round_start_unix AS rsu, pt.team,
               UPPER(LEFT(pt.player_guid, 8)) AS g8,
               pt.spawn_time_ms AS s, COALESCE(pt.death_time_ms, 2147483647) AS d
        FROM player_track pt
        JOIN rounds r ON r.id = pt.round_id AND r.is_valid
        WHERE pt.team IN ('AXIS', 'ALLIES') AND pt.round_start_unix > 0
          AND pt.spawn_time_ms >= 0
          AND pt.player_guid NOT LIKE 'OMNIBOT%'
          AND pt.player_name NOT LIKE '[BOT]%'
    """)
    lives: dict = defaultdict(list)
    for t in tracks:
        lives[(int(t["rsu"]), t["team"])].append(
            (int(t["s"]), int(t["d"]), t["g8"]))

    def solo_since(rsu: int, team: str, g8: str, t_ms: int) -> float | None:
        wins = lives.get((rsu, team))
        if not wins:
            return None
        others = [(s, d) for s, d, g in wins if g != g8]
        if not others:
            return None
        last_mate = max((d for s, d in others if s <= t_ms and d <= t_ms),
                        default=None)
        if last_mate is None:
            return None
        if any(s <= t_ms < d for s, d in others):
            return 0.0
        # player_track is per-life: cap the solo window at the CLUTCHER'S OWN
        # spawn for the life containing t_ms — if their current life started
        # after the last teammate died (a fresh respawn wave), time before
        # they existed must not count as endured solo (codex, PR #473
        # follow-up). Falls back to last_mate if no owning life is found
        # (shouldn't happen — the clutcher is alive doing this kill).
        own_spawn = next((s for s, d, g in wins if g == g8 and s <= t_ms < d),
                         None)
        start = max(last_mate, own_spawn) if own_spawn is not None else last_mate
        return max(0.0, (t_ms - start) / 1000.0)

    # ---- chain detection (per round, killer, SIDE first) ----
    # side_alive uses the killer's OWN team count directly (unaffected by
    # their own kill, no adjustment needed).
    # Keying on team too: a player who switches sides mid-round (sub, class
    # change edge case) must not have last-man kills from BOTH sides grouped
    # into one chain — the later scoring picks one team for winner/doc-return
    # bonus while still summing kills/enemy-counts from the other side.
    by_killer: dict = defaultdict(list)
    for r in rows:
        side_alive = r["axis_alive"] if r["team"] == "AXIS" else r["allies_alive"]
        if side_alive != 1:
            continue
        by_killer[(r["round_start_unix"], r["g8"], r["team"])].append(r)

    chains = []
    for krows in by_killer.values():
        krows.sort(key=lambda r: r["kill_time_ms"])
        cur = None
        for r in krows:
            # PRE-kill enemy count: the recorded value is POST-Obituary (the
            # victim of THIS kill is already removed), so add them back —
            # otherwise every 1vN chain understates N by exactly one, and a
            # full wipe's last kill (post-count 0) would show as "1v0".
            enemies_post = r["allies_alive"] if r["team"] == "AXIS" else r["axis_alive"]
            enemies = (enemies_post or 0) + 1
            if cur and r["kill_time_ms"] - cur["t1"] <= CHAIN_WINDOW_MS:
                cur["kills"].append(r)
                cur["t1"] = r["kill_time_ms"]
                cur["max_enemies"] = max(cur["max_enemies"], enemies)
            else:
                cur = {"t0": r["kill_time_ms"], "t1": r["kill_time_ms"],
                       "kills": [r], "max_enemies": enemies, "meta": r}
                chains.append(cur)

    scored = []
    for c in chains:
        if len(c["kills"]) < 2:
            continue
        m = c["meta"]
        kis_sum = sum(float(k["kis"] or 0) for k in c["kills"])
        stake = 1.0
        if any(k["carrier"] for k in c["kills"]) or any(k["obj_area"] for k in c["kills"]):
            stake *= 1.5
        rsu = m["round_start_unix"]
        if m["round_number"] == 2 and rsu in ttb:
            remaining = ttb[rsu] - c["t1"] / 1000.0
            stake *= 1.0 + max(0.0, min(1.0, 1.0 - remaining / 120.0))
        side_num = 1 if m["team"] == "AXIS" else 2
        out = OUT_WIN if winner.get(rsu) == side_num else (
            OUT_LOSS if rsu in winner else 1.0)
        v0_value = kis_sum * n_mult(c["max_enemies"]) * stake * out
        ret_note = ""
        for returner_team, rt in returns.get(rsu, []):
            # the bonus is for the CLUTCHER'S side recovering docs — an
            # opponent's return must not credit this chain (codex, PR #473)
            if returner_team != m["team"]:
                continue
            if 0 <= rt - c["t1"] <= 30_000:
                v0_value *= 1 + RETURN_BONUS
                ret_note = " +docs"
                break

        solo_s = solo_since(rsu, m["team"], m["g8"], c["t0"])
        diff = difficulty_mult(solo_s)
        v1_value = v0_value * diff

        scored.append((v1_value, v0_value, diff, solo_s, m["session_date"],
                       m["map_name"], m["round_number"], m["name"],
                       len(c["kills"]), c["max_enemies"],
                       (c["t1"] - c["t0"]) / 1000.0, ret_note, len(scored)))

    # scored rows carry a unique chain_idx (last field) — rank tables key off
    # that, never off tuple value/identity, so duplicate-looking rows (same
    # date/map/round/player/kill-count) can never collide or misrank.
    scored_v1 = sorted(scored, key=lambda row: -row[0])
    v1_rank = {row[-1]: i for i, row in enumerate(scored_v1)}
    scored_v0 = sorted(scored, key=lambda row: -row[1])
    v0_rank = {row[-1]: i for i, row in enumerate(scored_v0)}

    print(f"\n=== clutch-v1 (v0 x difficulty)  formula_version={FORMULA_VERSION} ===")
    print(f"chains(2+ kills as last man)={len(scored)}  | TOP 20 by v1 value:")
    print(f"{'v1':>6}{'v0':>7}{'diff':>6}{'solo':>6} {'date':<11}{'map':<16}"
          f"{'R':<2}{'player':<16}{'k':>2}{'1vN':>4}{'span':>6}")
    for row in scored_v1[:20]:
        v1, v0, diff, solo, d, mp, rn, name, k, n, span, ret, _idx = row
        solo_s = f"{solo:>5.1f}s" if solo is not None else "   n/a"
        print(f"{v1:>6.1f}{v0:>7.1f}{diff:>6.2f}{solo_s} {d!s:<11}{mp:<16}"
              f"{rn:<2}{name[:15]:<16}{k:>2}{'1v' + str(n):>4}{span:>5.1f}s{ret}")

    # movement: who benefits most from the difficulty multiplier (v0 rank -> v1 rank)
    gains = sorted(
        ((v0_rank[row[-1]] - v1_rank[row[-1]], row) for row in scored),
        key=lambda pair: -pair[0],
    )
    print("\nbiggest RANK gains from the difficulty multiplier (v0 -> v1):")
    for gain, row in gains[:8]:
        v1, v0, diff, solo, d, mp, rn, name, k, n, span, ret, idx = row
        if gain <= 0:
            continue
        v0_pos, v1_pos = v0_rank[idx], v1_rank[idx]
        solo_txt = f"{solo:.1f}s" if solo is not None else "n/a"
        print(f"  {name[:16]:<17} rank {v0_pos + 1:>3} -> {v1_pos + 1:>3}  "
              f"(solo {solo_txt}, diff x{diff:.2f})")

    await conn.close()


asyncio.run(main())
