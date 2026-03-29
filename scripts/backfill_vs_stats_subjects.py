#!/usr/bin/env python3
"""
Backfill subject_name / subject_guid into round_vs_stats.

Uses combat_engagement kill matrix as ground truth to identify which player
each VS block belongs to. Only processes rounds that have CE data (110 rounds).

Safety:
  - Only UPDATEs rows where subject_name IS NULL (never overwrites existing data)
  - Dry-run mode by default (--apply to actually write)
  - Validates every match against CE kill matrix before writing
  - Logs all changes for audit trail
"""
import argparse
import asyncio
import logging
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot.core.database_adapter import PostgreSQLAdapter as DatabaseAdapter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("backfill_vs_subjects")


def strip_et_colors(name: str) -> str:
    """Remove ET color codes (^X) from player names."""
    return re.sub(r'\^[0-9a-zA-Z]', '', name or '')


async def get_rounds_with_ce(db: DatabaseAdapter):
    """Get round_ids that have both vs_stats and combat_engagement data."""
    rows = await db.fetch_all("""
        SELECT DISTINCT v.round_id
        FROM round_vs_stats v
        INNER JOIN combat_engagement ce ON ce.round_id = v.round_id AND ce.outcome = 'killed'
        WHERE v.subject_name IS NULL
        ORDER BY v.round_id
    """)
    return [r[0] for r in rows] if rows else []


async def get_team_composition(db: DatabaseAdapter, round_id: int):
    """Get {clean_name: (guid, team)} for players in a round."""
    rows = await db.fetch_all("""
        SELECT player_guid, player_name, team
        FROM player_comprehensive_stats
        WHERE round_id = $1 AND round_number IN (1, 2)
        ORDER BY team, player_name
    """, (round_id,))
    if not rows:
        return {}
    result = {}
    for guid, name, team in rows:
        clean = strip_et_colors(name)
        result[clean] = (guid, int(team) if team else 0)
    return result


async def get_ce_kill_matrix(db: DatabaseAdapter, round_id: int):
    """Get {killer_guid: {target_guid: kill_count}} from combat_engagement."""
    rows = await db.fetch_all("""
        SELECT killer_guid, target_guid, COUNT(*) as kills
        FROM combat_engagement
        WHERE round_id = $1 AND outcome = 'killed' AND killer_guid IS NOT NULL
        GROUP BY killer_guid, target_guid
    """, (round_id,))
    matrix = {}
    for killer_guid, target_guid, kills in (rows or []):
        if killer_guid not in matrix:
            matrix[killer_guid] = {}
        matrix[killer_guid][target_guid] = int(kills)
    return matrix


async def get_vs_rows(db: DatabaseAdapter, round_id: int):
    """Get vs_stats rows in insertion order (id ASC)."""
    rows = await db.fetch_all("""
        SELECT id, player_name, kills, deaths
        FROM round_vs_stats
        WHERE round_id = $1 AND subject_name IS NULL
        ORDER BY id
    """, (round_id,))
    return [(int(r[0]), r[1], int(r[2]), int(r[3])) for r in rows] if rows else []


def split_into_blocks(vs_rows, team_comp):
    """Split vs_rows into blocks based on team sizes.

    Each player faces all opponents from the other team.
    Returns list of (block_rows, opponent_team, subject_team).
    """
    # Determine team sizes
    teams = {}
    for name, (guid, team) in team_comp.items():
        if team not in teams:
            teams[team] = []
        teams[team].append((name, guid))

    if len(teams) != 2:
        return None  # Can't process non-2-team rounds

    team_ids = sorted(teams.keys())
    t1_size = len(teams[team_ids[0]])
    t2_size = len(teams[team_ids[1]])

    # Total expected rows: t1_size * t2_size + t2_size * t1_size = 2 * t1 * t2
    expected = 2 * t1_size * t2_size

    if len(vs_rows) != expected:
        # Could be double-import. Try if rows are exactly 2x expected
        if len(vs_rows) == 2 * expected:
            # Use only first half (original import)
            vs_rows = vs_rows[:expected]
        else:
            return None

    # Each block has either t2_size rows (for t1 players) or t1_size rows (for t2 players)
    # First t1_size blocks have t2_size rows each, then t2_size blocks have t1_size rows
    # But actually the iteration is by slot number, not by team.
    # We need to figure out the block sizes dynamically.

    # Look at first block's opponent names to determine its size
    blocks = []
    idx = 0

    while idx < len(vs_rows):
        # Determine opponent team from first row's opponent name
        first_opponent = vs_rows[idx][1]
        first_opponent_info = team_comp.get(first_opponent)

        if first_opponent_info is None:
            # Try case-insensitive match
            for tc_name, tc_info in team_comp.items():
                if tc_name.lower() == first_opponent.lower():
                    first_opponent_info = tc_info
                    break

        if first_opponent_info is None:
            return None  # Can't identify opponent team

        opponent_team = first_opponent_info[1]
        subject_team = [t for t in team_ids if t != opponent_team][0]
        block_size = len(teams[opponent_team])

        if idx + block_size > len(vs_rows):
            return None  # Not enough rows

        block = vs_rows[idx:idx + block_size]
        blocks.append((block, opponent_team, subject_team))
        idx += block_size

    return blocks


def guid_matches(short_guid: str, long_guid: str) -> bool:
    """Check if a short GUID (8-char from PCS) matches a long GUID (32-char from CE)."""
    return long_guid.upper().startswith(short_guid.upper())


