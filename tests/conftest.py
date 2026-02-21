"""
Pytest Configuration and Shared Fixtures
Provides test fixtures for database, Discord mocks, and async operations
"""

import pytest
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from typing import Dict, Any

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import bot modules
from bot.core.database_adapter import DatabaseAdapter, PostgreSQLAdapter
from bot.config import BotConfig


# ============================================
# EVENT LOOP CONFIGURATION
# ============================================

@pytest.fixture(scope="session")
def event_loop_policy():
    """Set event loop policy for async tests"""
    return asyncio.get_event_loop_policy()


@pytest.fixture(scope="function")
def event_loop(event_loop_policy):
    """Create an event loop for each test function"""
    loop = event_loop_policy.new_event_loop()
    yield loop
    loop.close()


# ============================================
# DATABASE FIXTURES
# ============================================

@pytest.fixture(scope="session")
def test_db_config() -> Dict[str, Any]:
    """
    Test database configuration

    Uses environment variables if available, falls back to test defaults
    For CI/CD, set POSTGRES_TEST_* environment variables
    """
    return {
        "db_type": "postgresql",
        "host": os.getenv("POSTGRES_TEST_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_TEST_PORT", "5432")),
        "database": os.getenv("POSTGRES_TEST_DATABASE", "etlegacy_test"),
        "user": os.getenv("POSTGRES_TEST_USER", "etlegacy_user"),
        "password": os.getenv("POSTGRES_TEST_PASSWORD", "etlegacy_test_password"),
        "min_pool_size": 2,
        "max_pool_size": 5
    }


@pytest.fixture
async def db_adapter(test_db_config):
    """
    Provide a database adapter for testing

    Creates a fresh adapter for each test and ensures cleanup
    Automatically rolls back transactions after test
    """
    adapter = PostgreSQLAdapter(
        host=test_db_config["host"],
        port=test_db_config["port"],
        database=test_db_config["database"],
        user=test_db_config["user"],
        password=test_db_config["password"],
        min_pool_size=test_db_config["min_pool_size"],
        max_pool_size=test_db_config["max_pool_size"]
    )

    try:
        await adapter.connect()
        yield adapter
    finally:
        await adapter.close()


@pytest.fixture
async def clean_test_db(db_adapter):
    """
    Provide a clean test database for each test

    Truncates all tables before and after test
    Use this fixture when you need isolated database state
    """
    # Truncate tables before test
    await _truncate_test_tables(db_adapter)

    yield db_adapter

    # Truncate tables after test
    await _truncate_test_tables(db_adapter)


async def _truncate_test_tables(adapter: DatabaseAdapter):
    """Helper to truncate all test tables"""
    tables = [
        "weapon_comprehensive_stats",
        "player_comprehensive_stats",
        "rounds",
        "processed_files",
        "session_teams",
        "player_aliases",
        "player_links"
    ]

    try:
        for table in tables:
            await adapter.execute(f"TRUNCATE TABLE {table} CASCADE")
    except Exception:
        # Ignore errors if tables don't exist (for initial setup)
        pass


# ============================================
# DISCORD MOCK FIXTURES
# ============================================

@pytest.fixture
def mock_bot():
    """Mock Discord bot instance"""
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 123456789
    bot.user.name = "TestBot"
    bot.user.display_name = "TestBot"

    # Add db_adapter attribute (many cogs expect this)
    bot.db_adapter = MagicMock()

    return bot


@pytest.fixture
def mock_guild():
    """Mock Discord guild (server)"""
    guild = MagicMock()
    guild.id = 987654321
    guild.name = "Test Server"
    return guild


@pytest.fixture
def mock_channel():
    """Mock Discord text channel"""
    channel = MagicMock()
    channel.id = 111222333
    channel.name = "test-channel"
    channel.send = AsyncMock(return_value=MagicMock())
    return channel


@pytest.fixture
def mock_author():
    """Mock Discord user (message author)"""
    author = MagicMock()
    author.id = 231165917604741121  # Owner ID from .env.example
    author.name = "testuser"
    author.display_name = "TestUser"
    author.mention = "<@231165917604741121>"
    return author


@pytest.fixture
def mock_message(mock_author, mock_channel, mock_guild):
    """Mock Discord message"""
    message = MagicMock()
    message.id = 444555666
    message.author = mock_author
    message.channel = mock_channel
    message.guild = mock_guild
    message.content = "!test command"
    message.created_at = asyncio.get_event_loop().time()
    return message


@pytest.fixture
def mock_ctx(mock_bot, mock_author, mock_channel, mock_guild, mock_message):
    """Mock Discord command context"""
    ctx = MagicMock()
    ctx.bot = mock_bot
    ctx.author = mock_author
    ctx.channel = mock_channel
    ctx.guild = mock_guild
    ctx.message = mock_message
    ctx.send = AsyncMock(return_value=MagicMock())
    ctx.reply = AsyncMock(return_value=MagicMock())
    return ctx


@pytest.fixture
def mock_webhook():
    """Mock Discord webhook"""
    webhook = MagicMock()
    webhook.id = 1234567890123456789  # Valid webhook ID format
    webhook.name = "ET:Legacy Stats"
    webhook.avatar_url = "https://example.com/avatar.png"
    return webhook


# ============================================
# STATS FILE FIXTURES
# ============================================

