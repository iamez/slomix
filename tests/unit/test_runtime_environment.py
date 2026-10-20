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


@pytest.mark.parametrize('explicit', [False, True])
def test_bot_metrics_paths_use_external_log_root(configuration, monkeypatch, explicit):
    from bot.config import BotConfig
    root, config = configuration
    monkeypatch.chdir(root)
    monkeypatch.setenv('SLOMIX_ENV_FILE', str(config))
    monkeypatch.setenv('BOT_ENVIRONMENT', 'dev')
    monkeypatch.setenv('SSH_ENABLED', 'false')
    logs = config.parent / 'mutable-logs'
    monkeypatch.setenv('BOT_LOG_DIR', str(logs))
    custom = str(config.parent / 'custom-store' / 'custom.db')
    monkeypatch.delenv('METRICS_DB_PATH', raising=False)
    if explicit:
        monkeypatch.setenv('METRICS_DB_PATH', custom)
    loaded = BotConfig()
    assert loaded.metrics_log_dir == str(logs / 'metrics')
    assert loaded.metrics_db_path == (custom if explicit else str(logs / 'metrics' / 'metrics.db'))


def test_bot_entrypoint_explicit_environment_never_loads_ancestor(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path
    source = Path(__file__).resolve().parents[2] / 'bot/ultimate_bot.py'
    parent = tmp_path / 'ancestor'
    entry = parent / 'release' / 'bot' / 'ultimate_bot.py'
    entry.parent.mkdir(parents=True)
    entry.write_bytes(source.read_bytes())
    (parent / '.env').write_text('RUNTIME_ANCESTOR_SHOULD_NOT_LOAD=unexpected\n')
    explicit = tmp_path / 'explicit.env'
    explicit.write_text(f'BOT_LOG_DIR={tmp_path / "external-logs"}\nLOG_LEVEL=ERROR\n')
    explicit.chmod(0o600)
    code = r'''
import importlib.util, json, os, sys
import dotenv
calls = []
original = dotenv.load_dotenv
def observed(*args, **kwargs):
    calls.append(bool(args or kwargs))
    return original(*args, **kwargs)
dotenv.load_dotenv = observed
sys.path.insert(0, sys.argv[1])
spec = importlib.util.spec_from_file_location('entrypoint_fixture', sys.argv[2])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert 'RUNTIME_ANCESTOR_SHOULD_NOT_LOAD' not in os.environ
assert calls == [], calls
assert module.os.environ['BOT_LOG_DIR'] == sys.argv[3]
print(json.dumps({'ancestor_loaded': False, 'legacy_loader_calls': len(calls)}))
'''
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(tmp_path), 'SLOMIX_ENV_FILE': str(explicit),
           'BOT_ENVIRONMENT': 'dev', 'SSH_ENABLED': 'false', 'PYTHONDONTWRITEBYTECODE': '1'}
    result = subprocess.run([sys.executable, '-I', '-B', '-c', code, str(source.parents[1]),
                             str(entry), str(tmp_path / 'external-logs')], env=env, cwd=entry.parent,
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.splitlines()[-1]) == {'ancestor_loaded': False, 'legacy_loader_calls': 0}


def test_bot_entrypoint_environment_precedes_application_imports():
    import ast
    from pathlib import Path
    source = Path(__file__).resolve().parents[2] / 'bot/ultimate_bot.py'
    tree = ast.parse(source.read_text())
    top = tree.body
    boundary = next(i for i, node in enumerate(top) if isinstance(node, ast.Expr)
                    and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                    and node.value.func.id == 'load_environment')
    bot_imports = [i for i, node in enumerate(top) if isinstance(node, ast.ImportFrom)
                   and (node.module or '').startswith('bot.')]
    assert bot_imports and boundary < min(bot_imports)
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id == 'load_dotenv' for node in ast.walk(tree))


@pytest.mark.parametrize('key', ['LC_PAPER', 'LC_NAME', 'LC_ADDRESS', 'LC_TELEPHONE',
                                 'LC_MEASUREMENT', 'LC_IDENTIFICATION'])
def test_locale_metadata_still_cannot_override_approved_configuration(key):
    from shared.runtime_environment import refuse_unapproved_environment

    refuse_unapproved_environment({}, {key: 'C'}, set())
    with pytest.raises(ValueError, match='Unapproved'):
        refuse_unapproved_environment({key: 'C'}, {key: 'different'}, set())
