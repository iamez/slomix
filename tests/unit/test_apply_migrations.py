"""Migration runner correctness (Codex audit findings 1-2).

A migration that fails once must not be treated as applied forever:
get_applied() counts only success=TRUE rows, cmd_apply retries failed rows,
and the tracking upsert overwrites the earlier failure record. A populated DB
with an empty tracking table must refuse to apply instead of auto-baselining.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.apply_migrations import cmd_apply, get_applied, get_failed  # noqa: E402


class FakeConn:
    """Minimal asyncpg.Connection stand-in with a canned row store."""

    def __init__(self, rows=None, has_pcs_table=False):
        self.rows = rows or []  # list of {"filename": ..., "success": ...}
        self.has_pcs_table = has_pcs_table
        self.executed: list[tuple[str, tuple]] = []

    async def fetch(self, query, *args):
        if "WHERE success = TRUE" in query:
            return [r for r in self.rows if r["success"]]
        if "WHERE success = FALSE" in query:
            return [r for r in self.rows if not r["success"]]
        return list(self.rows)

    async def fetchval(self, query, *args):
        if "information_schema.tables" in query:
            return self.has_pcs_table
        return None

    async def execute(self, query, *args):
        self.executed.append((query, args))

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_get_applied_excludes_failed_rows():
    conn = FakeConn(rows=[
        {"filename": "001_ok.sql", "success": True},
        {"filename": "002_broken.sql", "success": False},
    ])
    applied = await get_applied(conn)
    assert applied == {"001_ok.sql"}
    assert await get_failed(conn) == {"002_broken.sql"}


@pytest.mark.asyncio
async def test_apply_refuses_auto_baseline_on_populated_db(monkeypatch, capsys):
    """Empty tracking + populated DB → exit 1 with --baseline instructions,
    never a silent baseline of every migration file."""
    conn = FakeConn(rows=[], has_pcs_table=True)
    monkeypatch.setattr("scripts.apply_migrations.get_connection",
                        _returning(conn))
    with pytest.raises(SystemExit) as exc:
        await cmd_apply()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "--baseline" in out
    # nothing was written to schema_migrations
    assert not any("INSERT INTO schema_migrations" in q for q, _ in conn.executed)


@pytest.mark.asyncio
async def test_apply_retries_failed_and_upserts_success(monkeypatch, tmp_path, capsys):
    """A success=FALSE row is pending again, and the success insert must
    ON CONFLICT DO UPDATE so the retry outcome overwrites the failure record."""
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_retry_me.sql").write_text("SELECT 1;")

    conn = FakeConn(rows=[{"filename": "001_retry_me.sql", "success": False}],
                    has_pcs_table=True)
    monkeypatch.setattr("scripts.apply_migrations.MIGRATIONS_DIR", mig_dir)
    monkeypatch.setattr("scripts.apply_migrations.get_connection",
                        _returning(conn))
    await cmd_apply()

    out = capsys.readouterr().out
    assert "FAILED migration(s) will be retried" in out
    tracking = [q for q, _ in conn.executed
                if "INSERT INTO schema_migrations" in q]
    assert tracking, "retried migration was not recorded"
    assert all("DO UPDATE" in q for q in tracking), (
        "tracking upsert must overwrite the earlier success=FALSE row"
    )


def _returning(conn):
    async def _get():
        return conn
    return _get
