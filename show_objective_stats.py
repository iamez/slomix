"""Quick summary showing objective stats extracted from stats file"""

from bot.community_stats_parser import C0RNP0RN3StatsParser

parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file('local_stats/2024-06-29-221611-supply-round-1.txt')

print("\n" + "=" * 80)
print("OBJECTIVE STATS SUMMARY - All Players")
print("=" * 80)
print(
    f"{'Player':<20} {'XP':>5} {'Assists':>7} {'Obj S/R':>8} {'Dyn P/D':>8} {'Revived':>7} {'2x/3x/4x':>10}"
)
print("-" * 80)

for player in result['players']:
    if 'objective_stats' in player:
        obj = player['objective_stats']
        print(
            f"{player['name']:<20} {obj['xp']:>5} {obj['kill_assists']:>7} "
            f"{obj['objectives_stolen']:>3}/{obj['objectives_returned']:<3} "
            f"{obj['dynamites_planted']:>3}/{obj['dynamites_defused']:<3} "
            f"{obj['times_revived']:>7} "
            f"{obj['multikill_2x']:>3}/{obj['multikill_3x']}/{obj['multikill_4x']:<3}"
        )
    else:
        print(f"{player['name']:<20} No objective stats")

print("\nLegend:")
print("  Obj S/R = Objectives Stolen / Returned")
print("  Dyn P/D = Dynamites Planted / Defused")
print("  2x/3x/4x = Double/Triple/Quad kills")
