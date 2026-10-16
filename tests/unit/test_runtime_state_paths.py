"""Real file outputs stay outside release cwd when state paths are configured."""
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.automation.file_tracker import FileTracker
from bot.cogs.server_control import ServerControl
from bot.cogs.stats_mixins import compare_mixin
from bot.services.automation.database_maintenance import DatabaseMaintenance
from bot.services.automation.metrics_logger import MetricsLogger
from bot.services.session_timing_shadow_service import SessionTimingShadowService
from tests.unit.test_session_timing_shadow_service import _FakeDB


@pytest.fixture
def external_state(tmp_path, monkeypatch):
    release = tmp_path / "release"
    release.mkdir()
    state = tmp_path / "state"
    monkeypatch.chdir(release)
    monkeypatch.setenv("BOT_LOG_DIR", str(state / "logs"))
    monkeypatch.setenv("MPLCONFIGDIR", str(state / "mpl-cache"))
    return release, state


@pytest.mark.asyncio
async def test_metrics_database_and_export_use_external_logs(external_state):
    release, state = external_state
    metrics = MetricsLogger(db_path="")
    try:
        await metrics.initialize_metrics_db()
        await metrics.log_event("release-path-proof", {"synthetic": True})
        exported = Path(await metrics.export_to_json())
        assert exported.parent == state / "logs/metrics"
        assert "release-path-proof" in exported.read_text()
        assert Path(metrics.metrics_db_path) == exported.parent / "metrics.db"
        assert Path(metrics.metrics_db_path).is_file()
    finally:
        await metrics.close()
    assert list(release.iterdir()) == []


def test_explicit_output_paths_win(external_state):
    release, state = external_state
    metrics = MetricsLogger(str(state / "custom.db"), str(state / "custom-metrics"))
    shadow = SessionTimingShadowService(None, state / "custom-shadow")
    assert metrics.log_dir == str(state / "custom-metrics")
    assert metrics.metrics_db_path == str(state / "custom.db")
    assert shadow.artifact_dir == state / "custom-shadow"
    assert list(release.iterdir()) == []


@pytest.mark.asyncio
async def test_maintenance_audit_and_shadow_share_external_logs(external_state, monkeypatch):
    release, state = external_state
    bot = SimpleNamespace(admin_channel_id=0)
    maintenance = DatabaseMaintenance(bot, None, 0)
    assert Path(maintenance.backup_dir) == state / "logs/backups"
    assert Path(maintenance.log_dir) == state / "logs"
    assert Path(maintenance.backup_dir).is_dir()
    monkeypatch.setenv("SSH_KEY_PATH", str(state / "absent-key"))
    control = ServerControl(bot)
    ctx = SimpleNamespace(author=SimpleNamespace(id=123))
    await control.log_action(ctx, "LOCAL_PROOF", "no remote action")
    audit = state / "logs/server_control_access.log"
    assert "LOCAL_PROOF" in audit.read_text()
    shadow = SessionTimingShadowService(_FakeDB())
    result = await shadow.compare_session([101, 102])
    assert Path(result.artifact_path).parent == state / "logs/timing_shadow"
    assert Path(result.artifact_path).stat().st_size > 0
    assert list(release.iterdir()) == []


@pytest.mark.asyncio
async def test_tracker_inspects_download_directory_not_cwd(external_state, caplog):
    release, state = external_state
    stats = state / "stats"
    stats.mkdir(parents=True)
    filename = "2026-10-09-120000-oasis-round-1.txt"
    (stats / filename).write_text("synthetic input; never imported\n")
    db = SimpleNamespace(fetch_all=AsyncMock(return_value=[]), fetch_one=AsyncMock(return_value=None))
    config = SimpleNamespace(stats_directory=str(stats), STARTUP_LOOKBACK_HOURS=168)
    startup = datetime(2026, 10, 9, 12)  # noqa: DTZ001 - tracker compares naive game filename timestamps
    tracker = FileTracker(db, config, startup, set())
    await tracker.sync_local_files_to_processed_table()
    assert db.fetch_all.await_args.args[1] == ([filename],)
    assert "1 unimported" in caplog.text
    assert await tracker.should_process_file(filename) is True
    assert list(release.iterdir()) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("send_failure", [False, True])
async def test_compare_chart_uses_memory_and_closes_attachment(external_state, monkeypatch, send_failure):
    release, _ = external_state
    # Real matplotlib/Discord objects, synthetic DB answers, no transport.
    import matplotlib.pyplot as plt

    monkeypatch.setattr(compare_mixin, "ensure_player_name_alias", AsyncMock())
    db = SimpleNamespace(fetch_one=AsyncMock(side_effect=[
        ("a" * 32, "Alpha"), (20, 10, 2, 2000, 4, 600), (50, 100, 10),
        ("b" * 32, "Beta"), (15, 10, 2, 1800, 3, 600), (40, 100, 8),
    ]))
    cog = SimpleNamespace(bot=SimpleNamespace(db_adapter=db, config=SimpleNamespace()))
    captured = []

    async def send(*args, **kwargs):
        if "file" in kwargs:
            attachment = kwargs["file"]
            captured.append(attachment.fp)
            assert attachment.filename == "comparison.png"
            assert attachment.fp.read(8) == b"\x89PNG\r\n\x1a\n"
            if send_failure:
                raise RuntimeError("synthetic send failure")

    ctx = SimpleNamespace(send=AsyncMock(side_effect=send), author=SimpleNamespace(display_name="proof"))
    await compare_mixin._StatsCompareMixin.compare.callback(cog, ctx, "Alpha", "Beta")  # noqa: SLF001 - command boundary
    assert len(captured) == 1
    assert captured[0].closed
    assert plt.get_fignums() == []
    assert list(release.iterdir()) == []
