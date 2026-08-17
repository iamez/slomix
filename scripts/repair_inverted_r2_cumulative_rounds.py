#!/usr/bin/env python3
"""repair_inverted_r2_cumulative_rounds.py — heal R2 rows imported before their R1.

When an R2 stats file is imported BEFORE its R1 (r2.id < r1.id for the same
match_id), the parser has nothing to subtract, so the stored R2 row keeps the
file's raw CUMULATIVE values (R1+R2 combined). Those rows then poison every
per-round surface — the 2026-02-06 delivery R2 held the site-wide damage
"record" (7,849 = bronze's R1 4,644 + real R2 3,205) and the kills "record"
(42 = 31 + 11).

The repair does NOT guess: it re-parses the ORIGINAL R2 stats file with the
production parser (bot.community_stats_parser), which recomputes the true
differential from the R1 file on disk, and rewrites the affected
player_comprehensive_stats and weapon_comprehensive_stats rows with exactly
the values a correctly-ordered import would have produced (same field mapping
as bot/services/stats_import_mixin._insert_player_stats).

    python scripts/repair_inverted_r2_cumulative_rounds.py            # dry-run
    python scripts/repair_inverted_r2_cumulative_rounds.py --apply    # write

Every run (dry or not) writes two artifacts next to nothing important:
    /tmp-style scratch is NOT used — artifacts go to --artifact-dir (default
    ./r2_repair_artifacts/): a row backup (pre-repair values as INSERT
    statements) and a portable repair .sql with literal values, so the same
    fix can be applied on production without needing the stats files there.

DB connection comes from POSTGRES_* env vars (same names as the bot/.env).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import glob
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Column -> how to pull it from a parsed differential player dict. This is the
# stats subset of the importer's 53-column INSERT (identity columns — round_id,
# guid, names, team, map, date — are intentionally NOT touched).
# fmt: off
_PCS_STAT_COLUMNS = [
    "kills", "deaths", "damage_given", "damage_received",
    "team_damage_given", "team_damage_received",
    "gibs", "self_kills", "team_kills", "team_gibs",
    "headshot_kills", "headshots",
    "time_played_seconds", "time_played_minutes",
    "time_dead_minutes", "time_dead_ratio", "time_played_percent",
    "xp", "kd_ratio", "dpm", "efficiency",
    "bullets_fired", "accuracy",
    "kill_assists",
    "objectives_stolen", "objectives_returned",
    "dynamites_planted", "dynamites_defused",
    "times_revived", "revives_given",
    "most_useful_kills", "useless_kills", "kill_steals",
    "denied_playtime", "constructions", "tank_meatshield",
    "double_kills", "triple_kills", "quad_kills", "multi_kills", "mega_kills",
    "killing_spree_best", "death_spree_worst",
]
# fmt: on


def _build_stat_values(player: dict) -> dict:
    """Mirror bot/services/stats_import_mixin._insert_player_stats exactly."""
    obj = player.get("objective_stats", {}) or {}

    time_seconds = player.get("time_played_seconds", 0)
    time_minutes = time_seconds / 60.0 if time_seconds > 0 else 0.0
    kills = player.get("kills", 0)
    deaths = player.get("deaths", 0)
    kd_ratio = kills / deaths if deaths > 0 else float(kills)
    efficiency = (kills / (kills + deaths) * 100) if (kills + deaths) > 0 else 0.0

    raw_td_ratio = obj.get("time_dead_ratio", 0) or 0
    td_percent = raw_td_ratio * 100.0 if 0 < raw_td_ratio <= 1 else float(raw_td_ratio)
    raw_dead_minutes = obj.get("time_dead_minutes", 0) or 0
    lua_time_minutes = obj.get("time_played_minutes", 0) or 0
    time_for_ratio = lua_time_minutes if lua_time_minutes > 0 else time_minutes
    if raw_dead_minutes <= 0 and td_percent > 0 and time_for_ratio > 0:
        raw_dead_minutes = time_for_ratio * (td_percent / 100.0)
    if td_percent <= 0 and raw_dead_minutes > 0 and time_for_ratio > 0:
        td_percent = (raw_dead_minutes / time_for_ratio) * 100.0

    return {
        "kills": kills,
        "deaths": deaths,
        "damage_given": player.get("damage_given", 0),
        "damage_received": player.get("damage_received", 0),
        "team_damage_given": obj.get("team_damage_given", 0),
        "team_damage_received": obj.get("team_damage_received", 0),
        "gibs": obj.get("gibs", 0),
        "self_kills": obj.get("self_kills", 0),
        "team_kills": obj.get("team_kills", 0),
        "team_gibs": obj.get("team_gibs", 0),
        "headshot_kills": obj.get("headshot_kills", 0),
        "headshots": player.get("headshots", 0),
        "time_played_seconds": time_seconds,
        "time_played_minutes": time_minutes,
        "time_dead_minutes": raw_dead_minutes,
        "time_dead_ratio": td_percent,
        "time_played_percent": float(obj.get("time_played_percent", 0) or 0),
        "xp": obj.get("xp", 0),
        "kd_ratio": kd_ratio,
        "dpm": player.get("dpm", 0.0),
        "efficiency": efficiency,
        "bullets_fired": obj.get("bullets_fired", 0),
        "accuracy": player.get("accuracy", 0.0),
        "kill_assists": obj.get("kill_assists", 0),
        "objectives_stolen": obj.get("objectives_stolen", 0),
        "objectives_returned": obj.get("objectives_returned", 0),
        "dynamites_planted": obj.get("dynamites_planted", 0),
        "dynamites_defused": obj.get("dynamites_defused", 0),
        "times_revived": obj.get("times_revived", 0),
        "revives_given": obj.get("revives_given", 0),
        "most_useful_kills": obj.get("useful_kills", 0),
        "useless_kills": obj.get("useless_kills", 0),
        "kill_steals": obj.get("kill_steals", 0),
        "denied_playtime": obj.get("denied_playtime", 0),
        "constructions": obj.get("repairs_constructions", 0),
        "tank_meatshield": obj.get("tank_meatshield", 0),
        "double_kills": obj.get("multikill_2x", 0),
        "triple_kills": obj.get("multikill_3x", 0),
        "quad_kills": obj.get("multikill_4x", 0),
        "multi_kills": obj.get("multikill_5x", 0),
        "mega_kills": obj.get("multikill_6x", 0),
        "killing_spree_best": obj.get("killing_spree", 0),
        "death_spree_worst": obj.get("death_spree", 0),
    }


# Columns that are cumulative in a raw R2 row and therefore healable by
# subtracting the stored R1 row (used only when the R1 STATS FILE is gone but
# the R1 round exists in the DB and the R2 row is file-proven raw cumulative).
# R2-only columns (xp, sprees, multikills, revives, denied_playtime, …) reset
# between rounds and must be kept; time columns are kept because captures of
# this era store per-round time (subtracting would clamp to 0).
_DB_SUBTRACT_COLUMNS = [
    "kills", "deaths", "damage_given", "damage_received",
    "team_damage_given", "team_damage_received",
    "gibs", "self_kills", "team_kills", "team_gibs",
    "headshots", "bullets_fired",
]


def _backup_round(cur, r2_id: int, backup_lines: list[str]) -> None:
    for table in ("player_comprehensive_stats", "weapon_comprehensive_stats"):
        cur.execute(f"SELECT * FROM {table} WHERE round_id = %s", (r2_id,))  # noqa: S608 # nosec B608 # nosemgrep: table name from fixed tuple
        cols = [d[0] for d in cur.description]
        for row in cur.fetchall():
            vals = ", ".join(_sql_literal(v) for v in row)
            backup_lines.append(
                f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({vals});"
            )


def _heal_suspect_by_db_subtraction(cur, pair: dict, repair_lines: list[str]) -> int:
    """R2_new = max(0, R2_stored - R1_stored) for cumulative columns, plus
    recomputed derived fields; weapon rows likewise. Only safe because the
    raw-file discriminator has already proven the stored R2 row IS the raw
    cumulative and the R1 round was imported from its own file."""
    cols = ", ".join(_DB_SUBTRACT_COLUMNS)
    cur.execute(  # nosemgrep: fixed column list, %s params
        f"SELECT player_guid, {cols}, time_played_seconds "  # noqa: S608 # nosec B608 - fixed column list
        "FROM player_comprehensive_stats WHERE round_id = %s",
        (pair["r1_id"],),
    )
    r1_rows = {row[0]: row[1:] for row in cur.fetchall()}
    cur.execute(  # nosemgrep: fixed column list, %s params
        f"SELECT player_guid, {cols}, time_played_seconds "  # noqa: S608 # nosec B608 - fixed column list
        "FROM player_comprehensive_stats WHERE round_id = %s",
        (pair["r2_id"],),
    )
    healed = 0
    for row in cur.fetchall():
        guid = row[0]
        if guid not in r1_rows:
            continue
        r1_vals = r1_rows[guid]
        new = {c: max(0, row[i + 1] - r1_vals[i])
               for i, c in enumerate(_DB_SUBTRACT_COLUMNS)}
        tps = row[len(_DB_SUBTRACT_COLUMNS) + 1] or 0
        kills, deaths = new["kills"], new["deaths"]
        new["kd_ratio"] = kills / deaths if deaths > 0 else float(kills)
        new["dpm"] = (new["damage_given"] / (tps / 60.0)) if tps > 0 else 0.0
        new["efficiency"] = (kills / (kills + deaths) * 100) if (kills + deaths) > 0 else 0.0

        # weapon rows: per-weapon subtraction, then player accuracy from totals
        cur.execute(
            "SELECT weapon_name, kills, deaths, headshots, hits, shots "
            "FROM weapon_comprehensive_stats "
            "WHERE round_id = %s AND player_guid = %s",
            (pair["r1_id"], guid),
        )
        w1 = {r[0]: r[1:] for r in cur.fetchall()}
        cur.execute(
            "SELECT weapon_name, kills, deaths, headshots, hits, shots "
            "FROM weapon_comprehensive_stats "
            "WHERE round_id = %s AND player_guid = %s",
            (pair["r2_id"], guid),
        )
        tot_hits = tot_shots = 0
        for wname, wk, wd, wh, whits, wshots in cur.fetchall():
            b = w1.get(wname, (0, 0, 0, 0, 0))
            nk, nd, nh = max(0, wk - b[0]), max(0, wd - b[1]), max(0, wh - b[2])
            nhits, nshots = max(0, whits - b[3]), max(0, wshots - b[4])
            tot_hits += nhits
            tot_shots += nshots
            wacc = (nhits / nshots * 100) if nshots > 0 else 0.0
            cur.execute(
                "UPDATE weapon_comprehensive_stats SET kills=%s, deaths=%s, "
                "headshots=%s, hits=%s, shots=%s, accuracy=%s "
                "WHERE round_id=%s AND player_guid=%s AND weapon_name=%s",
                (nk, nd, nh, nhits, nshots, wacc, pair["r2_id"], guid, wname),
            )
            repair_lines.append(
                f"UPDATE weapon_comprehensive_stats SET kills={nk}, deaths={nd}, "
                f"headshots={nh}, hits={nhits}, shots={nshots}, "
                f"accuracy={round(wacc, 6)} WHERE round_id={pair['r2_id']} "
                f"AND player_guid={_sql_literal(guid)} "
                f"AND weapon_name={_sql_literal(wname)};"
            )
        new["accuracy"] = (tot_hits / tot_shots * 100) if tot_shots > 0 else 0.0

        set_sql = ", ".join(f"{c} = %s" for c in new)
        cur.execute(
            f"UPDATE player_comprehensive_stats SET {set_sql} "  # noqa: S608 # nosec B608 - fixed column list
            "WHERE round_id = %s AND player_guid = %s",
            [*new.values(), pair["r2_id"], guid],
        )
        repair_lines.append(
            "UPDATE player_comprehensive_stats SET "
            + ", ".join(f"{c} = {_sql_literal(v)}" for c, v in new.items())
            + f" WHERE round_id = {pair['r2_id']} AND player_guid = {_sql_literal(guid)};"
        )
        healed += 1
        print(f"  db-subtract {guid:10s} kills {row[1]:>3} -> {kills:>3}   "
              f"dmg {row[3]:>5} -> {new['damage_given']:>5}")
    return healed


def _connect(readonly: bool):
    import psycopg2

    required = ("POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DATABASE",
                "POSTGRES_USER", "POSTGRES_PASSWORD")
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
    conn.set_session(readonly=readonly, autocommit=False)
    return conn


def _find_inverted_pairs(cur) -> list[dict]:
    cur.execute(  # nosemgrep: fixed column list, %s params
        """
        SELECT r2.id, r1.id, r2.map_name, r2.round_date::date::text, r2.match_id
        FROM rounds r1
        JOIN rounds r2 ON r2.match_id = r1.match_id
             AND r1.round_number = 1 AND r2.round_number = 2
        WHERE r2.id < r1.id
        ORDER BY r2.id
        """
    )
    return [
        {"r2_id": a, "r1_id": b, "map": c, "date": d, "match_id": e,
         "kind": "inverted"}
        for a, b, c, d, e in cur.fetchall()
    ]


def _find_suspect_pairs(cur) -> list[dict]:
    """Properly paired matches where EVERY shared player has R2 kills >= R1
    kills and R2 damage >= R1 damage (4+ shared players). A genuine R2 almost
    never has the whole lobby beating its own R1 on both axes — but a raw
    cumulative row always does. The raw-file discriminator makes the final
    call; this query only nominates."""
    cur.execute(  # nosemgrep: fixed column list, %s params
        """
        WITH pr AS (
            SELECT r1.id r1_id, r2.id r2_id, r2.map_name,
                   r2.round_date::date::text d, r2.match_id, r2.round_status
            FROM rounds r1
            JOIN rounds r2 ON r2.match_id = r1.match_id
                 AND r1.round_number = 1 AND r2.round_number = 2
            WHERE r2.id > r1.id
        ),
        cmp AS (
            SELECT pr.r2_id, COUNT(*) n,
                   COUNT(*) FILTER (WHERE p2.kills >= p1.kills
                                    AND p2.damage_given >= p1.damage_given) ge
            FROM pr
            JOIN player_comprehensive_stats p1 ON p1.round_id = pr.r1_id
            JOIN player_comprehensive_stats p2 ON p2.round_id = pr.r2_id
                 AND p2.player_guid = p1.player_guid
            GROUP BY pr.r2_id
        )
        SELECT pr.r2_id, pr.r1_id, pr.map_name, pr.d, pr.match_id, pr.round_status
        FROM pr JOIN cmp ON cmp.r2_id = pr.r2_id
        WHERE cmp.ge = cmp.n AND cmp.n >= 4
        ORDER BY pr.r2_id
        """
    )
    return [
        {"r2_id": a, "r1_id": b, "map": c, "date": d, "match_id": e,
         "status": f, "kind": "suspect"}
        for a, b, c, d, e, f in cur.fetchall()
    ]


def _find_orphan_r2s(cur) -> list[dict]:
    """R2 rounds with no R1 round for their match_id. Every one of these went
    through the parser's orphan path (match_id == the round's own timestamp),
    so the stored row holds raw CUMULATIVE values. Healable when the original
    R1 file exists on disk today."""
    cur.execute(  # nosemgrep: fixed column list, %s params
        """
        SELECT r2.id, r2.map_name, r2.round_date::date::text, r2.match_id,
               r2.round_status
        FROM rounds r2
        WHERE r2.round_number = 2
          AND NOT EXISTS (SELECT 1 FROM rounds r1
                          WHERE r1.match_id = r2.match_id AND r1.round_number = 1)
        ORDER BY r2.id
        """
    )
    return [
        {"r2_id": a, "r1_id": None, "map": b, "date": c, "match_id": d,
         "status": e, "kind": "orphan"}
        for a, b, c, d, e in cur.fetchall()
    ]


def _locate_r2_candidates(stats_dir: Path, pair: dict) -> list[Path]:
    """Candidate R2 files for a round. An orphan's match_id IS its own file
    timestamp, so the name is fully determined; for the other kinds we glob
    same-day, same-map round-2 files (plain and -endstats variants) and let
    the raw-cumulative discriminator pick the right one by content."""
    if pair["kind"] == "orphan":
        return [
            p for suffix in (".txt", "-endstats.txt")
            if (p := stats_dir / f"{pair['match_id']}-{pair['map']}-round-2{suffix}").exists()
        ]
    return sorted(
        Path(c)
        for c in glob.glob(str(stats_dir / f"{pair['date']}-*-{pair['map']}-round-2*.txt"))
    )


def _find_r1_endstats(r2_file: Path) -> Path | None:
    """The parser's R1 finder only knows '-round-1.txt' names, but captures
    exist as '-round-1-endstats.txt' too (same TAB format — it's what the
    endstats monitor imports). Pick the nearest same-map R1-endstats file
    before the R2 timestamp, same day or the previous day, within 60 min."""
    name = r2_file.name
    parts = name.split("-")
    if len(parts) < 6:
        return None
    date = "-".join(parts[:3])
    time_part = parts[3]
    map_name = "-".join(parts[4:]).split("-round-2")[0]
    r2_dt = _dt.datetime.strptime(f"{date}-{time_part}", "%Y-%m-%d-%H%M%S")  # noqa: DTZ007 filename timestamps carry no tz

    best: tuple[float, Path] | None = None
    for day_offset in (0, 1):
        day = (r2_dt.date() - _dt.timedelta(days=day_offset)).isoformat()
        for cand in glob.glob(str(r2_file.parent / f"{day}-*-{map_name}-round-1-endstats.txt")):
            cparts = Path(cand).name.split("-")
            c_dt = _dt.datetime.strptime("-".join(cparts[:4]), "%Y-%m-%d-%H%M%S")  # noqa: DTZ007
            gap = (r2_dt - c_dt).total_seconds()
            if 0 < gap <= 3600 and (best is None or gap < best[0]):
                best = (gap, Path(cand))
    return best[1] if best else None


def _compute_differential(parser, r2_file: Path) -> dict | None:
    """Parser-first; when the parser goes orphan (its finder misses
    endstats-named R1s), retry with the endstats R1 and call the parser's
    own differential routine directly."""
    result = parser.parse_round_2_with_differential(str(r2_file))
    if not result.get("is_orphan_r2") and result.get("players"):
        return result
    r1_file = _find_r1_endstats(r2_file)
    if r1_file is None:
        return None
    r1_res = parser.parse_regular_stats_file(str(r1_file))
    r2_res = parser.parse_regular_stats_file(str(r2_file))
    if not (r1_res.get("success") and r2_res.get("success")):
        return None
    diff = parser.calculate_round_2_differential(r1_res, r2_res)
    return diff if diff.get("players") else None


def _db_rows_equal_raw_cumulative(cur, r2_id: int, raw_players: list[dict]) -> bool:
    """The evidence gate for every heal: the stored row must equal the RAW
    (cumulative) parse of the candidate file on kills AND damage for every
    shared player. If it instead equals the differential, the round was
    imported correctly (or already healed) and must not be touched."""
    cur.execute(  # nosemgrep: fixed column list, %s params
        "SELECT player_guid, kills, damage_given "
        "FROM player_comprehensive_stats WHERE round_id = %s",
        (r2_id,),
    )
    db = {g: (k, d) for g, k, d in cur.fetchall()}
    raw = {p.get("guid"): (p.get("kills", 0), p.get("damage_given", 0))
           for p in raw_players}
    shared = set(db) & set(raw)
    if len(shared) < 3:
        return False
    return all(db[g] == raw[g] for g in shared)


def _sql_literal(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(round(v, 6) if isinstance(v, float) else v)
    return "'" + str(v).replace("'", "''") + "'"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true",
                    help="write the repair to the database (default: dry-run)")
    ap.add_argument("--heal-orphans", action="store_true",
                    help="also heal orphan R2 rounds (no R1 round in DB) whose "
                         "R1 file exists on disk; unhealable ones are listed only")
    ap.add_argument("--stamp-unhealable", action="store_true",
                    help="stamp unhealable orphan R2 rounds (files gone, values "
                         "stay cumulative) with round_status='orphan_r2' so "
                         "consumers can exclude them centrally; skips rounds "
                         "already stamped or cancelled")
    ap.add_argument("--stats-dir", default=str(_REPO_ROOT / "local_stats"),
                    help="directory holding the original stats files")
    ap.add_argument("--artifact-dir", default=str(_REPO_ROOT / "r2_repair_artifacts"),
                    help="where to write the backup + portable repair SQL")
    args = ap.parse_args()

    from bot.community_stats_parser import C0RNP0RN3StatsParser

    stats_dir = Path(args.stats_dir)
    artifact_dir = Path(args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")  # noqa: DTZ005 artifact naming only

    # Always connect read-write: the dry-run EXECUTES the statements (so the
    # SQL itself is validated) and then rolls the transaction back.
    conn = _connect(readonly=False)
    cur = conn.cursor()
    pairs = _find_inverted_pairs(cur)
    print(f"Inverted R1/R2 pairs (r2.id < r1.id): {len(pairs)}")
    if args.heal_orphans:
        orphans = _find_orphan_r2s(cur)
        print(f"Orphan R2 rounds (cumulative, no R1 in DB): {len(orphans)}")
        pairs += orphans
        suspects = _find_suspect_pairs(cur)
        print(f"Suspect pairs (whole lobby R2>=R1 — file check decides): "
              f"{len(suspects)}")
        pairs += suspects
    if not pairs:
        return 0

    parser = C0RNP0RN3StatsParser()
    backup_lines: list[str] = []
    repair_lines: list[str] = [
        "-- Portable repair for R2-cumulative rows (inverted import order).",
        "-- Generated by scripts/repair_inverted_r2_cumulative_rounds.py "
        f"on {stamp} from the original stats files.",
        "BEGIN;",
    ]
    total_updates = 0

    unhealable: list[dict] = []
    already_correct = 0
    for pair in pairs:
        why = {"inverted": "imported before R1 " + str(pair.get("r1_id")),
               "orphan": "orphan — no R1 round in DB",
               "suspect": "paired, but every player R2>=R1 (cumulative smell)",
               }[pair["kind"]]
        print(f"\n=== match {pair['match_id']} {pair['map']}: "
              f"R2 round_id={pair['r2_id']} ({why})")

        result = None
        saw_candidate = False
        raw_matched = False
        for cand in _locate_r2_candidates(stats_dir, pair):
            saw_candidate = True
            raw = parser.parse_regular_stats_file(str(cand))
            if not raw.get("success"):
                continue
            if not _db_rows_equal_raw_cumulative(cur, pair["r2_id"],
                                                 raw.get("players", [])):
                continue
            raw_matched = True
            result = _compute_differential(parser, cand)
            if result is not None:
                print(f"  file: {cand.name}")
                break

        if result is None:
            if raw_matched:
                if pair["kind"] == "suspect":
                    # R1 file is gone, but the R1 ROUND is in the DB (that is
                    # what makes it a pair) — heal by DB subtraction.
                    _backup_round(cur, pair["r2_id"], backup_lines)
                    total_updates += _heal_suspect_by_db_subtraction(
                        cur, pair, repair_lines)
                    continue
                print("  !! stored row IS the raw cumulative, but no R1 file "
                      "found (plain or endstats) — cannot heal")
                unhealable.append(pair)
            elif saw_candidate:
                # The stored row does not equal any candidate file's raw
                # cumulative — it is already a differential (correct import
                # or a previous heal). NEVER classify these as unhealable:
                # on an already-healed database that would stamp healthy
                # rounds as orphan_r2.
                print("  ok — stored row is already differential; leaving "
                      "untouched")
                already_correct += 1
            else:
                print("  !! original R2 stats file not found — cannot heal")
                if pair["kind"] != "suspect":
                    unhealable.append(pair)
            continue

        _backup_round(cur, pair["r2_id"], backup_lines)

        # ---- per-player UPDATE ---------------------------------------------------
        for player in result["players"]:
            guid = player.get("guid", "")
            new_vals = _build_stat_values(player)
            cur.execute(
                "SELECT kills, damage_given FROM player_comprehensive_stats "
                "WHERE round_id = %s AND player_guid = %s",
                (pair["r2_id"], guid),
            )
            existing = cur.fetchone()
            if existing is None:
                print(f"  ?? {player.get('name')}: no DB row for guid {guid} — skipping player")
                continue
            old_kills, old_dmg = existing
            print(f"  {player.get('name'):20s} kills {old_kills:>3} -> {new_vals['kills']:>3}   "
                  f"dmg {old_dmg:>5} -> {new_vals['damage_given']:>5}")

            set_clause = ", ".join(f"{c} = %s" for c in _PCS_STAT_COLUMNS)
            params = [new_vals[c] for c in _PCS_STAT_COLUMNS]
            update_sql = (
                f"UPDATE player_comprehensive_stats SET {set_clause} "  # noqa: S608 # nosec B608 - fixed column list
                "WHERE round_id = %s AND player_guid = %s"
            )
            cur.execute(update_sql, [*params, pair["r2_id"], guid])  # nosemgrep: fixed column list, %s params
            total_updates += cur.rowcount

            literal_set = ", ".join(
                f"{c} = {_sql_literal(new_vals[c])}" for c in _PCS_STAT_COLUMNS
            )
            repair_lines.append(
                f"UPDATE player_comprehensive_stats SET {literal_set} "
                f"WHERE round_id = {pair['r2_id']} AND player_guid = {_sql_literal(guid)};"
            )

            # ---- weapon rows: replace with true differentials --------------------
            cur.execute(
                "DELETE FROM weapon_comprehensive_stats "
                "WHERE round_id = %s AND player_guid = %s",
                (pair["r2_id"], guid),
            )
            repair_lines.append(
                "DELETE FROM weapon_comprehensive_stats "
                f"WHERE round_id = {pair['r2_id']} AND player_guid = {_sql_literal(guid)};"
            )
            for weapon_name, w in (player.get("weapon_stats", {}) or {}).items():
                hits = int(w.get("hits", 0) or 0)
                shots = int(w.get("shots", 0) or 0)
                acc = (hits / shots * 100) if shots > 0 else 0.0
                row = (
                    pair["r2_id"], pair["date"], pair["map"], 2, guid,
                    player.get("name", "Unknown"), weapon_name,
                    int(w.get("kills", 0) or 0), int(w.get("deaths", 0) or 0),
                    int(w.get("headshots", 0) or 0), hits, shots, acc,
                )
                cur.execute(
                    "INSERT INTO weapon_comprehensive_stats "
                    "(round_id, round_date, map_name, round_number, player_guid, "
                    "player_name, weapon_name, kills, deaths, headshots, hits, "
                    "shots, accuracy) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    row,
                )
                repair_lines.append(
                    "INSERT INTO weapon_comprehensive_stats (round_id, round_date, "
                    "map_name, round_number, player_guid, player_name, weapon_name, "
                    "kills, deaths, headshots, hits, shots, accuracy) VALUES ("
                    + ", ".join(_sql_literal(v) for v in row) + ");"
                )

    if args.stamp_unhealable:
        to_stamp = [p for p in unhealable
                    if p["kind"] == "orphan"
                    and p.get("status") not in ("orphan_r2", "cancelled")]
        for p in to_stamp:
            cur.execute(
                "UPDATE rounds SET round_status = 'orphan_r2' WHERE id = %s",
                (p["r2_id"],),
            )
            repair_lines.append(
                f"UPDATE rounds SET round_status = 'orphan_r2' "
                f"WHERE id = {p['r2_id']};"
            )
        print(f"\nStamped round_status='orphan_r2' on {len(to_stamp)} "
              "unhealable rounds (values stay cumulative; consumers exclude "
              "them by status).")

    repair_lines.append("COMMIT;")

    if already_correct:
        print(f"\nSuspect pairs cleared by the file check (already "
              f"differential): {already_correct}")
    if unhealable:
        print(f"\nUNHEALABLE (files gone; rows keep cumulative values — "
              f"candidates for a round_status='orphan_r2' stamp, owner call): "
              f"{len(unhealable)}")
        for p in unhealable:
            print(f"  round_id={p['r2_id']} {p['match_id']} {p['map']} "
                  f"status={p.get('status', '?')}")

    backup_path = artifact_dir / f"backup-{stamp}.sql"
    repair_path = artifact_dir / f"repair-{stamp}.sql"
    backup_path.write_text("\n".join(backup_lines) + "\n")
    repair_path.write_text("\n".join(repair_lines) + "\n")
    print(f"\nBackup of pre-repair rows: {backup_path}")
    print(f"Portable repair SQL (for prod): {repair_path}")

    if args.apply:
        conn.commit()
        print(f"APPLIED: {total_updates} player rows rewritten (+ weapon rows replaced).")
    else:
        conn.rollback()
        print(f"DRY-RUN: would rewrite {total_updates} player rows (+ weapon rows). "
              "Re-run with --apply to write.")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
