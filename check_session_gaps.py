import sqlite3
from datetime import datetime

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Get recent sessions
cursor.execute("""
    SELECT id, session_date, map_name 
    FROM sessions 
    WHERE id >= 3401 
    ORDER BY id
""")

sessions = cursor.fetchall()

print("📅 Recent sessions with time gaps:")
print("="*70)

prev_time = None
for sid, sdate, map_name in sessions:
    dt = datetime.strptime(sdate, '%Y-%m-%d-%H%M%S')
    
    if prev_time:
        gap_minutes = (dt - prev_time).total_seconds() / 60
        if gap_minutes > 30:
            gap_str = f"({gap_minutes:.0f}min gap) ⚠️ NEW SESSION"
        elif gap_minutes > 5:
            gap_str = f"({gap_minutes:.0f}min gap)"
        else:
            gap_str = ""
    else:
        gap_str = "(START)"
    
    time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    print(f"  ID {sid}: {time_str} - {map_name:20s} {gap_str}")
    prev_time = dt

conn.close()

print("\n💡 Analysis:")
print("  - Sessions with <30min gaps are likely part of same gaming session")
print("  - The 'last session' should group all maps from the same play session")
