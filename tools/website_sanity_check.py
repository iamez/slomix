#!/usr/bin/env python3
"""
Website-wide sanity check.

Cross-validira public API odgovore z direktnim SQL aggregate-om za vsak
ključen public endpoint. Output: pass / warn / fail status report.

Run: python3 tools/website_sanity_check.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

import os
import asyncpg  # type: ignore

API_BASE = os.getenv("WEBSITE_API_BASE", "http://localhost:8000/api")

# Visual: ANSI colors
G = "\033[32m"  # green
Y = "\033[33m"  # yellow
R = "\033[31m"  # red
B = "\033[1m"
N = "\033[0m"


def fetch(url: str, timeout: int = 10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {"error": str(e)}
    except Exception as e:
        return 0, {"error": str(e)}


async def db_conn():
    return await asyncpg.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER", "etlegacy_user"),
        password=os.getenv("DB_PASSWORD", "etlegacy_secure_2025"),
        database=os.getenv("DB_NAME", "etlegacy"),
    )


def status(level: str, msg: str):
    sym = {"pass": f"{G}✓{N}", "warn": f"{Y}⚠{N}", "fail": f"{R}✗{N}", "info": "•"}[level]
    print(f"  {sym} {msg}")


def _items_from(data):
    """Extract list from API response that's either a raw list or dict with various keys."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("leaderboard", "players", "items", "results", "rows", "data"):
            v = data.get(key)
            if isinstance(v, list):
                return v
    return []


async def check_leaderboard(conn):
    print(f"\n{B}1) LEADERBOARD (DPM all-time top 10){N}")
    code, data = fetch(f"{API_BASE}/stats/leaderboard?metric=dpm&limit=10")
    if code != 200:
        status("fail", f"HTTP {code}: {data}")
        return False

    items = _items_from(data)
    if not items:
        status("fail", f"empty: {type(data)}")
        return False

    api_top = items[0]
    api_top_name = api_top.get("name") or api_top.get("player_name", "?")
    api_top_dpm = api_top.get("value") or api_top.get("dpm") or api_top.get("metric_value", 0)
    status("pass", f"endpoint OK, {len(items)} entries")

    # SQL ground truth: filter R1/R2 only, no bots
    sql_top = await conn.fetchrow("""
        SELECT MAX(pcs.player_name) AS name, ROUND(AVG(pcs.dpm)::numeric, 2) AS avg_dpm
        FROM player_comprehensive_stats pcs
        JOIN rounds r ON r.id = pcs.round_id
        WHERE pcs.dpm > 0 AND r.round_number IN (1, 2) AND r.is_bot_round = FALSE
        GROUP BY pcs.player_guid
        ORDER BY AVG(pcs.dpm) DESC
        LIMIT 1
    """)
    if sql_top:
        status("info", f"API top: {api_top_name} (DPM={api_top_dpm}); SQL: {sql_top['name']} ({sql_top['avg_dpm']})")
    return True


async def check_records(conn):
    print(f"\n{B}2) RECORDS (all-time bests){N}")
    code, data = fetch(f"{API_BASE}/stats/records")
    if code != 200:
        status("fail", f"HTTP {code}")
        return False

    if not isinstance(data, dict):
        status("fail", f"wrong shape: {type(data)}")
        return False
    keys = list(data.keys())
    status("pass", f"endpoint OK, {len(keys)} record categories: {keys[:6]}")

    # Cross-check: highest single-round kills (R1/R2 only, no R0 summary inflation)
    sql_max_kills = await conn.fetchrow("""
        SELECT MAX(pcs.kills) AS max_kills, MAX(pcs.player_name) AS who
        FROM player_comprehensive_stats pcs
        JOIN rounds r ON r.id = pcs.round_id
        WHERE r.round_number IN (1, 2) AND r.is_bot_round = FALSE
        AND pcs.kills = (
            SELECT MAX(pcs2.kills) FROM player_comprehensive_stats pcs2
            JOIN rounds r2 ON r2.id = pcs2.round_id
            WHERE r2.round_number IN (1, 2) AND r2.is_bot_round = FALSE
        )
    """)
    api_kills = data.get("kills", [{}])
    if isinstance(api_kills, list) and api_kills:
        api_kr = api_kills[0]
        api_val = api_kr.get("value")
        api_who = api_kr.get("player")
        match_sym = "✓" if str(api_val) == str(sql_max_kills["max_kills"]) else "⚠"
        status("info", f"top kills: API={api_who}({api_val}), SQL={sql_max_kills['who']}({sql_max_kills['max_kills']}) {match_sym}")
    else:
        status("warn", f"kills record shape: {type(api_kills)}")
    return True


