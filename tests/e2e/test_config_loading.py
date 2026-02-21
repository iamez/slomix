"""
End-to-end test: Configuration loading and validation.

Verifies that the BotConfig class can load configuration from
environment variables and that critical settings are parsed correctly.
This is a lightweight E2E test that does not require Discord or database
connections.
"""

import pytest
import os


class TestConfigLoadingE2E:
    """Verify the production config loader works end-to-end."""

    def test_bot_config_loads_from_env(self, monkeypatch):
        """BotConfig initializes successfully from environment variables."""
        # Set minimal required env vars
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test_token_for_e2e")
        monkeypatch.setenv("DATABASE_TYPE", "postgres")
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_PORT", "5432")
        monkeypatch.setenv("DB_NAME", "etlegacy_test")
        monkeypatch.setenv("DB_USER", "etlegacy_user")
        monkeypatch.setenv("DB_PASSWORD", "test_password")
        monkeypatch.setenv("AUTOMATION_ENABLED", "false")
        monkeypatch.setenv("SSH_ENABLED", "false")

        from bot.config import BotConfig
        config = BotConfig()

        # Verify critical properties are accessible
        assert config is not None
        assert hasattr(config, "webhook_trigger_whitelist")

    def test_webhook_whitelist_parsing(self, monkeypatch):
        """BotConfig parses WEBHOOK_TRIGGER_WHITELIST correctly from env."""
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test_token")
        monkeypatch.setenv("AUTOMATION_ENABLED", "false")
        monkeypatch.setenv("SSH_ENABLED", "false")
        monkeypatch.setenv("WEBHOOK_TRIGGER_WHITELIST", "111222333444555666,999888777666555444")

        from bot.config import BotConfig
        config = BotConfig()

        assert isinstance(config.webhook_trigger_whitelist, list)
        assert "111222333444555666" in config.webhook_trigger_whitelist
        assert "999888777666555444" in config.webhook_trigger_whitelist

    def test_empty_webhook_whitelist(self, monkeypatch):
        """BotConfig handles empty WEBHOOK_TRIGGER_WHITELIST gracefully."""
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test_token")
        monkeypatch.setenv("AUTOMATION_ENABLED", "false")
        monkeypatch.setenv("SSH_ENABLED", "false")
        monkeypatch.setenv("WEBHOOK_TRIGGER_WHITELIST", "")

        from bot.config import BotConfig
        config = BotConfig()

        assert isinstance(config.webhook_trigger_whitelist, list)
        assert len(config.webhook_trigger_whitelist) == 0
