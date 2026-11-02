"""Retired DB paths must read the copied tree, never the retired originals."""
import json
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from greatshot.config import CONFIG
from website.backend.services.greatshot_store import GreatshotStorageService


@pytest.fixture
def relocated(tmp_path, monkeypatch):
    current, retired = tmp_path / "current", tmp_path / "retired"
    current.mkdir()
    retired.mkdir()
    monkeypatch.setattr(CONFIG, "storage_root", current)
    monkeypatch.setattr(CONFIG, "legacy_storage_root", retired)
    return GreatshotStorageService(tmp_path), current, retired


def test_mapping_uses_current_bytes_and_relative_display(relocated):
    store, current, retired = relocated
    (current / "report.txt").write_text("new copy")
    (retired / "report.txt").write_text("retired bytes")
    for root in (current, retired):
        assert store.resolve_checked_path(str(root / "report.txt")).read_text() == "new copy"
        assert store.safe_relative(root / "report.txt") == "report.txt"


def test_no_retired_fallback_when_copy_missing(relocated):
    store, _, retired = relocated
    old = retired / "report.txt"
    old.write_text("old file still exists")
    with pytest.raises(HTTPException) as error:
        store.resolve_checked_path(str(old))
    assert error.value.status_code == 404
    assert store.existing_artifact(str(old)) is None
    assert store.safe_relative(old) is None
    assert old.read_text() == "old file still exists"


@pytest.mark.parametrize("variant", ["sibling", "traversal", "relative", "symlink", "loop", "internal_link", "parent_link"])
def test_invalid_paths_fail_closed(relocated, variant):
    store, current, retired = relocated
    outside = current.parent / "outside.txt"
    outside.write_text("private")
    if variant == "sibling":
        path = Path(str(retired) + "-other") / "outside.txt"
    elif variant == "traversal":
        path = retired / ".." / "outside.txt"
    elif variant == "relative":
        path = Path("outside.txt")
    elif variant == "parent_link":
        (current / "link").symlink_to(current.parent, target_is_directory=True)
        path = retired / "link" / "outside.txt"
    else:
        link = current / "link"
        if variant == "internal_link":
            target = current / "real.txt"
            target.write_text("inside")
        else:
            target = outside if variant == "symlink" else link
        link.symlink_to(target)
        path = retired / "link"
    with pytest.raises(HTTPException) as error:
        store.existing_artifact(str(path))
    assert error.value.status_code == 403
    assert store.safe_relative(path) is None


def test_legacy_mapping_is_opt_in(relocated, monkeypatch):
    _, current, retired = relocated
    monkeypatch.setattr(CONFIG, "legacy_storage_root", None)
    store = GreatshotStorageService(current.parent)
    (current / "report.txt").write_text("current")
    assert store.resolve_checked_path(str(current / "report.txt")) == current / "report.txt"
    with pytest.raises(HTTPException) as error:
        store.resolve_checked_path(str(retired / "report.txt"))
    assert error.value.status_code == 403


@pytest.mark.parametrize("legacy", ["relative", "/", "same", "child", "parent", "traversal"])
def test_unsafe_legacy_configuration_refused(tmp_path, monkeypatch, legacy):
    current = tmp_path / "current"
    roots = {"relative": Path("retired"), "/": Path("/"), "same": current,
             "child": current / "old", "parent": tmp_path,
             "traversal": tmp_path / "old" / ".." / "other"}
    monkeypatch.setattr(CONFIG, "storage_root", current)
    monkeypatch.setattr(CONFIG, "legacy_storage_root", roots[legacy])
    with pytest.raises(ValueError, match="absolute and disjoint"):
        GreatshotStorageService(tmp_path)


def test_mapping_does_not_require_retired_root_to_exist(relocated):
    store, current, retired = relocated
    retired.rmdir()  # Empty synthetic fixture only.
    (current / "report.txt").write_text("copy")
    assert store.resolve_checked_path(str(retired / "report.txt")) == current / "report.txt"


@pytest.mark.asyncio
@pytest.mark.parametrize("handler", ["get_top_players", "get_top_accuracy", "get_top_damage"])
async def test_topshots_read_mapped_analysis(relocated, monkeypatch, handler):
    from website.backend.routers import greatshot_topshots as router
    store, current, retired = relocated
    monkeypatch.setattr(router, "storage", store)
    document = {"player_stats": {"Copied player": {
        "kills": 20, "deaths": 4, "damage_given": 1200, "accuracy": 40, "headshots": 7}}}
    (current / "analysis.json").write_text(json.dumps(document))
    (retired / "analysis.json").write_text('{"player_stats": {}}')
    db = SimpleNamespace(fetch_all=AsyncMock(return_value=[
        ("demo", "demo.dm_84", {}, str(retired / "analysis.json"), None)]))
    request = SimpleNamespace(session={"user": {"id": "999"}})
    result = await getattr(router, handler)(request, db=db)
    assert result[0]["player"] == "Copied player"


@pytest.mark.asyncio
async def test_analysis_job_passes_new_path_to_scanner(relocated, monkeypatch):
    from website.backend.services import greatshot_jobs as jobs
    store, current, retired = relocated
    (current / "demo.dm_84").write_bytes(b"copied demo")
    conn = SimpleNamespace(fetchrow=AsyncMock(return_value={
        "stored_path": str(retired / "demo.dm_84"), "extension": ".dm_84"}),
        execute=AsyncMock())

    @asynccontextmanager
    async def context():
        yield conn

    conn.transaction = context
    db = SimpleNamespace(connection=context, execute=AsyncMock())
    seen = []

    def scanner(path, *_args, **_kwargs):
        seen.append(path)
        raise RuntimeError("stop synthetic scanner after input verification")

    monkeypatch.setattr(jobs, "run_analysis_job", scanner)
    assert await jobs.GreatshotJobService(db, store)._process_analysis_job("demo") is False  # noqa: SLF001
    assert seen == [current / "demo.dm_84"]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["existing", "cut", "concurrent"])
async def test_render_job_maps_existing_source_and_concurrent_clip(relocated, monkeypatch, mode):
    from website.backend.services import greatshot_jobs as jobs
    store, current, retired = relocated
    (current / "demo.dm_84").write_bytes(b"copied demo")
    (current / "clip.dm_84").write_bytes(b"copied clip")
    old_clip = str(retired / "clip.dm_84")
    row = ("highlight", "demo", 100, 200, old_clip, str(retired / "demo.dm_84"), ".dm_84", {})
    conn = SimpleNamespace(fetchrow=AsyncMock(return_value=(old_clip,) if mode == "concurrent" else None),
                           execute=AsyncMock())

    @asynccontextmanager
    async def context():
        yield conn

    conn.transaction = context
    db = SimpleNamespace(fetch_one=AsyncMock(side_effect=[row, (old_clip,) if mode == "existing" else None]),
                         execute=AsyncMock(), connection=context)
    cut_inputs, rendered = [], []

    def cut(path, _start, _end, output, *_args):
        cut_inputs.append(path)
        output.write_bytes(b"new clip")

    def render(path, *_args):
        rendered.append(Path(path))

    monkeypatch.setattr(jobs, "cut_demo", cut)
    monkeypatch.setattr(jobs, "render_clip", render)
    assert await jobs.GreatshotJobService(db, store)._process_render_job("render") is True  # noqa: SLF001
    assert cut_inputs == ([] if mode == "existing" else [current / "demo.dm_84"])
    expected = current / "demo/clips/highlight.dm_84" if mode == "cut" else current / "clip.dm_84"
    assert rendered == [expected]
