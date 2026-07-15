#!/usr/bin/env python3
"""Phase-0 backtest: Slomix Museum — per-player career "memory card" (READ-ONLY).

Good Night plan rank 10 (§I). Turns a player's own history into a friendship-safe
keepsake ("rank vs yourself", not a global ladder): playing since, nights shown up,
personal-best round, best killing spree, and a *signature map* — the map where the
player most overperforms their OWN career average (not raw most-played, which is
te_escape2 for everyone on this group's data and so carries no information).

Everything is derived from player_comprehensive_stats (one row per round). Proves
with a table that the card is discriminating and defensible before any endpoint/UI.
No writes: SET default_transaction_read_only = on.
"""
import asyncio
import os
import sys

import asyncpg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from website.backend.utils.et_constants import strip_et_colors  # noqa: E402

MIN_ROUNDS_CAREER = 20     # only players with a real history get a card
MIN_ROUNDS_ON_MAP = 8      # a signature map needs enough rounds to mean anything
SIG_MIN_LIFT = 1.08        # map avg must beat the player's own avg by >=8% to qualify


async def main():
    conn = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DATABASE", "etlegacy"),
        user=os.environ.get("POSTGRES_USER", "etlegacy_user"),
        password=os.environ.get("POSTGRES_PASSWORD") or os.environ.get("PGPASSWORD", ""))
    await conn.execute("SET default_transaction_read_only = on")

    # Career spine: one row per player with the milestone facts.
    # Same scope as the shipped endpoint: valid R1/R2 rounds only. Joining rounds
    # and filtering round_number IN (1,2) excludes the round_number=0 R2 match
    # summaries the importer writes (cumulative rows that would double-count).
    careers = await conn.fetch("""
        SELECT pcs.player_guid,
               MAX(pcs.clean_name) AS name,
               MIN(CAST(r.round_date AS DATE)) AS first_seen,
               MAX(CAST(r.round_date AS DATE)) AS last_seen,
               COUNT(DISTINCT CAST(r.round_date AS DATE)) AS nights,
               COUNT(*) AS rounds,
               SUM(pcs.kills) AS career_kills,
               MAX(pcs.kills) AS best_round_kills,
               MAX(pcs.killing_spree_best) AS best_spree,
               AVG(pcs.kills::float) AS avg_kills
        FROM player_comprehensive_stats pcs JOIN rounds r ON r.id = pcs.round_id
        WHERE pcs.player_guid IS NOT NULL AND pcs.player_name NOT LIKE '[BOT]%'
          AND r.round_number IN (1, 2) AND r.is_valid IS DISTINCT FROM FALSE
        GROUP BY pcs.player_guid
        HAVING COUNT(*) >= $1
        ORDER BY nights DESC
    """, MIN_ROUNDS_CAREER)

    # Per-player, per-map averages so we can find the overperformance signature map.
    map_rows = await conn.fetch("""
        SELECT pcs.player_guid, pcs.map_name, COUNT(*) AS n, AVG(pcs.kills::float) AS avg_k
        FROM player_comprehensive_stats pcs JOIN rounds r ON r.id = pcs.round_id
        WHERE pcs.player_guid IS NOT NULL AND pcs.map_name IS NOT NULL
          AND pcs.player_name NOT LIKE '[BOT]%'
          AND r.round_number IN (1, 2) AND r.is_valid IS DISTINCT FROM FALSE
        GROUP BY pcs.player_guid, pcs.map_name
    """)
    by_player: dict[str, list] = {}
    for r in map_rows:
        by_player.setdefault(r["player_guid"], []).append(r)

    def signature_map(guid: str, career_avg: float):
        """Map with the highest avg-kills lift over the player's own career avg."""
        best = None
        for r in by_player.get(guid, []):
            if r["n"] < MIN_ROUNDS_ON_MAP or career_avg <= 0:
                continue
            lift = r["avg_k"] / career_avg
            if lift >= SIG_MIN_LIFT and (best is None or lift > best[1]):
                best = (r["map_name"], lift, r["n"])
        return best

    print("Slomix Museum — career memory card v0 (per player, rank-vs-self)")
    print(f"{'player':<16}{'since':>11}{'nights':>7}{'rounds':>7}"
          f"{'best rd':>8}{'spree':>6}  signature map (lift)")
    print("-" * 92)

    sig_maps = {}
    for c in careers:
        name = strip_et_colors(c["name"] or c["player_guid"][:8])[:15]
        sig = signature_map(c["player_guid"], c["avg_kills"] or 0.0)
        if sig:
            sig_txt = f"{sig[0]} (+{(sig[1] - 1) * 100:.0f}%, {sig[2]}r)"
            sig_maps[sig[0]] = sig_maps.get(sig[0], 0) + 1
        else:
            sig_txt = "(no standout map)"
        print(f"{name:<16}{str(c['first_seen']):>11}{c['nights']:>7}{c['rounds']:>7}"
              f"{c['best_round_kills']:>8}{c['best_spree']:>6}  {sig_txt}")

    print("-" * 92)
    print(f"players with a card: {len(careers)}")
    print(f"distinct signature maps: {len(sig_maps)} -> {dict(sorted(sig_maps.items(), key=lambda kv: -kv[1]))}")
    print("(distinct signature maps > 1 proves overperformance beats raw most-played,")
    print(" which is te_escape2 for everyone and carries no information.)")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
