"""Profile mapping tables for ET:Legacy greatshot."""

from __future__ import annotations

from typing import Dict

PROFILE_ID = "etlegacy_main"
PROFILE_NAME = "ET:Legacy Main"

# Cause-of-death values from parsed demos mapped to canonical identifiers.
WEAPON_MAP: Dict[str, str] = {
    "AKIMBO COLT": "akimbo_colt",
    "AKIMBO LUGER": "akimbo_luger",
    "ARTILLERY": "artillery",
    "BROWNING": "browning",
    "COLT": "colt",
    "DYNAMITE": "dynamite",
    "FG42": "fg42",
    "FG42SCOPE": "fg42_scope",
    "FLAMETHROWER": "flamethrower",
    "GARAND": "garand",
    "GARANDSCOPE": "garand_scope",
    "GPG40": "gpg40",
    "GRENADE": "grenade",
    "GRENADE_LAUNCHER": "grenade_launcher",
    "K43": "k43",
    "K43SCOPE": "k43_scope",
    "KICKED": "kicked",
    "KNIFE": "knife",
    "LANDMINE": "landmine",
    "LUGER": "luger",
    "M7": "m7",
    "MOBILE_MG42": "mobile_mg42",
    "MORTAR": "mortar",
    "MORTAR_SPLASH": "mortar_splash",
    "MP40": "mp40",
    "PANZERFAUST": "panzerfaust",
    "PISTOL": "pistol",
    "POISON": "poison",
    "RIFLE_GRENADE": "rifle_grenade",
    "SATCHEL": "satchel",
    "SMG": "smg",
    "STEN": "sten",
    "SYRINGE": "syringe",
    "THOMPSON": "thompson",
    "VENOM": "venom",
    "WATER": "water",
}

TEAM_MAP: Dict[str, str] = {
    "axis": "axis",
    "allies": "allies",
    "spectator": "spectator",
    "spec": "spectator",
}

# g_gametype values observed in ET family servers.
GAMETYPE_BY_ID: Dict[str, str] = {
    "0": "ffa",
    "1": "1v1",
    "2": "objective",
    "3": "stopwatch",
    "4": "campaign",
    "5": "last_man_standing",
    "6": "mapvoting",
}


def canonical_weapon(raw_value: str | None) -> str:
    if not raw_value:
        return "unknown"
    normalized = str(raw_value).strip().upper()
    return WEAPON_MAP.get(normalized, normalized.lower().replace(" ", "_"))


def canonical_team(raw_value: str | None) -> str:
    if not raw_value:
        return "unknown"
    normalized = str(raw_value).strip().lower()
    return TEAM_MAP.get(normalized, normalized)
