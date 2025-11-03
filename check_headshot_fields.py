from bot.community_stats_parser import C0RNP0RN3StatsParser

p = C0RNP0RN3StatsParser()
data = p.parse_stats_file('bot/local_stats/2025-11-01-212527-supply-round-1.txt')

player = data['players'][0]
obj = player.get('objective_stats', {})
ws = player.get('weapon_stats', {})

print('='*60)
print(f'Player: {player.get("name")}')
print('='*60)

print('\n=== PLAYER TOP-LEVEL ===')
print(f'headshots: {player.get("headshots")}')

print('\n=== OBJECTIVE_STATS ===')
print(f'headshot_kills: {obj.get("headshot_kills")}')

print('\n=== WEAPON_STATS AGGREGATION ===')
total_weapon_hs = sum(w.get('headshots', 0) for w in ws.values())
print(f'Total weapon headshots: {total_weapon_hs}')

print('\nWeapon breakdown:')
for weapon, stats in ws.items():
    hs = stats.get('headshots', 0)
    if hs > 0:
        print(f'  {weapon}: {hs} headshots')

print('\n=== CONCLUSION ===')
print(f'player["headshots"] = {player.get("headshots")}')
print(f'objective_stats["headshot_kills"] = {obj.get("headshot_kills")}')
print(f'Sum of weapon headshots = {total_weapon_hs}')
print(f'\nDo they match?')
print(f'  player.headshots == sum(weapon_hs): {player.get("headshots") == total_weapon_hs}')
print(f'  player.headshots == headshot_kills: {player.get("headshots") == obj.get("headshot_kills")}')
