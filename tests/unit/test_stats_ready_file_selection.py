from __future__ import annotations

import pytest

from bot.ultimate_bot import UltimateETLegacyBot


class _Cfg:
    ssh_host = "host"
    ssh_port = 22
    ssh_user = "user"
    ssh_key_path = "/tmp/key"
    ssh_remote_path = "/remote/stats"
    stats_directory = "/tmp"
    lua_round_link_max_diff_seconds = 90


class _FakeFileTracker:
    def __init__(self) -> None:
        self.claimed: list[str] = []
        self.released: list[str] = []

    async def claim_file(self, filename: str) -> bool:
        self.claimed.append(filename)
        return True

    async def release_file_claim(self, filename: str) -> None:
        self.released.append(filename)


class _FakeRoundPublisher:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []

    async def publish_round_stats(self, filename: str, result: dict) -> None:
        self.published.append((filename, result))


class _FakeBot:
    _normalize_lua_round_for_metadata_paths = (
        UltimateETLegacyBot._normalize_lua_round_for_metadata_paths
    )
    _extract_stats_filename_timestamp = (
        UltimateETLegacyBot._extract_stats_filename_timestamp
    )
    _select_stats_ready_candidate = UltimateETLegacyBot._select_stats_ready_candidate
    _fetch_latest_stats_file = UltimateETLegacyBot._fetch_latest_stats_file

    def __init__(self) -> None:
        self.config = _Cfg()
        self.file_tracker = _FakeFileTracker()
        self.round_publisher = _FakeRoundPublisher()
        self.processed: list[tuple[str, str, dict]] = []

    async def process_gamestats_file(
        self,
        local_path: str,
        filename: str,
        override_metadata: dict | None = None,
    ) -> dict:
        self.processed.append((local_path, filename, override_metadata or {}))
        return {"success": True, "player_count": 6}


def test_select_stats_ready_candidate_requires_exact_map_name():
    bot = _FakeBot()
    metadata = {
        "map_name": "te_escape2",
        "round_number": 1,
        "round_end_unix": 1772746975,
    }
    files = [
        "2026-03-05-224257-te_escape20-round-1.txt",
        "2026-03-05-224257-te_escape2-round-1.txt",
    ]

    filename, diff_s, candidate_count = bot._select_stats_ready_candidate(files, metadata)

    assert filename == "2026-03-05-224257-te_escape2-round-1.txt"
    assert diff_s == 2
    assert candidate_count == 1


@pytest.mark.asyncio
async def test_fetch_latest_stats_file_waits_for_close_candidate(monkeypatch):
    bot = _FakeBot()
    metadata = {
        "map_name": "te_escape2",
        "round_number": 1,
        "round_end_unix": 1772746382,
    }
    remote_file_sets = [
        ["2026-03-05-222146-te_escape2-round-1.txt"],
        [
            "2026-03-05-222146-te_escape2-round-1.txt",
            "2026-03-05-223305-te_escape2-round-1.txt",
        ],
    ]
    downloaded: list[str] = []

    async def _fake_list_remote_files(_ssh_config):
        if len(remote_file_sets) > 1:
            return remote_file_sets.pop(0)
        return remote_file_sets[0]

    async def _fake_download_file(_ssh_config, filename, _stats_dir):
        downloaded.append(filename)
        return f"/tmp/{filename}"

    async def _fake_sleep(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "bot.automation.ssh_handler.SSHHandler.list_remote_files",
        _fake_list_remote_files,
    )
    monkeypatch.setattr(
        "bot.automation.ssh_handler.SSHHandler.download_file",
        _fake_download_file,
    )
    monkeypatch.setattr("bot.ultimate_bot.asyncio.sleep", _fake_sleep)

    await bot._fetch_latest_stats_file(metadata, None)

    assert downloaded == ["2026-03-05-223305-te_escape2-round-1.txt"]
    assert bot.file_tracker.claimed == ["2026-03-05-223305-te_escape2-round-1.txt"]
    assert bot.processed[0][1] == "2026-03-05-223305-te_escape2-round-1.txt"


@pytest.mark.asyncio
async def test_fetch_latest_stats_file_skips_far_same_day_candidate(monkeypatch):
    bot = _FakeBot()
    metadata = {
        "map_name": "te_escape2",
        "round_number": 1,
        "round_end_unix": 1772746382,
    }
    downloaded: list[str] = []

    async def _fake_list_remote_files(_ssh_config):
        return ["2026-03-05-222146-te_escape2-round-1.txt"]

    async def _fake_download_file(_ssh_config, filename, _stats_dir):
        downloaded.append(filename)
        return f"/tmp/{filename}"

    async def _fake_sleep(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "bot.automation.ssh_handler.SSHHandler.list_remote_files",
        _fake_list_remote_files,
    )
    monkeypatch.setattr(
        "bot.automation.ssh_handler.SSHHandler.download_file",
        _fake_download_file,
    )
    monkeypatch.setattr("bot.ultimate_bot.asyncio.sleep", _fake_sleep)

    await bot._fetch_latest_stats_file(metadata, None)

    assert downloaded == []
    assert bot.file_tracker.claimed == []
    assert bot.processed == []