async def check_maps(conn):
    print(f"\n{B}3) MAPS (per-map stats){N}")
    code, data = fetch(f"{API_BASE}/stats/maps")
    if code != 200:
        status("fail", f"HTTP {code}")
        return False

    items = _items_from(data) or (data.get("maps", []) if isinstance(data, dict) else [])
    if not items:
        status("fail", "empty")
        return False
    status("pass", f"{len(items)} maps returned")

    # Cross-check rounds count
    sql = await conn.fetch("""
        SELECT map_name, COUNT(*) AS rounds_played
        FROM rounds
        WHERE map_name IS NOT NULL AND round_number IN (1, 2)
        GROUP BY map_name
        ORDER BY rounds_played DESC
        LIMIT 5
    """)
    sql_top = {r['map_name']: r['rounds_played'] for r in sql}

    # Find API's first map and compare counts
    if items and isinstance(items[0], dict):
        api_map = items[0]
        mname = api_map.get("map_name") or api_map.get("name", "?")
        rcount = api_map.get("rounds_played") or api_map.get("total_rounds") or api_map.get("rounds", "?")
        sql_count = sql_top.get(mname, "missing")
        match = "✓" if rcount == sql_count else f"⚠ API={rcount}, SQL={sql_count}"
        status("info", f"top map '{mname}': rounds_played={rcount} (SQL={sql_count}) {match}")
    return True


async def check_sessions(conn):
    print(f"\n{B}4) SESSIONS (recent){N}")
    code, data = fetch(f"{API_BASE}/stats/sessions?limit=5")
    if code != 200:
        status("fail", f"HTTP {code}")
        return False
    items = _items_from(data) or (data.get("sessions", []) if isinstance(data, dict) else [])
    if not items:
        status("fail", f"empty: {type(data)}")
        return False
    status("pass", f"{len(items)} recent sessions")
    s0 = items[0]
    sd = s0.get("session_date") or s0.get("date") or "?"
    rounds = s0.get("rounds") or s0.get("total_rounds") or s0.get("rounds_count", "?")
    status("info", f"latest session: date={sd}, rounds={rounds}")

    # Cross-check rounds count for that session — sd as date for asyncpg
    if sd != "?":
        from datetime import date as date_t, datetime as datetime_t
        sd_date = sd if isinstance(sd, date_t) else datetime_t.strptime(str(sd)[:10], "%Y-%m-%d").date()
        sql_rounds = await conn.fetchval(
            "SELECT COUNT(DISTINCT round_id) FROM proximity_kill_outcome WHERE session_date = $1",
            sd_date
        )
        status("info", f"  SQL rounds for {sd}: {sql_rounds}")
    return True


async def check_weapons(conn):
    print(f"\n{B}5) WEAPONS (top weapon stats){N}")
    code, data = fetch(f"{API_BASE}/stats/weapons?limit=10")
    if code != 200:
        status("fail", f"HTTP {code}")
        return False
    items = _items_from(data) or (data.get("weapons", []) if isinstance(data, dict) else [])
    if not items:
        status("warn", f"empty result: keys={list(data.keys()) if isinstance(data,dict) else '-'}")
        return True
    status("pass", f"{len(items)} weapon entries")

    # Spot-check: weapon with most kills should have ≥1 kills
    if isinstance(items, list) and items and isinstance(items[0], dict):
        w0 = items[0]
        wname = w0.get("weapon") or w0.get("name", "?")
        wkills = w0.get("kills") or w0.get("total_kills", 0)
        status("info", f"top weapon: {wname} = {wkills} kills")
    return True


