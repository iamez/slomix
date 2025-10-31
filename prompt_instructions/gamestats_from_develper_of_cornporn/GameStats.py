import utils
import os.path

class Weapon:
    def __init__(self, weapon):
        self.weapon       = weapon
        self.hits         = 0
        self.shots        = 0
        self.kills        = 0
        self.deaths       = 0
        self.headshots    = 0
        self.acc          = 0


class PlayerStats:
    def __init__(self):
        self.weapons = []

        self.totShots     = 0
        self.totHits      = 0
        self.totKills     = 0
        self.totDeaths    = 0
        self.totHeadshots = 0

        self.dmgGiven        = 0
        self.dmgReceived     = 0
        self.teamDmgGiven    = 0
        self.teamDmgReceived = 0
        self.gibs            = 0
        self.selfKills       = 0
        self.teamKills       = 0
        self.teamGibs        = 0
        self.ptRatio         = 0
        self.htRatio         = 0
        self.hsRatio         = 0
        self.xp              = 0
        
        self.hasStats = False


class Player:
    def __init__(self, id, guid, name, rounds, team):
        self.id     = id
        self.guid   = guid
        self.name   = name
        self.rounds = rounds
        self.team   = utils.Team(team)
        self.stats  = PlayerStats()


class GameStats:
    def __init__(self):
        self.tot_kills  = 0
        self.tot_deaths = 0
        self.tot_gibs   = 0
        self.tot_sk     = 0
        self.tot_tk     = 0
        self.tot_tg     = 0
        self.tot_dg     = 0
        self.tot_dr     = 0
        self.tot_tdg    = 0
        self.tot_tdr    = 0
        self.tot_xp     = 0
        self.tot_pt     = 0


class GameTeams:
    def __init__(self, team):
        self.team  = team
        self.stats = GameStats()


class Game:
    def set(self, servername, mapname, config, round, defender, winner, timelimit, nextTimelimit):
        self.servername   = servername
        self.mapname      = mapname
        self.config       = config
        self.round        = round
        self.defender     = utils.Team(defender)
        self.winner       = utils.Team(winner)
        self.timelimit    = timelimit
        self.nexTimelimit = nextTimelimit
        self.players      = []
        self.teams        = []
        for team in utils.Team:
            self.teams.append(GameTeams(team))


def sortByXP(players):
    return players.stats.xp


