"""Release config is explicit, external and literal; legacy selection is retained."""
import os

import pytest

from shared.runtime_environment import explicit_env_file, load_environment


@pytest.fixture
def configuration(tmp_path, monkeypatch):
    root = tmp_path / "release"
    root.mkdir()
    (root / ".slomix-release.json").write_text("{}")
    config = tmp_path / "service.env"
    config.write_text("RUNTIME_TEST_LITERAL='${RUNTIME_TEST_AMBIENT}'\nRUNTIME_TEST_WIN=file\n")
    config.chmod(0o600)
    monkeypatch.delenv("SLOMIX_ENV_FILE", raising=False)
    for name in ("RUNTIME_TEST_LITERAL", "RUNTIME_TEST_WIN", "RUNTIME_TEST_AMBIENT"):
        monkeypatch.delenv(name, raising=False)
    return root, config


def test_release_refuses_implicit_environment(configuration):
    root, _ = configuration
    with pytest.raises(ValueError, match="requires explicit"):
        load_environment(root=root)


@pytest.mark.parametrize("damage", ["empty", "relative", "missing", "directory", "public", "symlink", "inside"])
def test_invalid_explicit_environment_never_falls_back(configuration, monkeypatch, damage):
    root, config = configuration
    selected = str(config)
    if damage == "empty":
        selected = ""
    elif damage == "relative":
        selected = "service.env"
    elif damage == "missing":
        selected = str(config.parent / "absent.env")
    elif damage == "directory":
        selected = str(config.parent)
    elif damage == "public":
        config.chmod(0o644)
    elif damage == "symlink":
        link = config.parent / "linked.env"
        link.symlink_to(config)
        selected = str(link)
    else:
        inside = root / ".env"
        inside.write_text("RUNTIME_TEST_WIN=wrong\n")
        inside.chmod(0o600)
        selected = str(inside)
    monkeypatch.setenv("SLOMIX_ENV_FILE", selected)
    with pytest.raises(ValueError, match="absolute canonical private"):
        load_environment(root / ".env", root=root)
    assert "RUNTIME_TEST_WIN" not in os.environ


def test_literal_values_and_process_precedence(configuration, monkeypatch):
    root, config = configuration
    monkeypatch.setenv("SLOMIX_ENV_FILE", str(config))
    monkeypatch.setenv("RUNTIME_TEST_AMBIENT", "do-not-expand")
    monkeypatch.setenv("RUNTIME_TEST_WIN", "process")
    load_environment(root=root)
    assert explicit_env_file(root) == config
    assert os.environ["RUNTIME_TEST_LITERAL"] == "${RUNTIME_TEST_AMBIENT}"
    assert os.environ["RUNTIME_TEST_WIN"] == "process"


def test_invalid_syntax_refuses_before_partial_environment(configuration, monkeypatch):
    root, config = configuration
    config.write_text("RUNTIME_TEST_WIN=partial\nBROKEN='unterminated\n")
    monkeypatch.setenv("SLOMIX_ENV_FILE", str(config))
    with pytest.raises(ValueError, match="Invalid external dotenv syntax"):
        load_environment(root=root)
    assert "RUNTIME_TEST_WIN" not in os.environ


def test_unmarked_legacy_uses_supplied_path(tmp_path, monkeypatch):
    config = tmp_path / "legacy.env"
    config.write_text("RUNTIME_TEST_LEGACY=loaded\n")
    monkeypatch.delenv("SLOMIX_ENV_FILE", raising=False)
    monkeypatch.delenv("RUNTIME_TEST_LEGACY", raising=False)
    assert explicit_env_file(tmp_path) is None
    load_environment(config, root=tmp_path)
    assert os.environ["RUNTIME_TEST_LEGACY"] == "loaded"


def test_bot_external_mode_ignores_cwd_json(configuration, monkeypatch):
    root, config = configuration
    monkeypatch.chdir(root)
    (root / "bot_config.json").write_text('{"POSTGRES_HOST":"wrong-host"}')
    monkeypatch.setenv("SLOMIX_ENV_FILE", str(config))
    monkeypatch.setenv("BOT_ENVIRONMENT", "dev")
    monkeypatch.setenv("SSH_ENABLED", "false")
    monkeypatch.setenv("POSTGRES_HOST", "expected-host")
    monkeypatch.delenv("STATS_DIRECTORY", raising=False)
    from bot.config import BotConfig

    loaded = BotConfig()
    assert loaded.config_file is None
    assert loaded.postgres_host == "expected-host"
    # Explicit JSON is allowed, but it must be external/private and valid.
    external_json = config.parent / "explicit.json"
    external_json.write_text("[]")
    external_json.chmod(0o600)
    with pytest.raises(ValueError, match="Invalid explicit bot JSON"):
        BotConfig(str(external_json))
    external_json.write_text('{"STATS_DIRECTORY":"/explicit/stats"}')
    assert BotConfig(str(external_json)).stats_directory == "/explicit/stats"


def test_migration_and_sentinel_use_same_explicit_file(configuration, monkeypatch):
    from scripts import apply_migrations, data_plausibility_audit

    root, config = configuration
    monkeypatch.setenv("SLOMIX_ENV_FILE", str(config))
    assert apply_migrations.resolve_env_file(root) == config
    data_plausibility_audit._load_dotenv(root)  # noqa: SLF001 - script boundary
    assert os.environ["RUNTIME_TEST_WIN"] == "file"
