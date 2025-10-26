from enum import Enum, auto

class Arg:
    def __iter__(self):
        self.a = 0
        return self

    def __next__(self):
        self.a += 1
        return self.a


class WeaponStats(Enum):
    WS_KNIFE           = 0
    WS_KNIFE_KBAR      = auto()
    WS_LUGER           = auto()
    WS_COLT            = auto()
    WS_MP40            = auto()
    WS_THOMPSON        = auto()
    WS_STEN            = auto()
    WS_FG42            = auto()
    WS_PANZERFAUST     = auto()
    WS_BAZOOKA         = auto()
    WS_FLAMETHROWER    = auto()
    WS_GRENADE         = auto()
    WS_MORTAR          = auto()
    WS_MORTAR2         = auto()
    WS_DYNAMITE        = auto()
    WS_AIRSTRIKE       = auto()
    WS_ARTILLERY       = auto()
    WS_SATCHEL         = auto()
    WS_GRENADELAUNCHER = auto()
    WS_LANDMINE        = auto()
    WS_MG42            = auto()
    WS_BROWNING        = auto()
    WS_CARBINE         = auto()
    WS_KAR98           = auto()
    WS_GARAND          = auto()
    WS_K43             = auto()
    WS_MP34            = auto()
    WS_SYRINGE         = auto()
    WS_MAX             = auto()


class Team(Enum):
    TEAM_FREE      = 0
    TEAM_AXIS      = 1
    TEAM_ALLIES    = 2
    TEAM_SPECTATOR = 3