def getGame():
    #filename = os.path.join(os.path.curdir, "stats", "2022-07-08-122712-adlernest-round-1.txt")
    filename = os.path.join(os.path.curdir, "stats", "2022-07-08-122910-adlernest-round-2.txt")
    #filename = os.path.join(os.path.curdir, "stats", "adler.txt")
    game = Game()
    id   = 0
    
    with open(filename) as file:
        header = file.readline().split('\\')
        game.set(header[0], header[1], header[2], header[3], int(header[4]), int(header[5]), header[6], header[7])

        for line in file:
            arg   = iter(utils.Arg())
            lines = line.strip().split('\\')
    
            guid   = lines[0]
            name   = lines[1]
            rounds = lines[2]
            team   = int(lines[3])
            stats  = lines[4].split(' ')

            player = Player(id, guid, name, rounds, team)
            game.players.append(player)
            id += 1

            for weapon in utils.WeaponStats:
                if int(stats[0]) & (1 << weapon.value):
                    pWeapon = Weapon(weapon)
                    player.stats.weapons.append(pWeapon)

                    pWeapon.hits       = int(stats[next(arg)])
                    pWeapon.shots      = int(stats[next(arg)])
                    pWeapon.kills      = int(stats[next(arg)])
                    pWeapon.deaths     = int(stats[next(arg)])
                    pWeapon.headshots  = int(stats[next(arg)])
                    pWeapon.acc        = (pWeapon.hits * 100) / pWeapon.shots if pWeapon.shots > 0 else 0.0;
            
                    player.stats.totShots     += pWeapon.shots
                    player.stats.totHits      += pWeapon.hits
                    player.stats.totKills     += pWeapon.kills;
                    player.stats.totDeaths    += pWeapon.deaths;
                    player.stats.totHeadshots += pWeapon.headshots;
                    player.stats.hasStats     = True

            if player.stats.hasStats:
                player.stats.dmgGiven        = int(stats[next(arg)])
                player.stats.dmgReceived     = int(stats[next(arg)])
                player.stats.teamDmgGiven    = int(stats[next(arg)])
                player.stats.teamDmgReceived = int(stats[next(arg)])
                player.stats.gibs            = int(stats[next(arg)])
                player.stats.selfKills       = int(stats[next(arg)])
                player.stats.teamKills       = int(stats[next(arg)])
                player.stats.teamGibs        = int(stats[next(arg)])
                player.stats.ptRatio         = float(stats[next(arg)])
                player.stats.xp              = int(stats[next(arg)])
        
                player.stats.htRatio = 0 if (player.stats.totShots == 0) else (player.stats.totHits * 100.0 / player.stats.totShots)
                player.stats.hsRatio = 0

                game.teams[player.team.value].stats.tot_kills  += player.stats.totKills
                game.teams[player.team.value].stats.tot_deaths += player.stats.totDeaths
                game.teams[player.team.value].stats.tot_gibs   += player.stats.gibs
                game.teams[player.team.value].stats.tot_sk     += player.stats.selfKills
                game.teams[player.team.value].stats.tot_tk     += player.stats.teamKills
                game.teams[player.team.value].stats.tot_tg     += player.stats.teamGibs
                game.teams[player.team.value].stats.tot_dg     += player.stats.dmgGiven
                game.teams[player.team.value].stats.tot_dr     += player.stats.dmgReceived
                game.teams[player.team.value].stats.tot_tdg    += player.stats.teamDmgGiven
                game.teams[player.team.value].stats.tot_tdr    += player.stats.teamDmgReceived
                game.teams[player.team.value].stats.tot_pt     += player.stats.ptRatio
                game.teams[player.team.value].stats.tot_xp     += player.stats.xp


    return game


def getGameStats():
    game = getGame()
    game.players.sort(key = sortByXP, reverse = True)

    gamestats = []

    stats = "Server: {} Mapname: {} Round: {} Config: {} Defender: {} Winner: {} Timelimit: {} NextTimelimit: {}\n".format(game.servername, game.mapname, game.round, game.config,
                                                                                                                      game.defender.name[5:], game.winner.name[5:], game.timelimit, game.nexTimelimit)
    stats += "ID TEAM        Player              Kll  Dth  Gib  SK   TK   TG    Eff  DG      DR      TDG    TDR    Score\n"
    stats += "----------------------------------------------------------------------------------------------------------\n"

    for team in game.teams[1:]:
        for player in game.players:
            if player.team == team.team and player.stats.hasStats:
                stats += "{0:<2} {1:<11} {2:<19} {3:<4} {4:<4} {5:<4} {6:<4} {7:<4} {8:<4} {9:<5} {10:<7} {11:<7} {12:<6} {13:<6} {14:<5}\n".format(
                    player.id, player.team.name[5:], player.name, player.stats.totKills, player.stats.totDeaths,
                    player.stats.gibs, player.stats.selfKills, player.stats.teamKills,
                    player.stats.teamGibs, -10, player.stats.dmgGiven, player.stats.dmgReceived,
                    player.stats.teamDmgGiven, player.stats.teamDmgReceived, player.stats.xp)

        stats += "----------------------------------------------------------------------------------------------------------\n"
        stats += "   {0:<11} Totals              {1:<4} {2:<4} {3:<4} {4:<4} {5:<4} {6:<4} {7:<5} {8:<7} {9:<7} {10:<6} {11:<6} {12:<5}\n".format(
            team.team.name[5:], team.stats.tot_kills, team.stats.tot_deaths, team.stats.tot_gibs, team.stats.tot_sk, team.stats.tot_tk,
           team.stats.tot_tg, -10, team.stats.tot_dg, team.stats.tot_dr, team.stats.tot_tdg, team.stats.tot_tdr,  team.stats.tot_xp)
        #stats += "\n"
        gamestats.append(stats)
        stats = ""

    return gamestats


