"""The canonical parser runs without Discord; rendering still uses real embeds."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/sample_stats_files"

SCRIPT = r'''
import importlib.abc
import json
import sys
from datetime import datetime

blocked = sys.argv[1] == "blocked"
class NoPresentation(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"discord", "dotenv", "website"} or fullname == "bot.config":
            raise ModuleNotFoundError("Presentation/config dependency forbidden: " + fullname)

if blocked:
    sys.meta_path.insert(0, NoPresentation())
else:
    import discord

import bot.community_stats_parser as module
class FixedClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2025, 12, 17, 12, 0, 0, tzinfo=tz)
module.datetime = FixedClock
parser = module.C0RNP0RN3StatsParser()
result = parser.parse_stats_file(sys.argv[2])
players = [parser.parse_player_line(chr(92).join([
    "a" * 32, "Fixture", "1", "1", stats,
])) for stats in ("1 10 20 3 2 1", "1 25 40 8 4 2")]
assert all(players)
rounds = [dict(map_name="goldrush", players=[player], actual_time="10:00",
               map_time="10:00", defender_team=1, round_outcome="Fullhold") for player in players]
differential = parser.calculate_round_2_differential(*rounds)
assert differential["players"][0]["kills"] == 5
if blocked:
    assert "discord" not in sys.modules
    assert "bot.config" not in sys.modules
    try:
        parser.create_stylish_round_embed({})
    except ModuleNotFoundError as error:
        assert "discord" in str(error)
    else:
        raise AssertionError("Rendering must retain its explicit Discord dependency")
print(json.dumps(dict(parsed=result, differential=differential), sort_keys=True))
'''


@pytest.mark.parametrize("filename", [
    "2025-12-17-120000-goldrush-round-1.txt",
    "2025-12-17-120000-goldrush-round-2.txt",
    "2025-12-17-130000-badmap-round-1.txt",
])
def test_fixture_parity_in_process_without_discord_or_bot_config(filename):
    fixture = FIXTURES / filename
    assert fixture.is_file(), "Committed parser fixture must not silently skip"
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("DISCORD_", "POSTGRES_", "BOT_ENVIRONMENT"))}
    results = []
    for mode in ("normal", "blocked"):
        completed = subprocess.run(
            [sys.executable, "-c", SCRIPT, mode, str(fixture)],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=15,
        )
        assert completed.returncode == 0, completed.stderr
        results.append(json.loads(completed.stdout.splitlines()[-1]))
    assert results[0] == results[1]
    # These legacy fixture player lines are not in the parser's current format;
    # nonempty player/differential coverage is supplied separately above.
    assert results[1]["parsed"]["total_players"] == 0
    assert len(results[1]["differential"]["players"]) == 1
    print(f"Parser subprocess proof: {filename}, identical output with Discord forbidden")


def test_rendering_still_returns_real_discord_embed():
    import discord

    from bot.community_stats_parser import C0RNP0RN3StatsParser

    embed = C0RNP0RN3StatsParser().create_stylish_round_embed({
        "map_name": "goldrush", "round_num": 2, "round_outcome": "Fullhold",
        "actual_time": "10:00", "players": [],
    })
    assert isinstance(embed, discord.Embed)
    assert "goldrush" in embed.description and "Round 2" in embed.description
    assert embed.colour.value == 0xFF6B35
    assert embed.timestamp is not None
    assert embed.footer.text == "ET:Legacy Community Stats • c0rnp0rn3.lua"
