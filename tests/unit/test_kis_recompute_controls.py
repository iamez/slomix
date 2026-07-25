"""Safety controls on the historical KIS recompute (Codex KIS-02).

The tool rewrites every scored kill in the database, so its guards matter
more than its happy path. These tests exercise the argument contract and
the reporting surface without touching a database.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path("scripts/backfill_kis_recompute.py")


def _load():
    spec = importlib.util.spec_from_file_location("_kis_recompute", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_kis_recompute"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_target_version_is_imported_never_hardcoded():
    """A hardcoded version would rescore history against a formula the live
    readers no longer use. It must follow kis.py."""
    src = SCRIPT.read_text(encoding="utf-8")
    assert "from website.backend.services.storytelling.kis import FORMULA_VERSION" in src
    for literal in ('"kis-v4"', "'kis-v4'", '"kis-v5"', "'kis-v5'"):
        assert literal not in src, f"hardcoded version {literal}"


def test_dry_run_is_the_default():
    mod = _load()
    assert mod  # module import must not perform any work
    src = SCRIPT.read_text(encoding="utf-8")
    assert '"--apply", action="store_true"' in src
    assert "DRY-RUN: no writes" in src


@pytest.mark.asyncio
async def test_apply_requires_backup_confirmation(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(sys, "argv", ["x", "--apply"])
    rc = await mod.main()
    assert rc == 1
    assert "--i-have-a-backup" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_apply_requires_an_explicit_db_target(monkeypatch, capsys):
    """Without this a stale .env silently rewrites the wrong environment."""
    mod = _load()
    monkeypatch.setattr(sys, "argv", ["x", "--apply", "--i-have-a-backup"])
    rc = await mod.main()
    assert rc == 1
    assert "--expect-db" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_mismatched_db_target_aborts_before_connecting(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DATABASE", "etlegacy")
    monkeypatch.setattr(sys, "argv", [
        "x", "--apply", "--i-have-a-backup", "--expect-db", "elsewhere:5432/other",
    ])

    async def _boom(*a, **kw):  # pragma: no cover - must never run
        raise AssertionError("connected despite a target mismatch")

    monkeypatch.setattr(mod.asyncpg, "connect", _boom)
    rc = await mod.main()
    assert rc == 1
    out = capsys.readouterr().out
    assert "ABORT" in out and "Nothing was written" in out


def test_reports_residue_and_postcondition():
    """404/ambiguous scopes must surface as accepted residue, and a session
    that ends up empty or mixed must fail the run rather than exit 0."""
    src = SCRIPT.read_text(encoding="utf-8")
    assert "accepted_residue" in src
    assert "--residue-file" in src
    assert "POSTCONDITION FAILED" in src
    # a clean exit requires no failures AND a satisfied postcondition
    assert "return 0 if (failed == 0 and not bad and not missing) else 1" in src


def test_404_is_residue_not_failure():
    """The scope resolver rejecting a session with no accepted rounds is the
    resolver working, not a recompute failure — it must not flip the exit
    code."""
    src = SCRIPT.read_text(encoding="utf-8")
    assert 'reason": "no_accepted_rounds"' in src
    assert "if e.status_code == 404:" in src