def getPlayerStats(player):
    game = getGame()
    game.players.sort(key = sortByXP, reverse = True)

    index = int(player)

    if len(game.players) > index and index >= 0:
        for player in game.players:
            if player.id == index and player.stats.hasStats:
                stats = "Server: {} Mapname: {} Round: {} Config: {} Defender: {} Winner: {} Timelimit: {} NextTimelimit: {}\n".format(
                    game.servername, game.mapname, game.round, game.config, game.defender.name[5:], game.winner.name[5:], game.timelimit, game.nexTimelimit)
                stats += "Name: {} Team: {} Rounds: {}\n".format(player.name, player.team.name[5:], player.rounds)
                stats += "Weapon          Acrcy  Hits/Shts Kills Deaths Headshots\n"
                stats += "-------------------------------------------------------\n"

                for weapon in player.stats.weapons:
                    stats += "{0: <16}{1:<7.1f}{2: <10}{3: <6}{4: <7}{5: <9}\n".format(
                        weapon.weapon.name[3:], weapon.acc, "{}/{}".format(weapon.hits, weapon.shots), weapon.kills, weapon.deaths, weapon.headshots)
            
                stats += "\n"
                stats += "Damage Given: {0:<7} Team Damage Given: {1:<7}\n".format(player.stats.dmgGiven, player.stats.teamDmgGiven)
                stats += "Damage Recvd: {0:<7} Team Damage Recvd: {1:<7}\n".format(player.stats.dmgReceived, player.stats.teamDmgReceived)
                stats += "\n"
                stats += "Kills:  {0:<4} Team Kills: {1:<4} Accuracy:  {2:<6.1f}\n".format(player.stats.totKills, player.stats.teamKills, player.stats.htRatio)
                stats += "Deaths: {0:<4} Self Kills: {1:<4} Headshots: {2:<4}\n".format(player.stats.totDeaths, player.stats.selfKills, player.stats.hsRatio)
                stats += "Gibs:   {0:<4} Team Gibs:  {1:<4} Playtime:  {2:<6.1f}\n".format(player.stats.gibs, player.stats.teamGibs, float(player.stats.ptRatio))
                stats += "\n"

                return stats              
    else:
        return "Bad argument"

    return "No stats for given player"



#eff = (cl->sess.deaths + cl->sess.kills == 0) ? 0 : 100 * cl->sess.kills / (cl->sess.deaths + cl->sess.kills);






    #for player in game.players:
    #    if player.stats.hasStats:
    #        print("Server: {} Mapname: {} Round: {} Config: {} Defender: {} Winner: {} Timelimit: {} NextTimelimit: {}".format(game.servername, game.mapname, game.round, game.config, game.defender.name[5:], game.winner.name[5:], game.timelimit, game.nexTimelimit))
    #        print("Name: {} Team: {} Rounds: {}".format(player.name, player.team.name[5:], player.rounds))
    #        print("Weapon          Acrcy  Hits/Shts Kills Deaths Headshots");
    #        print("-------------------------------------------------------");

    #        for weapon in player.stats.weapons:
    #            print("{0: <16}{1:<7.1f}{2: <10}{3: <6}{4: <7}{5: <9}".format(weapon.weapon.name[3:], weapon.acc, "{}/{}".format(weapon.hits, weapon.shots), weapon.kills, weapon.deaths, weapon.headshots))
            
    #        print("");
    #        print("Damage Given: {0:<7} Team Damage Given: {1:<7}".format(player.stats.dmgGiven, player.stats.teamDmgGiven));
    #        print("Damage Recvd: {0:<7} Team Damage Recvd: {1:<7}".format(player.stats.dmgReceived, player.stats.teamDmgReceived));
    #        print("");
    #        print("Kills:  {0:<4} Team Kills: {1:<4} Accuracy:  {2:<6.1f}".format(player.stats.totKills, player.stats.teamKills, player.stats.htRatio))
    #        print("Deaths: {0:<4} Self Kills: {1:<4} Headshots: {2:<4}".format(player.stats.totDeaths, player.stats.selfKills, player.stats.hsRatio))
    #        print("Gibs:   {0:<4} Team Gibs:  {1:<4} Playtime:  {2:<6.1f}".format(player.stats.gibs, player.stats.teamGibs, float(player.stats.ptRatio)))
    #        print("");
    #        print("");