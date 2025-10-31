import sys

from community_stats_parser import C0RNP0RN3StatsParser

sys.path.insert(0, 'bot')

parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file('local_stats/2025-10-02-211808-etl_adlernest-round-1.txt')

vid_data = None
for player in result['players']:
    if player['name'] == 'vid':
        vid_data = player
        break

print('PARSER OUTPUT (top-level):')
print(f'  multikill_2x: {vid_data.get("multikill_2x", "NOT FOUND")}')
print(f'  multikill_3x: {vid_data.get("multikill_3x", "NOT FOUND")}')
print('')

print('PARSER OUTPUT (objective_stats):')
obj_stats = vid_data.get('objective_stats', {})
print(f'  denied_playtime: {obj_stats.get("denied_playtime", "NOT FOUND")}')
print(f'  multikill_2x: {obj_stats.get("multikill_2x", "NOT FOUND")}')
print(f'  multikill_3x: {obj_stats.get("multikill_3x", "NOT FOUND")}')
print(f'  multikill_4x: {obj_stats.get("multikill_4x", "NOT FOUND")}')
print(f'  multikill_5x: {obj_stats.get("multikill_5x", "NOT FOUND")}')
print(f'  multikill_6x: {obj_stats.get("multikill_6x", "NOT FOUND")}')
print('')

# Read raw file
with open(
    'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt',
    'r',
    encoding='utf-8',
    errors='ignore',
) as f:
    lines = f.readlines()
    for line in lines:
        if 'vid' in line.lower():
            parts = line.split(' \t')
            if len(parts) > 1:
                tab_fields = parts[1].split('\t')
                print('RAW FILE TAB FIELDS:')
                print(f'  field[28] (should be multikills(2)): {tab_fields[28]}')
                print(f'  field[29] (should be multikills(3)): {tab_fields[29]}')
                print(f'  field[30] (should be multikills(4)): {tab_fields[30]}')
                print(f'  field[31] (should be multikills(5)): {tab_fields[31]}')
                print(f'  field[32] (should be multikills(6)): {tab_fields[32]}')
                print('')
                print('ANALYSIS:')
                print(f'  Is 78 double-kills realistic? Seems very high!')
                print(f'  Parser reads: {vid_data.get("multikill_2x", "NOT FOUND")}')
                print(f'  Raw file has: 78')
                break
