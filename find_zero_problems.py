"""
Find ALL sessions with zero/missing stats
"""
import sqlite3

db_path = "bot/etlegacy_production.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get recent sessions with problematic zeros
print("=" * 100)
print("SESSIONS WITH ZERO/MISSING STATS (Last 100 sessions)")
print("=" * 100)

cursor.execute("""
    SELECT 
        s.id, s.session_date, s.map_name, s.round_number,
        COUNT(*) as player_count,
        SUM(CASE WHEN p.headshot_kills = 0 THEN 1 ELSE 0 END) as zero_hs,
        SUM(CASE WHEN p.revives_given = 0 THEN 1 ELSE 0 END) as zero_revs,
        SUM(CASE WHEN p.accuracy = 0 THEN 1 ELSE 0 END) as zero_acc,
        SUM(CASE WHEN p.time_dead_minutes = 0 THEN 1 ELSE 0 END) as zero_tdead
    FROM sessions s
    JOIN player_comprehensive_stats p ON s.id = p.session_id AND s.round_number = p.round_number
    WHERE s.id >= (SELECT MAX(id) - 100 FROM sessions)
    GROUP BY s.id, s.session_date, s.map_name, s.round_number
    HAVING zero_acc > player_count * 0.5 OR zero_tdead > player_count * 0.5
    ORDER BY s.id DESC
""")

problem_sessions = cursor.fetchall()

print(f"\nFound {len(problem_sessions)} sessions with >50% players having zero accuracy or time_dead\n")

for sid, sdate, map_name, rnum, pcount, zhs, zrevs, zacc, ztdead in problem_sessions:
    issues = []
    if zacc > pcount * 0.5:
        issues.append(f"Acc0: {zacc}/{pcount}")
    if ztdead > pcount * 0.5:
        issues.append(f"TDead0: {ztdead}/{pcount}")
    
    print(f"Session {sid:4d} R{rnum} {sdate[:16]:16s} {map_name[:18]:18s} | {' | '.join(issues)}")

# Now check what percentage of ALL recent sessions have this issue
cursor.execute("""
    SELECT COUNT(DISTINCT s.id)
    FROM sessions s
    WHERE s.id >= (SELECT MAX(id) - 100 FROM sessions)
""")
total_recent = cursor.fetchone()[0]

print(f"\n{'=' * 100}")
print(f"SUMMARY: {len(problem_sessions)} / {total_recent} recent sessions affected ({len(problem_sessions)*100/total_recent:.1f}%)")
print("=" * 100)

conn.close()
