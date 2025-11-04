"""Small harness to render sample images for last_session helpers.
Generates:
 - tmp/session_overview.png
 - tmp/performance_analytics_map.png
 - tmp/performance_analytics_players.png

Run from the repo root: python tools/render_sample_images.py
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
# Ensure repo root is on sys.path so `bot` package can be imported
sys.path.insert(0, str(ROOT))

# Import the helpers
from bot.last_session_helpers import (
    create_map_performance_image,
    create_performance_image,
)
from bot.image_generator import StatsImageGenerator

TMP = ROOT / "tmp"
TMP.mkdir(exist_ok=True)

# Mock map aggregates
maps = [
    {
        "map": "Map_A",
        "kills": 34,
        "deaths": 20,
        "gibs": 5,
        "time_played": 12.5,
        "denied": 7,
        "time_dead": 1.2,
        "damage_given": 15230,
        "damage_received": 8420,
        "dpm": 127.5,
    },
    {
        "map": "Map_B",
        "kills": 21,
        "deaths": 25,
        "gibs": 3,
        "time_played": 9.0,
        "denied": 4,
        "time_dead": 0.9,
        "damage_given": 9840,
        "damage_received": 11230,
        "dpm": 109.3,
    },
    {
        "map": "Map_C",
        "kills": 45,
        "deaths": 18,
        "gibs": 8,
        "time_played": 15.3,
        "denied": 12,
        "time_dead": 2.1,
        "damage_given": 20450,
        "damage_received": 10100,
        "dpm": 133.6,
    },
]

# Mock top players rows (tuple-compatible)
players = [
    ("PlayerOne", 34, 20, 127.5, 750, 45, 7, 2, 1),
    ("PlayerTwo", 21, 25, 109.3, 540, 32, 4, 1, 0),
    ("PlayerThree", 45, 18, 133.6, 920, 63, 12, 3, 4),
]

# Create map performance image (per-map default)
buf = create_map_performance_image(maps, "2025-10-30")
path = TMP / "performance_analytics_map.png"
with open(path, "wb") as f:
    f.write(buf.read())
print(f"Wrote: {path}")

# Create player performance image
buf2 = create_performance_image(players, "2025-10-30")
path2 = TMP / "performance_analytics_players.png"
with open(path2, "wb") as f:
    f.write(buf2.read())
print(f"Wrote: {path2}")

# Create session overview using StatsImageGenerator
sg = StatsImageGenerator()
# Minimal session_data mock
session_data = {
    "session_id": 123,
    "maps_list": [m["map"] for m in maps],
    "duration_minutes": sum(m["time_played"] for m in maps),
}

# Build a simplified top_players list as dicts to exercise new code path
top_players_dicts = [
    {
        "name": "PlayerOne",
        "kills": 34,
        "deaths": 20,
        "dpm": 127.5,
        "hits": 120,
        "shots": 300,
        "hs": 15,
        "playtime_minutes": 12.5,
        "time_dead_minutes": 0.75,
        "gibs": 2,
        "revives": 1,
    },
    {
        "name": "PlayerTwo",
        "kills": 21,
        "deaths": 25,
        "dpm": 109.3,
        "hits": 80,
        "shots": 220,
        "hs": 7,
        "playtime_minutes": 9.0,
        "time_dead_minutes": 0.53,
        "gibs": 1,
        "revives": 0,
    },
]

team_data = {"team1": {}, "team2": {}}

buf3 = sg.create_session_overview(
    session_data, top_players_dicts, team_data, ("Team A", "Team B")
)
path3 = TMP / "session_overview.png"
with open(path3, "wb") as f:
    f.write(buf3.getvalue())
print(f"Wrote: {path3}")