def find_ce_kills_for_guid(ce_matrix: dict, short_guid: str) -> dict:
    """Find CE kills for a short GUID by prefix-matching against full CE GUIDs."""
    for full_guid, kills in ce_matrix.items():
        if guid_matches(short_guid, full_guid):
            return kills
    return {}


def find_ce_kill_count(ce_kills: dict, short_opp_guid: str) -> int:
    """Find kill count against opponent by prefix-matching GUID."""
    for full_guid, count in ce_kills.items():
        if guid_matches(short_opp_guid, full_guid):
            return count
    return 0


def match_block_to_subject(block_rows, team_comp, ce_matrix, subject_team_players):
    """Match a block to a specific subject using CE kill matrix.

    Returns (subject_name, subject_guid, confidence) or None.
    """
    # Build block's kill signature: {opponent_name: kills}
    block_kills = {}
    for _, opponent_name, kills, deaths in block_rows:
        block_kills[opponent_name] = kills

    # Convert opponent names to short GUIDs
    block_kills_by_guid = {}
    for opp_name, kills in block_kills.items():
        opp_info = team_comp.get(opp_name)
        if opp_info is None:
            for tc_name, tc_info in team_comp.items():
                if tc_name.lower() == opp_name.lower():
                    opp_info = tc_info
                    break
        if opp_info:
            block_kills_by_guid[opp_info[0]] = kills  # short guid -> kills

    # Try each candidate subject
    best_match = None
    best_score = -1

    for subj_name, subj_guid in subject_team_players:
        ce_kills = find_ce_kills_for_guid(ce_matrix, subj_guid)

        # Compare kill counts
        match_score = 0
        mismatch = False

        for opp_short_guid, expected_kills in block_kills_by_guid.items():
            actual_kills = find_ce_kill_count(ce_kills, opp_short_guid)
            if actual_kills == expected_kills:
                match_score += 1
            else:
                mismatch = True
                break

        if not mismatch and match_score > best_score:
            best_score = match_score
            best_match = (subj_name, subj_guid, match_score)

    return best_match


async def backfill_round(db: DatabaseAdapter, round_id: int, apply: bool):
    """Backfill subjects for one round. Returns (updated_count, skipped_reason)."""

    team_comp = await get_team_composition(db, round_id)
    if not team_comp:
        return 0, "no team composition"

    ce_matrix = await get_ce_kill_matrix(db, round_id)
    if not ce_matrix:
        return 0, "no CE data"

    vs_rows = await get_vs_rows(db, round_id)
    if not vs_rows:
        return 0, "no vs_stats rows (or already backfilled)"

    # Split into blocks
    blocks = split_into_blocks(vs_rows, team_comp)
    if blocks is None:
        return 0, f"block split failed (rows={len(vs_rows)}, players={len(team_comp)})"

    # Build team player lists
    teams = {}
    for name, (guid, team) in team_comp.items():
        if team not in teams:
            teams[team] = []
        teams[team].append((name, guid))

    updates = []
    used_subjects = set()

    for block_rows, opponent_team, subject_team in blocks:
        subject_candidates = [
            (name, guid) for name, guid in teams.get(subject_team, [])
            if guid not in used_subjects
        ]

        match = match_block_to_subject(block_rows, team_comp, ce_matrix, subject_candidates)

        if match is None:
            log.warning(f"  Round {round_id}: no match for block starting at id={block_rows[0][0]}")
            continue

        subj_name, subj_guid, confidence = match
        used_subjects.add(subj_guid)

        for row_id, opp_name, kills, deaths in block_rows:
            updates.append((row_id, subj_name, subj_guid))

    if not updates:
        return 0, "no matches found"

    if apply:
        for row_id, subj_name, subj_guid in updates:
            await db.execute(
                "UPDATE round_vs_stats SET subject_name = $1, subject_guid = $2 WHERE id = $3 AND subject_name IS NULL",
                (subj_name, subj_guid, row_id),
            )
        log.info(f"  Round {round_id}: updated {len(updates)} rows")
    else:
        log.info(f"  Round {round_id}: would update {len(updates)} rows")
        # Show first block as example
        if updates:
            first_subj = updates[0][1]
            first_guid = updates[0][2]
            log.info(f"    Example: subject={first_subj} guid={first_guid}")

    return len(updates), None


async def main():
    parser = argparse.ArgumentParser(description="Backfill round_vs_stats subject columns")
    parser.add_argument("--apply", action="store_true", help="Actually write changes (default: dry-run)")
    parser.add_argument("--round-id", type=int, help="Process single round only")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of rounds to process")
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY-RUN"
    log.info(f"=== VS Stats Subject Backfill ({mode}) ===")

    db = DatabaseAdapter(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "etlegacy"),
        user=os.getenv("DB_USER", "etlegacy_user"),
        password=os.getenv("DB_PASSWORD"),
        min_pool_size=1,
        max_pool_size=3,
    )
    await db.connect()

    try:
        if args.round_id:
            round_ids = [args.round_id]
        else:
            round_ids = await get_rounds_with_ce(db)

        if args.limit > 0:
            round_ids = round_ids[:args.limit]

        log.info(f"Processing {len(round_ids)} rounds with CE data")

        total_updated = 0
        total_skipped = 0
        total_failed = 0

        for round_id in round_ids:
            count, reason = await backfill_round(db, round_id, args.apply)
            if reason:
                log.warning(f"  Round {round_id}: SKIPPED — {reason}")
                total_skipped += 1
            elif count > 0:
                total_updated += count
            else:
                total_failed += 1

        log.info(f"=== Done: {total_updated} rows {'updated' if args.apply else 'would update'}, "
                 f"{total_skipped} rounds skipped, {total_failed} failed ===")

    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
