import sys

from community_stats_parser import C0RNP0RN3StatsParser

sys.path.insert(0, 'bot')

parser = C0RNP0RN3StatsParser()
result = parser.parse_file('local_stats/2025-10-02-211808-etl_adlernest-round-1.txt')

print("Players with time_played_minutes:")
print("=" * 60)
for guid, data in result['players'].items():
    time_played = data['objective_stats'].get('time_played_minutes', -999)
    print(f"{data['name']:20} | time={time_played:6.1f} min")