async def check_skill_leaderboard(conn):
    print(f"\n{B}6) ET RATING (skill leaderboard){N}")
    code, data = fetch(f"{API_BASE}/skill/leaderboard?limit=10")
    if code != 200:
        status("fail", f"HTTP {code}")
        return False
    items = _items_from(data)
    if not items:
        status("fail", f"empty: keys={list(data.keys()) if isinstance(data,dict) else '-'}")
        return False
    status("pass", f"{len(items)} players rated")

    sql_count = await conn.fetchval("SELECT COUNT(*) FROM player_skill_ratings")
    api_count_total = data.get("total") if isinstance(data, dict) else None
    api_count_total = api_count_total or len(items)
    status("info", f"rated players: API={api_count_total}, SQL={sql_count}")

    top = items[0]
    name = top.get("player_name") or top.get("name") or top.get("display_name") or "?"
    rating = (top.get("rating") or top.get("composite_rating")
              or top.get("skill_rating") or top.get("score") or "?")
    status("info", f"top: {name} (rating={rating}); fields={list(top.keys())[:6]}")
    return True


async def check_hall_of_fame(conn):
    print(f"\n{B}7) HALL OF FAME{N}")
    code, data = fetch(f"{API_BASE}/hall-of-fame")
    if code != 200:
        status("fail", f"HTTP {code}")
        return False
    if not isinstance(data, dict):
        status("fail", f"shape: {type(data)}")
        return False
    keys = list(data.keys())
    status("pass", f"{len(keys)} categories: {keys[:5]}...")
    # Sniff for empty arrays
    empties = [k for k, v in data.items() if isinstance(v, list) and not v]
    if empties:
        status("warn", f"empty categories: {empties}")
    return True


async def check_awards(conn):
    print(f"\n{B}8) AWARDS{N}")
    code, data = fetch(f"{API_BASE}/awards/leaderboard?limit=10")
    if code != 200:
        status("fail", f"HTTP {code}")
        return False
    items = data.get("leaderboard") or data.get("awards") or data
    if not isinstance(items, list):
        items = items if isinstance(items, list) else []
    if not items:
        status("warn", "empty")
        return True
    status("pass", f"{len(items)} entries")
    return True


async def check_quick_leaders(conn):
    print(f"\n{B}9) QUICK LEADERS (homepage widget){N}")
    code, data = fetch(f"{API_BASE}/stats/quick-leaders")
    if code != 200:
        status("fail", f"HTTP {code}")
        return False
    if not isinstance(data, dict):
        status("fail", f"shape: {type(data)}")
        return False
    keys = list(data.keys())
    status("pass", f"{len(keys)} leader categories: {keys[:6]}")
    # Each category should have ≥1 entry
    for k, v in data.items():
        if isinstance(v, list) and not v:
            status("warn", f"category '{k}' empty")
    return True


async def check_rivalries(conn):
    print(f"\n{B}10) RIVALRIES{N}")
    code, data = fetch(f"{API_BASE}/rivalries/leaderboard?limit=10")
    if code != 200:
        status("fail", f"HTTP {code}")
        return False
    items = data.get("rivalries") or data.get("leaderboard") or data
    if not isinstance(items, list) or not items:
        status("warn", f"empty/shape: keys={list(data.keys()) if isinstance(data,dict) else '-'}")
        return True
    status("pass", f"{len(items)} rivalry pairs")
    return True


async def check_overview(conn):
    print(f"\n{B}11) OVERVIEW (homepage stats){N}")
    code, data = fetch(f"{API_BASE}/stats/overview")
    if code != 200:
        status("fail", f"HTTP {code}")
        return False
    if not isinstance(data, dict):
        status("fail", "shape")
        return False
    keys = list(data.keys())
    status("pass", f"{len(keys)} fields: {keys}")

    # Critical canary: total_rounds + total_kills vs SQL (R1/R2 only, no R0 inflation)
    api_rounds = data.get("rounds") or data.get("total_rounds")
    sql_rounds = await conn.fetchval(
        "SELECT COUNT(*) FROM rounds WHERE round_number IN (1, 2) AND is_bot_round = FALSE"
    )
    sql_kills = await conn.fetchval("""
        SELECT SUM(pcs.kills) FROM player_comprehensive_stats pcs
        JOIN rounds r ON r.id = pcs.round_id
        WHERE r.round_number IN (1, 2) AND r.is_bot_round = FALSE
    """)
    api_kills = data.get("total_kills") or data.get("kills_total")

    rounds_match = "✓" if api_rounds and abs(int(api_rounds) - int(sql_rounds)) <= 5 else "⚠"
    kills_match = "✓" if api_kills and abs(int(api_kills) - int(sql_kills)) <= 100 else "⚠"
    status("info", f"rounds: API={api_rounds}, SQL={sql_rounds} {rounds_match}")
    status("info", f"kills: API={api_kills}, SQL={sql_kills} {kills_match}")
    return True


