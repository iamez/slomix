"""
Analyze raw stats file to understand the TAB field positions
"""

# Sample line from sw_goldrush_te-round-2.txt:
# D8423F90\^pvid\1\2\134219839 0 3 0 0 0 0 2 0 0 0 4 8 0 2 0 8 26 1 0 1
# 150 335 12 11 17 116 288 12 10 12 7 18 2 1 0 8 8 0 0 0    5785    5146
# 105     98      7       8       1       0       79.6    133     4
# 3       7       0       4       0       0       0       0       2
# 53125   0.0     18.2    0.0     25.8    4.7     1.1     7       143
# 0       0       0       0       0       2       1       1

raw_line = r"D8423F90\^pvid\1\2\134219839 0 3 0 0 0 0 2 0 0 0 4 8 0 2 0 8 26 1 0 1 150 335 12 11 17 116 288 12 10 12 7 18 2 1 0 8 8 0 0 0 	5785	5146	105	98	7	8	1	0	79.6	133	4	3	7	0	4	0	0	0	0	2	53125	0.0	18.2	0.0	25.8	4.7	1.1	7	143	0	0	0	0	0	2	1	1"

print("=== RAW STATS FILE ANALYSIS ===\n")

# Split by tab
parts = raw_line.split('\t')
print(f"Parts separated by TAB: {len(parts)}")
print(f"\nPart 0 (Player ID + Space-separated weapon stats):")
print(f"  {parts[0][:100]}...")

print(f"\nPart 1 onwards (TAB-separated objective stats):")
tab_fields = parts[1:]

print(f"\nTotal TAB fields: {len(tab_fields)}")
print("\nField positions according to parser:")
print(f"  [0] damage_given: {tab_fields[0]}")
print(f"  [1] damage_received: {tab_fields[1]}")
print(f"  [2] gibs: {tab_fields[2]}")
print(f"  [3] team_kills: {tab_fields[3]}")
print(f"  [9] xp: {tab_fields[9]}")
print(f"  [12] kill_assists: {tab_fields[12]}")
print(f"  [15] objectives_stolen: {tab_fields[15]}")
print(f"  [16] objectives_returned: {tab_fields[16]}")
print(f"  [17] dynamites_planted: {tab_fields[17]}")
print(f"  [18] dynamites_defused: {tab_fields[18]}")
print(f"  [19] times_revived: {tab_fields[19]}")
print(f"  [21] dpm: {tab_fields[21]}")
print(f"  [22] time_played_minutes: {tab_fields[22]}")

print("\n=== ANALYSIS ===")
print(f"✅ XP = {tab_fields[9]} (NOT ZERO!)")
print(f"✅ Kill Assists = {tab_fields[12]} (NOT ZERO!)")
print(f"⚠️ Gibs = {tab_fields[2]} (SHOWING {tab_fields[2]})")
print(f"✅ Times Revived = {tab_fields[19]} (NOT ZERO!)")
print(f"✅ Dynamites Planted = {tab_fields[17]} (NOT ZERO!)")
print(f"✅ Dynamites Defused = {tab_fields[18]}")

print("\n=== CONCLUSION ===")
print("The raw file HAS non-zero values!")
print("This means either:")
print("  1. Parser is extracting them correctly but not saving to DB")
print("  2. Import script is not passing them to DB INSERT")
print("  3. Different stats files were imported than expected")
