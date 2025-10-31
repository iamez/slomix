import sqlite3
import pprint
from datetime import datetime

DB = 'bot/etlegacy_production.db'

def fetch_latest_date(conn):
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT SUBSTR(session_date,1,10) as date FROM sessions ORDER BY date DESC LIMIT 1")
    row = cur.fetchone()
    return row[0] if row else None


def fetch_sessions_for_date(conn, date):
    cur = conn.cursor()
    cur.execute("SELECT id, map_name, round_number, actual_time FROM sessions WHERE SUBSTR(session_date,1,10)=? ORDER BY id ASC", (date,))
    return cur.fetchall()


def count_unique_players(conn, session_ids):
    if not session_ids:
        return 0
    placeholders = ','.join('?'*len(session_ids))
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(DISTINCT player_guid) FROM player_comprehensive_stats WHERE session_id IN ({placeholders})", session_ids)
    return cur.fetchone()[0]


def top_players(conn, session_ids, limit=10):
    placeholders = ','.join('?'*len(session_ids))
    cur = conn.cursor()
    query = f"""
        SELECT p.player_name,
               SUM(p.kills) as kills,
               SUM(p.deaths) as deaths,
               CASE WHEN SUM(p.time_played_seconds) > 0 THEN (SUM(p.damage_given)*60.0)/SUM(p.time_played_seconds) ELSE 0 END as dpm,
               SUM(p.time_played_seconds) as total_seconds
        FROM player_comprehensive_stats p
        WHERE p.session_id IN ({placeholders})
        GROUP BY p.player_name
        ORDER BY kills DESC
        LIMIT {limit}
    """
    cur.execute(query, session_ids)
    return cur.fetchall()


def team_composition(conn, session_ids):
    placeholders = ','.join('?'*len(session_ids))
    cur = conn.cursor()
    cur.execute(f"SELECT player_name, team, COUNT(*) as rounds_played FROM player_comprehensive_stats WHERE session_id IN ({placeholders}) GROUP BY player_name, team ORDER BY player_name, rounds_played DESC", session_ids)
    rows = cur.fetchall()
    # Choose primary team per player
    primary = {}
    for player, team, rounds in rows:
        if player not in primary:
            primary[player] = team
    team1 = [p for p,t in primary.items() if t==1]
    team2 = [p for p,t in primary.items() if t==2]
    return team1, team2, rows


def map_play_counts(sessions):
    counts = {}
    for sid, map_name, round_num, actual_time in sessions:
        if round_num == 2:
            counts[map_name] = counts.get(map_name,0) + 1
    return counts


def main():
    conn = sqlite3.connect(DB)
    latest = fetch_latest_date(conn)
    if not latest:
        print('No sessions found in database')
        return
    print(f'Latest session date: {latest}')

    sessions = fetch_sessions_for_date(conn, latest)
    print(f'Found {len(sessions)} session rows (rounds) for that date')

    session_ids = [s[0] for s in sessions]
    player_count = count_unique_players(conn, session_ids)
    print(f'Unique players: {player_count}')

    maps_counts = map_play_counts(sessions)
    if maps_counts:
        print('\nMaps played:')
        for m, plays in maps_counts.items():
            print(f' - {m}: {plays*2} rounds ({plays} map completions)')

    print('\nTop players by kills:')
    for i, row in enumerate(top_players(conn, session_ids, limit=10),1):
        name, kills, deaths, dpm, total_seconds = row
        kd = (kills/deaths) if deaths>0 else kills
        mins = int((total_seconds or 0)//60)
        secs = int((total_seconds or 0)%60)
        print(f"{i}. {name} - {kills}K/{deaths}D ({kd:.2f} KD) • {dpm:.0f} DPM • {mins}:{secs:02d} playtime")

    team1, team2, raw = team_composition(conn, session_ids)
    print(f'\nTeam 1 players ({len(team1)}): {", ".join(team1[:10])}{"..." if len(team1)>10 else ""}')
    print(f'Team 2 players ({len(team2)}): {", ".join(team2[:10])}{"..." if len(team2)>10 else ""}')

    conn.close()

if __name__ == '__main__':
    main()
