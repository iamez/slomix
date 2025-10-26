import GameStats

gamestats = GameStats.getGameStats()
for stats in gamestats:
    print(stats)

print(GameStats.getPlayerStats(3))