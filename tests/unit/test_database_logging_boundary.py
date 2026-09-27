"""Keep database logging usable without configuring a bot process."""

import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

from shared import database_logging as subject


def test_legacy_exports_are_identical():
    """Legacy callers must receive the original shared function objects."""
    from bot import logging_config

    for name in ("_exc_info_for", "log_database_operation", "log_stats_import",
                 "log_performance_warning"):
        assert getattr(logging_config, name) is getattr(subject, name)


def test_success_records_and_threshold(caplog):
    """Preserve logger names, formatting and the strict slow-operation threshold."""
    caplog.set_level(logging.DEBUG)
    subject.log_database_operation("SELECT", "rows", duration=1.2345)
    subject.log_database_operation("SELECT", "rows", duration=0)
    subject.log_stats_import("sample", 1, 2, 3, duration=1.2345)
    subject.log_performance_warning("query", 1.0)
    subject.log_performance_warning("query", 1.25)
    assert [(r.name, r.levelname, r.getMessage()) for r in caplog.records] == [
        ("bot.database", "DEBUG", "✓ DB SELECT [1.234s]: rows"),
        ("bot.database", "DEBUG", "✓ DB SELECT: rows"),
        ("bot.database", "INFO", "✓ IMPORTED [1.23s]: sample | Rounds: 1, Players: 2, Weapons: 3"),
        ("bot.performance", "WARNING", "⚠️ SLOW OPERATION [1.25s]: query"),
    ]


@pytest.mark.parametrize("error", [ValueError("bad input"), "bad input"])
@pytest.mark.parametrize("kind", ["operation", "import"])
def test_error_records(caplog, error, kind):
    """Exceptions retain their identity; text errors do not invent tracebacks."""
    if kind == "operation":
        subject.log_database_operation("INSERT", "rows", duration=2, error=error)
        expected = "❌ DB INSERT FAILED [2.000s]: rows | Error: bad input"
    else:
        subject.log_stats_import("sample", duration=2, error=error)
        expected = "❌ IMPORT FAILED [2.00s]: sample | Error: bad input"
    record, = caplog.records
    assert (record.name, record.levelname, record.getMessage()) == (
        "bot.database", "ERROR", expected,
    )
    if isinstance(error, BaseException):
        assert record.exc_info[1] is error
    else:
        assert not record.exc_info


def test_independent_process_emits_without_setup(tmp_path):
    """A fresh process emits records without bot imports or implicit setup."""
    script = '''
import importlib.abc
import logging
import os
from pathlib import Path
import sys

class BlockBot(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"bot", "discord", "dotenv", "website"}:
            raise ModuleNotFoundError("Forbidden dependency: " + fullname)

sys.meta_path.insert(0, BlockBot())
root = logging.getLogger()
before = (tuple(root.handlers), root.level, dict(os.environ))
from shared import database_logging
assert before == (tuple(root.handlers), root.level, dict(os.environ))
assert not Path(os.environ["BOT_LOG_DIR"]).exists()
records = []
class Capture(logging.Handler):
    def emit(self, record):
        records.append(record)
root.addHandler(Capture())
root.setLevel(logging.DEBUG)
database_logging.log_database_operation("SELECT", "probe")
database_logging.log_stats_import("probe", player_count=1)
database_logging.log_performance_warning("probe", 2)
assert [r.levelname for r in records] == ["DEBUG", "INFO", "WARNING"]
assert [r.name for r in records] == ["bot.database", "bot.database", "bot.performance"]
assert not Path(os.environ["BOT_LOG_DIR"]).exists()
print("runtime logging proof: 3 records; no bot imports or log directory")
'''
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "BOT_LOG_DIR": str(tmp_path / "not-created")},
        capture_output=True, text=True, timeout=15, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "runtime logging proof: 3 records" in result.stdout
