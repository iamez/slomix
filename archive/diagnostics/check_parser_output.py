from bot.community_stats_parser import C0RNP0RN3StatsParser

parser = C0RNP0RN3StatsParser()

file_path = 'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt'
data = parser.parse_stats_file(file_path)

print(f"Total players: {len(data['players'])}")
print("\nPlayers:")
for i, player in enumerate(data['players']):
    print(f"{i + 1}. Keys: {list(player.keys())[:10]}...")  # Show first 10 keys
    if 'player_name' in player:
        print(f"   Name: {player['player_name']}")
    else:
        print(f"   NO PLAYER_NAME! All keys: {player.keys()}")
