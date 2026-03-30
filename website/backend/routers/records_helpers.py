"""Shared constants and helpers used by records sub-routers."""

from typing import Any

# Award categories for display (mirrors bot/endstats_parser.py)
AWARD_CATEGORIES = {
    "combat": {
        "emoji": "\u2694\ufe0f",
        "name": "Combat",
        "awards": [
            "Most damage given",
            "Most damage received",
            "Most kills per minute",
            "Most damage per minute",
            "Best K/D ratio",
            "Tank/Meatshield (Refuses to die)",
        ],
    },
    "deaths": {
        "emoji": "\U0001f480",
        "name": "Deaths & Mayhem",
        "awards": [
            "Most deaths",
            "Most selfkills",
            "Most teamkills",
            "Longest death spree",
            "Most panzer deaths",
            "Most mortar deaths",
            "Most MG42 deaths",
            "Mortarmagnet",
        ],
    },
    "skills": {
        "emoji": "\U0001f3af",
        "name": "Skills",
        "awards": [
            "Most headshot kills",
            "Most headshots",
            "Highest light weapons accuracy",
            "Highest headshot accuracy",
            "Most light weapon kills",
            "Most pistol kills",
            "Most rifle kills",
            "Most sniper kills",
            "Most knife kills",
            "Longest killing spree",
            "Most multikills",
            "Most doublekills",
            "Quickest multikill w/ light weapons",
            "Most bullets fired",
        ],
    },
    "weapons": {
        "emoji": "\U0001f52b",
        "name": "Weapons",
        "awards": [
            "Most grenade kills",
            "Most panzer kills",
            "Most mortar kills",
            "Most mine kills",
            "Most air support kills",
            "Most riflenade kills",
            "Farthest riflenade kill",
            "Most MG42 kills",
        ],
    },
    "teamwork": {
        "emoji": "\U0001f91d",
        "name": "Teamwork",
        "awards": [
            "Most revives",
            "Most revived",
            "Most kill assists",
            "Most killsteals",
            "Most team damage given",
            "Most team damage received",
        ],
    },
    "objectives": {
        "emoji": "\U0001f3af",
        "name": "Objectives",
        "awards": [
            "Most dynamites planted",
            "Most dynamites defused",
            "Most objectives stolen",
            "Most objectives returned",
            "Most corpse gibs",
        ],
    },
    "timing": {
        "emoji": "\u23f1\ufe0f",
        "name": "Timing",
        "awards": [
            "Most useful kills (>Half respawn time left)",
            "Most useless kills",
            "Full respawn king",
            "Most playtime denied",
            "Least time dead (What spawn?)",
        ],
    },
}


def categorize_award(award_name: str) -> tuple:
    """Return (category_key, emoji, category_name) for an award."""
    for cat_key, cat_data in AWARD_CATEGORIES.items():
        if award_name in cat_data["awards"]:
            return (cat_key, cat_data["emoji"], cat_data["name"])
    return ("other", "\U0001f4cb", "Other")


def serialize_round_label(round_number: Any) -> str:
    """Convert round numbers to UI-safe labels."""
    if round_number is None:
        return "R?"
    try:
        normalized = int(round_number)
    except (TypeError, ValueError):
        return "R?"
    if normalized == 0:
        return "Match Summary"
    return f"R{normalized}"
