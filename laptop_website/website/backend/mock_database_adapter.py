"""
Mock Database Adapter for Website Backend
Used when no real database is available.
"""

import logging
from typing import Any, Optional, List, Tuple
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import random

# Import base class from bot core
# If this fails, we might need to define a local base class
try:
    from bot.core.database_adapter import DatabaseAdapter
except ImportError:
    # Fallback if bot core is not importable
    class DatabaseAdapter:
        pass

logger = logging.getLogger("MockDatabaseAdapter")

class MockAdapterV2(DatabaseAdapter):
    """Mock database adapter returning dummy data."""

    # Class-level storage for persistence across requests (but not restarts)
    _clips = []
    _configs = []

    def __init__(self):
        logger.info("📦 Mock Database Adapter initialized")
        self.players = []
        
        # Initialize with some dummy community data if empty
        if not MockAdapterV2._clips:
            MockAdapterV2._clips = [
                {"id": 1, "title": "Insane 5k on Supply", "author": "BAMBAM", "url": "https://youtu.be/dQw4w9WgXcQ", "views": 124, "likes": 45, "date": "2025-11-28"},
                {"id": 2, "title": "Medic clutch", "author": "Viper", "url": "https://youtu.be/dQw4w9WgXcQ", "views": 89, "likes": 12, "date": "2025-11-27"},
            ]
            
        if not MockAdapterV2._configs:
            MockAdapterV2._configs = [
                {"id": 1, "title": "BAMBAM's Comp Config", "author": "BAMBAM", "downloads": 56, "description": "High FPS, low graphics", "date": "2025-11-20"},
                {"id": 2, "title": "Standard ET:Legacy", "author": "Admin", "downloads": 120, "description": "Default competitive settings", "date": "2025-10-15"},
            ]
        
        # Generate some realistic-looking player data
        names = [
            "BAMBAM", "Snake", "Viper", "Ghost", "Raptor", "Eagle", "Wolf", "Bear", "Tiger", "Lion",
            "Shadow", "Storm", "Blaze", "Frost", "Nova", "Pulse", "Ace", "King", "Queen", "Jack",
            "Joker", "Batman", "Superman", "Flash", "Hulk", "Thor", "Loki", "Odin", "Zeus", "Hades"
        ]
        
        for i, name in enumerate(names):
            games = random.randint(10, 100)
            wins = int(games * random.uniform(0.3, 0.7))
            kills = int(games * random.uniform(10, 30))
            deaths = int(games * random.uniform(5, 25))
            # Ensure at least 1 death to avoid div by zero
            if deaths == 0: deaths = 1
            
            time_played = games * random.randint(600, 1200) # 10-20 mins per game
            damage = kills * random.randint(100, 150)
            
            self.players.append({
                "name": name,
                "kills": kills,
                "deaths": deaths,
                "damage": damage,
                "time": time_played,
                "games": games,
                "wins": wins
            })

    async def connect(self):
        pass

    async def close(self):
        pass

    @asynccontextmanager
    async def connection(self):
        yield self

    async def execute(self, query: str, params: Optional[Tuple] = None):
        logger.info(f"Mock Execute: {query}")
        pass

    async def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Any]:
        logger.info(f"Mock Fetch One: {query}")
        query = query.lower()

        # Latest Session Date
        if "substr(s.round_date, 1, 10)" in query and "from rounds s" in query:
            return (datetime.now().strftime("%Y-%m-%d"),)

        # Max Gaming Session ID
        if "max(gaming_session_id)" in query:
            return (100,)

        # Player Count in Session
        if "count(distinct player_guid)" in query:
            return (12,)

        # Live Session
        if "live-session" in query or "current_date" in query:
            return (datetime.now(), 5, 12) # last_round, rounds, players
        
        # Latest Round
        if "stopwatch_time" in query and "limit 1" in query:
            return ("Supply Depot", datetime.now(), 600)

        # Player Stats
        if "player_comprehensive_stats p" in query and "sum(p.kills)" in query:
            player_name = params[0] if params else "Unknown"
            # Find player or return random
            p = next((x for x in self.players if x["name"].lower() == player_name.lower()), self.players[0])
            return (
                p["kills"], p["deaths"], p["damage"], p["time"], p["games"], 
                p["kills"] * 10, # xp
                p["wins"], 
                datetime.now() # last_seen
            )

        # Link Player
        if "player_links" in query:
            return None # Not linked

        # Player Exists Check
        if "select 1 from player_comprehensive_stats" in query:
            return (1,)

        return None

    async def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Any]:
        logger.info(f"Mock Fetch All: {query}")
        query = query.lower()

        # Rounds in Session (fetch_session_data)
        if "from rounds" in query and "gaming_session_id =" in query:
             # id, map_name, round_number, actual_time
             return [
                 (1, "Supply Depot", 1, "15:00"),
                 (2, "Supply Depot", 2, "14:30"),
                 (3, "Goldrush", 1, "20:00"),
                 (4, "Goldrush", 2, "18:45"),
             ]

        # Leaderboard
        if "leaderboard" in query or ("player_comprehensive_stats" in query and "group by" in query):
            results = []
            for p in self.players:
                # name, value(dpm), sessions, kills, deaths, kd
                dpm = p["damage"] / (p["time"] / 60)
                kd = p["kills"] / p["deaths"] if p["deaths"] > 0 else p["kills"]
                
                # If query asks for specific stat, we might need to adjust, but for now return generic structure
                # The api.py expects: name, value, sessions, kills, deaths, kd
                # Note: The order of columns in the mock response MUST match the SELECT clause in api.py
                # api.py selects: player_name, value, sessions_played, total_kills, total_deaths, kd_ratio
                results.append((p["name"], dpm, 10, p["kills"], p["deaths"], kd))
            
            # Sort by value (2nd element)
            results.sort(key=lambda x: x[1], reverse=True)
            return results

        # Recent Matches
        if "matches" in query or "limit" in query:
            # Return dummy matches
            # map_name, date, round, duration, winner, outcome
            maps = ["Supply Depot", "Goldrush", "Oasis", "Fuel Dump", "Radar", "Railgun", "Battery"]
            matches = []
            
            current_time = datetime.now()
            for i in range(20):
                match_map = random.choice(maps)
                match_time = current_time - timedelta(hours=i*0.5)
                duration = f"{random.randint(10, 29)}:{random.randint(10, 59)}"
                winner = random.choice(["Allies", "Axis"])
                outcome = random.choice(["Victory", "Defeat"]) # From perspective of... usually handled by frontend but here just string
                
                # Schema: id, map_name, round_number, actual_time, winner_team, round_outcome, round_date
                matches.append((
                    i + 1000, # id
                    match_map, # map_name
                    (i % 2) + 1, # round_number
                    duration, # actual_time
                    winner, # winner_team
                    outcome, # round_outcome
                    match_time # round_date
                ))
                
            return matches

        # Community - Clips
        if "select" in query and "from clips" in query:
            return MockAdapterV2._clips
            
        # Community - Configs
        if "select" in query and "from configs" in query:
            return MockAdapterV2._configs

        # Player Search
        if "player_name ilike" in query:
            return [(p["name"],) for p in self.players]

        return []

    async def execute(self, query: str, params: Optional[Tuple] = None):
        logger.info(f"Mock Execute: {query}")
        query = query.lower()
        
        # Insert Clip
        if "insert into clips" in query:
            # params: title, author, url, description
            new_id = len(MockAdapterV2._clips) + 1
            MockAdapterV2._clips.insert(0, {
                "id": new_id,
                "title": params[0],
                "author": params[1],
                "url": params[2],
                "views": 0,
                "likes": 0,
                "date": datetime.now().strftime("%Y-%m-%d")
            })
            return
            
        # Insert Config
        if "insert into configs" in query:
            # params: title, author, description, content
            new_id = len(MockAdapterV2._configs) + 1
            MockAdapterV2._configs.insert(0, {
                "id": new_id,
                "title": params[0],
                "author": params[1],
                "downloads": 0,
                "description": params[2],
                "date": datetime.now().strftime("%Y-%m-%d")
            })
            return

    async def fetch_val(self, query: str, params: Optional[Tuple] = None) -> Any:
        return None

def create_mock_adapter(**kwargs) -> DatabaseAdapter:
    return MockAdapterV2()
