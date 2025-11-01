import sqlite3
import sys

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Find October 2nd sessions
print("=== OCTOBER 2ND SESSIONS ===")
cursor.execute(
    """
    SELECT DISTINCT session_date, session_id
    FROM player_comprehensive_stats
    WHERE session_date LIKE '2025-10-02%'
    ORDER BY session_id
"""
)
sessions = cursor.fetchall()
for date, sid in sessions:
    print(f"Session {sid}: {date}")

if not sessions:
    print("No sessions found for 2025-10-02")
    print("\n=== CHECKING ALL DATES ===")
    cursor.execute(
        """
        SELECT DISTINCT session_date
        FROM player_comprehensive_stats
        ORDER BY session_date DESC LIMIT 20
    """
    )
    for row in cursor.fetchall():
        print(row[0])
    sys.exit(1)

# Print which files were imported for these sessions
print(f"\n=== IMPORTED FILES CHECK ===")
for sid in [sid for _, sid in sessions[:5]]:  # Check first 5 sessions
    cursor.execute(
        """
        SELECT DISTINCT map_name, round_number
        FROM player_comprehensive_stats
        WHERE session_id = ?
        ORDER BY round_number
    """,
        (sid,),
    )
    rounds = cursor.fetchall()
    print(f"\nSession {sid}:")
    for map_name, round_num in rounds:
        print(f"  Round {round_num}: {map_name}")
else:
    # Get the session IDs
    session_ids = [sid for _, sid in sessions]
    session_ids_str = ','.join([str(sid) for sid in session_ids])

    print(f"\n=== CHECKING DATA FOR SESSION(S): {session_ids_str} ===")

    # Check player stats
    print("\n--- PLAYER STATS (times_revived, gibs, xp, kill_assists, dynamites) ---")
    cursor.execute(
        f"""
        SELECT
            clean_name,
            SUM(times_revived) as revives,
            SUM(gibs) as gibs,
            SUM(xp) as xp,
            SUM(kill_assists) as assists,
            SUM(dynamites_planted) as dyn_planted,
            SUM(dynamites_defused) as dyn_defused,
            SUM(objectives_stolen) as obj_stolen,
            SUM(objectives_returned) as obj_returned
        FROM player_comprehensive_stats
        WHERE session_id IN ({session_ids_str})
        GROUP BY clean_name
        ORDER BY SUM(kills) DESC
    """
    )

    print(
        f"{'Player':<20} {'Revived':<10} {'Gibs':<8} {'XP':<10} {'Assists':<10} {'Dyn P/D':<15} {'Obj S/R':<15}"
    )
    print("-" * 110)
    for row in cursor.fetchall():
        name, revives, gibs, xp, assists, dyn_p, dyn_d, obj_s, obj_r = row
        print(
            f"{name:<20} {revives:<10} {gibs:<8} {xp:<10} {assists:<10} {dyn_p}/{dyn_d:<13} {obj_s}/{obj_r:<13}"
        )

    # Check weapon stats
    print("\n--- WEAPON STATS (checking for syringe, colt, luger) ---")
    cursor.execute(
        f"""
        SELECT
            weapon_name,
            SUM(kills) as total_kills
        FROM weapon_comprehensive_stats
        WHERE session_id IN ({session_ids_str})
        AND weapon_name IN ('syringe', 'colt', 'luger', 'Syringe', 'Colt', 'Luger')
        GROUP BY weapon_name
        ORDER BY total_kills DESC
    """
    )

    weapon_results = cursor.fetchall()
    if weapon_results:
        for weapon, kills in weapon_results:
            print(f"  {weapon}: {kills} kills")
    else:
        print("  No syringe/colt/luger data found")

        # Check what weapons ARE in the database
        print("\n  Checking all weapons in database for these sessions:")
        cursor.execute(
            f"""
            SELECT DISTINCT weapon_name
            FROM weapon_comprehensive_stats
            WHERE session_id IN ({session_ids_str})
            ORDER BY weapon_name
        """
        )
        weapons = [row[0] for row in cursor.fetchall()]
        print(f"  Weapons found: {', '.join(weapons[:20])}")
        if len(weapons) > 20:
            print(f"  ... and {len(weapons) - 20} more")

conn.close()
