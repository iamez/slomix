"""Run the real shared conftest in fresh, network-denied pytest processes."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = r'''
import importlib.abc
import sys
import asyncpg
import pytest

attempts = []
async def denied_pool(*args, **kwargs):
    attempts.append('pool')
    raise RuntimeError('SYNTHETIC_DATABASE_UNAVAILABLE')
asyncpg.create_pool = denied_pool
asyncpg.connect = denied_pool

class NoConfig(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'bot.config':
            raise AssertionError('COLLECTION_IMPORTED_APPLICATION_CONFIG')
sys.meta_path.insert(0, NoConfig())
result = pytest.main(sys.argv[1:])
print('POOL_ATTEMPTS=' + str(len(attempts)))
raise SystemExit(result)
'''


def run_shared_collection(tmp_path, source, *, requested=False, collect=False):
    # Copy actual fixture code, not a model of its behavior. A private cwd and
    # explicit plugin list prevent unrelated repository test imports/plugins.
    (tmp_path / "conftest.py").write_bytes((ROOT / "tests/conftest.py").read_bytes())
    (tmp_path / "pytest.ini").write_text("[pytest]\nasyncio_mode = auto\n")
    (tmp_path / "test_probe.py").write_text(source)
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("POSTGRES_", "PG", "PYTEST_", "RUNTIME_EVENTS_TEST_"))
           and key != "GITHUB_ACTIONS"}
    env.update(PYTHONPATH=str(ROOT), PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    if requested:
        env.update(POSTGRES_TEST_HOST="127.0.0.1", POSTGRES_TEST_PORT="5432",
                   POSTGRES_TEST_DATABASE="etlegacy_test", POSTGRES_TEST_USER="etlegacy_user",
                   POSTGRES_TEST_PASSWORD="synthetic", RUNTIME_EVENTS_TEST_CI="true",
                   GITHUB_ACTIONS="true")
    args = [sys.executable, "-c", RUNNER, "-q", "-p", "pytest_asyncio.plugin",
            "-c", str(tmp_path / "pytest.ini"), "test_probe.py"]
    if collect:
        args.append("--collect-only")
    return subprocess.run(args, cwd=tmp_path, env=env, capture_output=True,
                          text=True, timeout=20)


@pytest.mark.parametrize("requested", [False, True])
@pytest.mark.parametrize("collect", [False, True])
def test_discovery_and_pure_tests_never_probe_database(tmp_path, requested, collect):
    result = run_shared_collection(tmp_path, "def test_pure(): assert 2 + 2 == 4\n",
                                   requested=requested, collect=collect)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "POOL_ATTEMPTS=0" in result.stdout


def test_db_fixture_without_opt_in_is_explicitly_skipped(tmp_path):
    result = run_shared_collection(
        tmp_path, "async def test_needs_db(db_adapter): raise AssertionError('BODY_RAN')\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 skipped" in result.stdout
    assert "POOL_ATTEMPTS=0" in result.stdout


def test_opted_in_db_failure_is_error_not_skip(tmp_path):
    result = run_shared_collection(
        tmp_path, "async def test_needs_db(db_adapter): raise AssertionError('BODY_RAN')\n",
        requested=True)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "SYNTHETIC_DATABASE_UNAVAILABLE" in result.stdout
    assert "1 error" in result.stdout
    assert "POOL_ATTEMPTS=1" in result.stdout


def test_collect_only_of_db_fixture_does_not_set_it_up(tmp_path):
    result = run_shared_collection(
        tmp_path, "async def test_needs_db(db_adapter): raise AssertionError('BODY_RAN')\n",
        requested=True, collect=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "POOL_ATTEMPTS=0" in result.stdout