@pytest.fixture
def sample_stats_r1() -> str:
    """
    Sample R1 (round 1) stats file content

    Contains basic match stats for testing parser
    """
    return """ET:Legacy Stats File
Version: 1.0
Map: goldrush
GameType: objective
Round: 1
Date: 2025-12-17
Time: 12:00:00

Player Stats:
PlayerName,Team,Kills,Deaths,DamageGiven,DamageReceived,Accuracy,Headshots,Revives,AmmoGiven,HealthGiven,TimePlayed,Efficiency,KDR,DPM
TestPlayer1,axis,15,8,2500,1200,28.5,3,5,150,200,1800,65.2,1.88,83.3
TestPlayer2,allies,12,10,2100,1500,25.0,2,8,200,300,1800,54.5,1.20,70.0
TestPlayer3,axis,20,5,3000,800,32.1,5,3,100,100,1800,80.0,4.00,100.0
"""


@pytest.fixture
def sample_stats_r2() -> str:
    """
    Sample R2 (round 2) stats file content

    Contains cumulative stats (R1 + R2) for differential calculation
    """
    return """ET:Legacy Stats File
Version: 1.0
Map: goldrush
GameType: objective
Round: 2
Date: 2025-12-17
Time: 12:30:00

Player Stats:
PlayerName,Team,Kills,Deaths,DamageGiven,DamageReceived,Accuracy,Headshots,Revives,AmmoGiven,HealthGiven,TimePlayed,Efficiency,KDR,DPM
TestPlayer1,allies,28,15,4800,2400,30.2,6,10,300,400,3600,62.0,1.87,80.0
TestPlayer2,axis,25,18,4200,2800,27.5,4,15,400,500,3600,58.1,1.39,70.0
TestPlayer3,allies,35,12,5500,1600,33.0,9,6,200,200,3600,74.5,2.92,91.7
"""


@pytest.fixture
def sample_stats_malformed() -> str:
    """Malformed stats file for error handling tests"""
    return """INVALID HEADER
No proper format
Missing fields
"""


@pytest.fixture
def sample_stats_file(tmp_path, sample_stats_r1) -> Path:
    """
    Create a temporary sample stats file

    Returns path to the file for parser testing
    """
    stats_file = tmp_path / "endstats_goldrush_20251217_120000_R1.txt"
    stats_file.write_text(sample_stats_r1)
    return stats_file


# ============================================
# CONFIGURATION FIXTURES
# ============================================

@pytest.fixture
def mock_config(monkeypatch):
    """
    Mock configuration for testing

    Overrides BotConfig class to return test values
    """
    # Override environment variables for testing
    test_env = {
        "DISCORD_BOT_TOKEN": "test_token_123",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_DATABASE": "etlegacy_test",
        "POSTGRES_USER": "etlegacy_user",
        "POSTGRES_PASSWORD": "test_password",
        "STATS_CHANNEL_ID": "111222333",
        "ADMIN_CHANNEL_ID": "444555666",
        "OWNER_USER_ID": "231165917604741121",
        "AUTOMATION_ENABLED": "false",
        "SSH_ENABLED": "false",
        "WEBHOOK_TRIGGER_CHANNEL_ID": "0",
    }

    for key, value in test_env.items():
        monkeypatch.setenv(key, value)

    return BotConfig


# ============================================
# UTILITY FIXTURES
# ============================================

@pytest.fixture
def fixture_dir():
    """Get path to fixtures directory with sample stats files"""
    return Path(__file__).parent / "fixtures" / "sample_stats_files"


@pytest.fixture
def temp_stats_dir(tmp_path):
    """Create a temporary stats directory for file operations"""
    stats_dir = tmp_path / "local_stats"
    stats_dir.mkdir()
    return stats_dir


@pytest.fixture
def capture_logs(caplog):
    """
    Fixture to capture log messages during tests

    Usage:
        def test_something(capture_logs):
            # your test code
            assert "expected log message" in capture_logs.text
    """
    return caplog


# ============================================
# PYTEST CONFIGURATION
# ============================================

def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests"
    )
    config.addinivalue_line(
        "markers", "requires_db: marks tests that require database connection"
    )


def pytest_collection_modifyitems(config, items):
    """
    Automatically mark tests based on their location

    - tests/integration/* → integration marker
    - tests/e2e/* → e2e marker
    - tests with db_adapter fixture → requires_db marker
    """
    # Check if test database is available (cached result)
    db_available = _check_test_database_available()

    for item in items:
        # Add markers based on test location
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)

        # Add requires_db marker if test uses db fixtures
        if "db_adapter" in item.fixturenames or "clean_test_db" in item.fixturenames:
            item.add_marker(pytest.mark.requires_db)

        # Skip requires_db tests if database is unavailable
        if item.get_closest_marker("requires_db") and not db_available:
            item.add_marker(pytest.mark.skip(
                reason="Test database unavailable (etlegacy_test). "
                       "Set POSTGRES_TEST_* environment variables to configure."
            ))


def _check_test_database_available() -> bool:
    """
    Check if the test database is available.

    This runs once at collection time to avoid repeated connection attempts.
    Returns True if we can connect, False otherwise.
    """
    import asyncio

    async def _try_connect():
        try:
            adapter = PostgreSQLAdapter(
                host=os.getenv("POSTGRES_TEST_HOST", "localhost"),
                port=int(os.getenv("POSTGRES_TEST_PORT", "5432")),
                database=os.getenv("POSTGRES_TEST_DATABASE", "etlegacy_test"),
                user=os.getenv("POSTGRES_TEST_USER", "etlegacy_user"),
                password=os.getenv("POSTGRES_TEST_PASSWORD", "etlegacy_test_password"),
                min_pool_size=1,
                max_pool_size=2
            )
            await adapter.connect()
            await adapter.close()
            return True
        except Exception:
            return False

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_try_connect())
        loop.close()
        return result
    except Exception:
        return False
