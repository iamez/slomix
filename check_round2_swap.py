"""
Check Round 2 of etl_adlernest to verify stopwatch swap
"""
import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

print("="*80)
print("OCT 28 - etl_adlernest - ROUND 2")
print("="*80)

cursor.execute("""
    SELECT 
        player_guid,
        player_name,
        team,
        kills,
        deaths,
        time_played_minutes
    FROM player_comprehensive_stats
    WHERE session_date = '2024-10-28'
      AND map_name = 'etl_adlernest'
      AND round_number = 2
    ORDER BY team, player_name
""")

rows = cursor.fetchall()

print(f"\nTotal records: {len(rows)}\n")

axis_players = []
allies_players = []

for row in rows:
    guid, name, team, kills, deaths, time = row
    player_info = {'guid': guid, 'name': name, 'kills': kills, 'deaths': deaths, 'time': time}
    
    if team == 1:
        axis_players.append(player_info)
    else:
        allies_players.append(player_info)

print(f"🔴 AXIS TEAM ({len(axis_players)} players):")
for p in axis_players:
    print(f"   {p['name']:<20} ({p['guid']}) - K:{p['kills']}, D:{p['deaths']}")

print(f"\n🔵 ALLIES TEAM ({len(allies_players)} players):")
for p in allies_players:
    print(f"   {p['name']:<20} ({p['guid']}) - K:{p['kills']}, D:{p['deaths']}")

# Now compare with Round 1
print("\n" + "="*80)
print("STOPWATCH VERIFICATION")
print("="*80)

r1_axis = {'5D989160', '1C747DF1', '9CC78CFE'}  # .olz, noProne.lgz, v_kt_r
r1_allies = {'0A26D447', '7B84BE88', 'FDA127DF'}  # carniee, endekk, wajs

r2_axis_guids = {p['guid'] for p in axis_players}
r2_allies_guids = {p['guid'] for p in allies_players}

print("\nRound 1:")
print(f"   Axis:   {r1_axis}")
print(f"   Allies: {r1_allies}")

print("\nRound 2:")
print(f"   Axis:   {r2_axis_guids}")
print(f"   Allies: {r2_allies_guids}")

# Check if they swapped
if r1_axis == r2_allies_guids and r1_allies == r2_axis_guids:
    print("\n✅ PERFECT STOPWATCH SWAP!")
    print("   Round 1 Axis → Round 2 Allies")
    print("   Round 1 Allies → Round 2 Axis")
    print("\n🏆 FINAL TEAMS:")
    print("\n   TEAM A (started as Axis in R1):")
    print("   - .olz")
    print("   - noProne.lgz")
    print("   - v_kt_r")
    print("\n   TEAM B (started as Allies in R1):")
    print("   - carniee")
    print("   - endekk")
    print("   - wajs")
elif r1_axis == r2_axis_guids and r1_allies == r2_allies_guids:
    print("\n❌ NO SWAP - Same teams on same sides")
else:
    print("\n⚠️  PARTIAL SWAP or roster changes")

conn.close()