async def check_activity_calendar(conn):
    print(f"\n{B}12) ACTIVITY CALENDAR (90-day heatmap){N}")
    code, data = fetch(f"{API_BASE}/stats/activity-calendar?days=90")
    if code != 200:
        status("fail", f"HTTP {code}")
        return False
    activity = data.get("activity", {}) if isinstance(data, dict) else {}
    if not isinstance(activity, dict):
        status("warn", f"unexpected: {type(activity)}")
        return True
    active_days = [(k, v) for k, v in activity.items() if v and v > 0]
    status("pass", f"{data.get('days', '?')}-day window, {len(active_days)} days with activity")

    # Cross-check against SQL
    if active_days:
        # Pick most recent active day, verify rounds count
        sample_day, api_rounds = sorted(active_days)[-1]
        sql_rounds = await conn.fetchval("""
            SELECT COUNT(*) FROM rounds
            WHERE round_number IN (1, 2)
              AND (round_status IN ('completed', 'substitution') OR round_status IS NULL)
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) = $1
        """, sample_day)
        match_sym = "✓" if api_rounds == sql_rounds else "⚠"
        status("info", f"{sample_day}: API={api_rounds}, SQL={sql_rounds} {match_sym}")
    return True


async def check_player_profile_consistency(conn):
    print(f"\n{B}13) PLAYER PROFILE CONSISTENCY{N}")
    code, lb = fetch(f"{API_BASE}/stats/leaderboard?metric=kills&limit=1")
    if code != 200:
        status("fail", f"leaderboard HTTP {code}")
        return False
    items = _items_from(lb)
    if not items:
        status("fail", "leaderboard empty")
        return False
    top = items[0]
    name = top.get("name") or top.get("player_name") or "?"
    api_kills = top.get("value") or top.get("kills") or top.get("total_kills") or 0

    if name == "?":
        status("warn", "no name in leaderboard top entry")
        return True

    code2, profile = fetch(f"{API_BASE}/stats/player/{urllib.parse.quote(name)}")
    if code2 != 200:
        status("warn", f"profile HTTP {code2} for '{name}'")
        return True
    profile_kills = (profile.get("total_kills") or profile.get("kills")
                     or (profile.get("stats", {}).get("kills") if isinstance(profile.get("stats"), dict) else None)
                     or (profile.get("totals", {}).get("kills") if isinstance(profile.get("totals"), dict) else None)
                     or "?")
    sql_guid = await conn.fetchval(
        "SELECT player_guid FROM player_comprehensive_stats WHERE player_name = $1 LIMIT 1",
        name
    )
    sql_kills = None
    if sql_guid:
        sql_kills = await conn.fetchval("""
            SELECT SUM(pcs.kills) FROM player_comprehensive_stats pcs
            JOIN rounds r ON r.id = pcs.round_id
            WHERE pcs.player_guid = $1 AND r.round_number IN (1, 2) AND r.is_bot_round = FALSE
        """, sql_guid)
    match_sym = ""
    try:
        if profile_kills != "?" and sql_kills:
            match_sym = "✓" if abs(int(profile_kills) - int(sql_kills)) <= 50 else "⚠"
    except (ValueError, TypeError):
        pass
    status("info", f"'{name}': leaderboard={api_kills}, profile={profile_kills}, SQL R1+R2={sql_kills} {match_sym}")
    return True


async def main():
    conn = await db_conn()
    try:
        print(f"{B}=== Website Sanity Check ==={N}")
        print(f"API: {API_BASE}")

        checks = [
            check_leaderboard, check_records, check_maps, check_sessions,
            check_weapons, check_skill_leaderboard, check_hall_of_fame,
            check_awards, check_quick_leaders, check_rivalries,
            check_overview, check_activity_calendar,
            check_player_profile_consistency,
        ]
        passed = 0
        for c in checks:
            try:
                if await c(conn):
                    passed += 1
            except Exception as e:
                status("fail", f"{c.__name__} EXCEPTION: {e}")

        print(f"\n{B}=== Result: {passed}/{len(checks)} checks ran successfully ==={N}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
