"""Explicit constructor configuration, not yet an import-side-effect boundary."""

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import postgresql_database_manager as module


class FalseyConfig(SimpleNamespace):
    def __bool__(self):
        return False


@pytest.mark.parametrize("config_type", [SimpleNamespace, FalseyConfig])
def test_explicit_config_bypasses_loader_and_preserves_identity(monkeypatch, tmp_path, config_type):
    loader = Mock(side_effect=AssertionError("Legacy loader must not be used"))
    monkeypatch.setattr(module, "load_config", loader)
    config = config_type(database_type="postgresql", excluded_maps=frozenset({"fixture"}))
    manager = module.PostgreSQLDatabaseManager(str(tmp_path), config=config)
    assert manager.config is config
    assert manager.stats_dir == tmp_path
    assert manager.pool is None
    assert manager.stats["files_processed"] == 0
    assert manager.config.excluded_maps == frozenset({"fixture"})
    loader.assert_not_called()


@pytest.mark.parametrize("explicit_none", [False, True])
def test_default_constructor_keeps_legacy_loader(monkeypatch, explicit_none):
    config = SimpleNamespace(database_type="postgresql")
    loader = Mock(return_value=config)
    monkeypatch.setattr(module, "load_config", loader)
    manager = module.PostgreSQLDatabaseManager(**({"config": None} if explicit_none else {}))
    loader.assert_called_once_with()
    assert manager.config is config
    assert manager.stats_dir == Path("local_stats")
    assert manager.pool is None


def test_default_loader_failure_is_not_silenced(monkeypatch):
    monkeypatch.setattr(module, "load_config", Mock(side_effect=ValueError("fixture configuration")))
    with pytest.raises(ValueError, match="fixture configuration"):
        module.PostgreSQLDatabaseManager()


def test_explicit_config_still_requires_postgresql(monkeypatch):
    loader = Mock(side_effect=AssertionError("must not fall back"))
    monkeypatch.setattr(module, "load_config", loader)
    with pytest.raises(ValueError, match="requires PostgreSQL"):
        module.PostgreSQLDatabaseManager(config=SimpleNamespace(database_type="sqlite"))
    loader.assert_not_called()


def test_constructor_subprocess_uses_supplied_config_without_connecting(tmp_path):
    code = r'''
import json
from types import SimpleNamespace
import postgresql_database_manager as module

def forbidden(*args, **kwargs):
    raise AssertionError("Ambient configuration or database access attempted")

module.load_config = forbidden
module.asyncpg.create_pool = forbidden
config = SimpleNamespace(database_type="postgresql", excluded_maps=frozenset())
manager = module.PostgreSQLDatabaseManager(config=config)
assert manager.config is config and manager.pool is None
player, issues = manager.validate_player_stats({
    "kills": 3, "objective_stats": {"headshot_kills": 5},
})
assert player["objective_stats"]["headshot_kills"] == 3
assert issues
print(json.dumps({"config": "caller", "pool": "absent", "headshot_kills": 3}))
'''
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("DISCORD_", "POSTGRES_"))}
    env["BOT_LOG_DIR"] = str(tmp_path / "logs")
    result = subprocess.run([sys.executable, "-c", code], env=env,
                            cwd=Path(__file__).resolve().parents[2],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.splitlines()[-1]) == {
        "config": "caller", "pool": "absent", "headshot_kills": 3,
    }
    print("Manager subprocess proof: explicit config, no connection, canonical validation exercised")
