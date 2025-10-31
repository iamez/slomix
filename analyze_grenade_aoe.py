import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

# Check a specific player's grenade stats
c.execute("""
    SELECT player_name, 
           SUM(kills) as kills, 
           SUM(shots) as throws, 
           SUM(hits) as hits,
           ROUND(CAST(SUM(hits) AS FLOAT) / SUM(shots) * 100, 1) as hit_rate,
           ROUND(CAST(SUM(hits) AS FLOAT) / SUM(kills), 2) as hits_per_kill
    FROM weapon_comprehensive_stats
    WHERE weapon_name = 'WS_GRENADE'
    GROUP BY player_name
    ORDER BY kills DESC
    LIMIT 10
""")

print("Top 10 Grenadiers - Detailed Stats:")
print("=" * 80)
print(f"{'Player':<20} {'Kills':<8} {'Throws':<8} {'Hits':<8} {'Hit%':<8} {'Hits/Kill'}")
print("-" * 80)

for row in c.fetchall():
    player, kills, throws, hits, hit_rate, hits_per_kill = row
    print(f"{player:<20} {kills:<8} {throws:<8} {hits:<8} {hit_rate:<8} {hits_per_kill}")

print("\n" + "=" * 80)
print("INTERPRETATION:")
print("- Throws: Number of grenades thrown")
print("- Hits: Number of PLAYERS hit by grenades (includes non-lethal damage)")
print("- Kills: Number of players killed by grenades")
print("- Hits/Kill: How many players were damaged per kill (AOE effectiveness)")
print("  * 1.0 = Only hit the person you killed (single target)")
print("  * 2.0+ = Hit multiple people with one grenade (good AOE placement!)")

# Find best AOE grenadiers (high hits per kill ratio)
c.execute("""
    SELECT player_name, 
           SUM(kills) as kills, 
           SUM(hits) as hits,
           ROUND(CAST(SUM(hits) AS FLOAT) / SUM(kills), 2) as hits_per_kill
    FROM weapon_comprehensive_stats
    WHERE weapon_name = 'WS_GRENADE'
    GROUP BY player_name
    HAVING kills > 100
    ORDER BY hits_per_kill DESC
    LIMIT 5
""")

print("\n" + "=" * 80)
print("🎖️ BEST AOE GRENADIERS (Most players hit per kill):")
print("-" * 80)
for row in c.fetchall():
    player, kills, hits, ratio = row
    print(f"  {player}: {ratio} hits/kill ({hits} hits, {kills} kills)")

conn.close()
