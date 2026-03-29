"""ET:Legacy shared constants and utility functions.

Extracted from storytelling_service, rivalries_service, replay_service
to eliminate duplication.
"""
import re

# ET:Legacy kill_mod (means_of_death) → weapon name mapping (from MOD_* constants)
KILL_MOD_NAMES: dict[int, str] = {
    3: "Knife", 4: "Luger", 5: "Colt", 6: "Luger", 7: "Colt",
    8: "MP40", 9: "Thompson", 10: "Sten", 11: "Garand",
    12: "Silenced", 13: "FG42", 14: "FG42 Scope", 15: "Panzerfaust",
    16: "Grenade", 17: "Flamethrower", 18: "Grenade",
    22: "Dynamite", 23: "Airstrike", 26: "Artillery",
    37: "Carbine", 38: "K98", 39: "GPG40", 40: "M7",
    41: "Landmine", 42: "Satchel", 44: "Mobile MG42",
    45: "Silenced Colt", 46: "Garand Scope",
    50: "K43", 51: "K43 Scope", 52: "Mortar",
    53: "Akimbo Colt", 54: "Akimbo Luger",
    55: "Akimbo Silenced Colt", 56: "Akimbo Silenced Luger",
    60: "Sten",  # MOD_STEN_DMGBODY
    66: "Backstab",
}

_ET_COLOR_RE = re.compile(r'\^[0-9a-zA-Z]')


def strip_et_colors(name: str) -> str:
    """Remove ET:Legacy color codes (^0-^9, ^a-^z, ^A-^Z) from names."""
    if not name:
        return ""
    return _ET_COLOR_RE.sub('', name)


def weapon_name(kill_mod) -> str:
    """Map kill_mod (means_of_death) integer to human-readable weapon name."""
    if kill_mod is None:
        return "Unknown"
    return KILL_MOD_NAMES.get(int(kill_mod), f"MOD_{kill_mod}")
