import sys, json, itertools
sys.path.append('bot')
from community_stats_parser import C0RNP0RN3StatsParser
p=C0RNP0RN3StatsParser()
file='local_stats/2025-10-30-230944-braundorf_b4-round-2.txt'
r=p.parse_stats_file(file)
print('success=', r.get('success'))
players=r.get('players', [])
print('players=', len(players))
if players:
    print('sample_player_keys=', list(players[0].keys()))
    ws = players[0].get('weapon_stats', {})
    print('weapon_stats_count_sample=', len(ws))
    print('weapon_stats_keys_sample=', list(ws.keys())[:10])
    # print first 3 weapon entries
    for i,(k,v) in enumerate(list(ws.items())[:3]):
        print(f'weapon {i}:', k, v)
else:
    print('no players')
