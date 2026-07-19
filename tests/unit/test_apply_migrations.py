"""Migration runner correctness (Codex audit findings 1-2 + AUD-002 hardening).

A migration that fails once must not be treated as applied forever:
get_applied() counts only success=TRUE rows, cmd_apply retries failed rows,
and the tracking upsert overwrites the earlier failure record. A populated DB
with an empty tracking table must refuse to apply instead of auto-baselining.

AUD-002 additions: migration + ledger success commit in one transaction, a
failure rolls back and exits non-zero, checksum drift refuses to apply, and
file-level BEGIN/COMMIT wrappers are unwrapped (anything else is rejected).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.apply_migrations import (  # noqa: E402
    MigrationRejected,
    cmd_apply,
    cmd_validate,
    collect_state,
    get_applied,
    get_failed,
    requires_non_transactional,
    split_statements,
    unwrap_outer_transaction,
)


class FakeTransaction:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        self.conn.txn_depth += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.conn.txn_depth -= 1
        if exc_type:
            self.conn.rolled_back += 1
        return False


class FakeConn:
    """Minimal asyncpg.Connection stand-in with a canned row store."""

    def __init__(self, rows=None, has_pcs_table=False, fail_on_sql=None):
        # rows: list of {"filename": ..., "success": ..., "checksum": ...}
        self.rows = [dict(r, checksum=r.get("checksum")) for r in (rows or [])]
        self.has_pcs_table = has_pcs_table
        self.fail_on_sql = fail_on_sql
        self.executed: list[tuple[str, tuple]] = []
        self.txn_depth = 0
        self.rolled_back = 0
        self.advisory_lock_calls = 0
        # (query substring, txn_depth at execution) — to assert the ledger
        # success write happened inside the migration's transaction.
        self.execution_depths: list[tuple[str, int]] = []

    def transaction(self):
        return FakeTransaction(self)

    async def fetch(self, query, *args):
        if "WHERE success = TRUE" in query:
            return [r for r in self.rows if r["success"]]
        if "WHERE success = FALSE" in query:
            return [r for r in self.rows if not r["success"]]
        return list(self.rows)

    async def fetchval(self, query, *args):
        if "pg_try_advisory_lock" in query:
            self.advisory_lock_calls += 1
            return True
        if "information_schema.tables" in query:
            return self.has_pcs_table
        return None

    async def execute(self, query, *args):
        self.executed.append((query, args))
        self.execution_depths.append((query[:60], self.txn_depth))
        if self.fail_on_sql and self.fail_on_sql in query:
            raise RuntimeError(f"boom on: {self.fail_on_sql}")

    async def close(self):
        pass


def _returning(conn):
    async def _get():
        return conn
    return _get


# ── SQL wrapper analysis ─────────────────────────────────────────────


def test_unwrap_strips_outer_begin_commit():
    sql = "-- header comment\nBEGIN;\nALTER TABLE t ADD COLUMN x int;\nCOMMIT;\n"
    body = unwrap_outer_transaction(sql)
    assert "ALTER TABLE t" in body
    assert "BEGIN" not in body
    assert "COMMIT" not in body


def test_unwrap_tolerates_plpgsql_begin_in_dollar_quotes():
    sql = (
        "BEGIN;\n"
        "DO $$\nBEGIN\n  PERFORM 1;\nEND $$;\n"
        "COMMIT;\n"
    )
    body = unwrap_outer_transaction(sql)
    assert "DO $$" in body
    assert body.strip().startswith("DO")


def test_unwrap_allows_content_after_commit():
    """014-style: a DO block after COMMIT joins the runner's transaction."""
    sql = "BEGIN;\nSELECT 1;\nCOMMIT;\nDO $$ BEGIN PERFORM 2; END $$;\n"
    body = unwrap_outer_transaction(sql)
    assert "PERFORM 2" in body


def test_unwrap_rejects_stray_commit():
    sql = "BEGIN;\nSELECT 1;\nCOMMIT;\nBEGIN;\nSELECT 2;\nCOMMIT;\n"
    with pytest.raises(MigrationRejected):
        unwrap_outer_transaction(sql)


def test_unwrap_rejects_rollback():
    sql = "BEGIN;\nSELECT 1;\nROLLBACK;\n"
    with pytest.raises(MigrationRejected):
        unwrap_outer_transaction(sql)


def test_unwrap_rejects_transaction_aliases():
    """ABORT (=ROLLBACK) and END WORK (=COMMIT) are transaction-control aliases
    that must be rejected too (Codex #509)."""
    for sql in ("BEGIN;\nSELECT 1;\nABORT;\n", "BEGIN;\nSELECT 1;\nEND WORK;\n"):
        with pytest.raises(MigrationRejected):
            unwrap_outer_transaction(sql)


def test_unwrap_rejects_and_chain():
    """COMMIT/ROLLBACK AND CHAIN opens a new transaction → reject (Codex #509)."""
    with pytest.raises(MigrationRejected):
        unwrap_outer_transaction("BEGIN;\nSELECT 1;\nCOMMIT AND CHAIN;\n")


def test_unwrap_allows_case_end():
    """A bare END closing a CASE expression must NOT be mistaken for a
    transaction-ending alias (5 repo migrations use CASE)."""
    sql = "BEGIN;\nSELECT CASE WHEN x > 0 THEN 1 ELSE 0 END FROM t;\nCOMMIT;\n"
    body = unwrap_outer_transaction(sql)
    assert "CASE WHEN" in body
    assert "BEGIN" not in body and "COMMIT" not in body


def test_unwrap_ignores_tokens_in_comments_and_strings():
    sql = (
        "-- BEGIN; not a wrapper\n"
        "INSERT INTO t (msg) VALUES ('COMMIT; ROLLBACK;');\n"
        "/* COMMIT */\n"
    )
    assert unwrap_outer_transaction(sql) == sql


def test_every_repo_migration_is_accepted():
    """No committed migration may be rejected by the runner's analysis —
    neither the wrapper unwrap nor the IMP-008 CONCURRENTLY rejection (053's
    CONCURRENTLY mention lives inside masked dollar-quoted/comment context).
    This is the guard the apply-loop comment cites: a migration that trips
    requires_non_transactional() must go through the manual psql + --mark
    path, and adding one to the repo should fail HERE first."""
    mig_dir = Path(__file__).resolve().parents[2] / "migrations"
    assert sorted(mig_dir.glob("*.sql")), "no migrations found — wrong path?"
    for path in sorted(mig_dir.glob("*.sql")):
        body = unwrap_outer_transaction(path.read_text(encoding="utf-8"))
        assert not requires_non_transactional(body), (
            f"{path.name} contains live CONCURRENTLY — the runner would "
            "REJECT it (IMP-008); apply manually via psql + --mark instead"
        )


def test_concurrently_detection_ignores_comments():
    assert requires_non_transactional("CREATE INDEX CONCURRENTLY idx ON t(x);")
    assert not requires_non_transactional("-- REFRESH ... CONCURRENTLY\nSELECT 1;")


@pytest.mark.asyncio
async def test_concurrently_migration_is_rejected(monkeypatch, tmp_path, capsys):
    """IMP-008: the statement-by-statement CONCURRENTLY path is non-atomic and
    is disabled — such a migration is REJECTED (exit 1) with the manual-psql +
    --mark instruction, never applied piecemeal."""
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_conc.sql").write_text(
        "CREATE INDEX CONCURRENTLY idx_x ON t(x);"
    )
    conn = FakeConn(rows=[])
    monkeypatch.setattr("scripts.apply_migrations.MIGRATIONS_DIR", mig_dir)
    monkeypatch.setattr("scripts.apply_migrations.get_connection",
                        _returning(conn))
    with pytest.raises(SystemExit) as exc:
        await cmd_apply()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "REJECTED" in out and "--mark" in out
    # Nothing was executed or recorded for the rejected migration.
    assert not any("CREATE INDEX" in q for q, _ in conn.executed)
    assert not any("INSERT INTO schema_migrations" in q for q, _ in conn.executed)


def test_split_statements_respects_strings():
    stmts = split_statements("SELECT 'a;b'; SELECT 2;")
    assert stmts == ["SELECT 'a;b'", "SELECT 2"]


# ── Ledger semantics ─────────────────────────────────────────────────


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
async def test_collect_state_excludes_failed_from_pending(monkeypatch, tmp_path):
    """A FAILED file appears only under `failed`, never double-counted in
    `pending` (Copilot review on #509)."""
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_a.sql").write_text("SELECT 1;")
    (mig_dir / "002_b.sql").write_text("SELECT 2;")
    monkeypatch.setattr("scripts.apply_migrations.MIGRATIONS_DIR", mig_dir)

    conn = FakeConn(rows=[{"filename": "001_a.sql", "success": False}])
    state = await collect_state(conn)
    assert state["failed"] == ["001_a.sql"]
    assert state["pending"] == ["002_b.sql"]  # 001_a not double-listed
    assert state["missing"] == []


@pytest.mark.asyncio
async def test_collect_state_flags_missing_applied_file(monkeypatch, tmp_path):
    """A row recorded applied whose SQL file is gone shows up as `missing`
    (deleted/renamed migration — Copilot/Codex review on #509)."""
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_a.sql").write_text("SELECT 1;")
    monkeypatch.setattr("scripts.apply_migrations.MIGRATIONS_DIR", mig_dir)

    conn = FakeConn(rows=[
        {"filename": "001_a.sql", "success": True},
        {"filename": "099_deleted.sql", "success": True},
        # A FAILED row whose file was also deleted must ALSO count as missing
        # (orphaned failed drift — Codex review on #509).
        {"filename": "098_failed_gone.sql", "success": False},
    ])
    state = await collect_state(conn)
    assert state["missing"] == ["098_failed_gone.sql", "099_deleted.sql"]
    assert "099_deleted.sql" not in state["pending"]


@pytest.mark.asyncio
async def test_validate_clean_takes_lock_and_exits_zero(monkeypatch, tmp_path):
    """A fully-applied ledger validates clean AND takes the runner advisory
    lock so it can't read a half-written ledger mid-apply (Copilot #509)."""
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_a.sql").write_text("SELECT 1;")
    monkeypatch.setattr("scripts.apply_migrations.MIGRATIONS_DIR", mig_dir)

    conn = FakeConn(rows=[{"filename": "001_a.sql", "success": True}])
    monkeypatch.setattr("scripts.apply_migrations.get_connection",
                        _returning(conn))
    await cmd_validate()  # no SystemExit → clean
    assert conn.advisory_lock_calls == 1, "validate must acquire the runner lock"


@pytest.mark.asyncio
async def test_validate_pending_exits_nonzero(monkeypatch, tmp_path, capsys):
    """A pending file (drift) makes --validate exit 1 for deploy gating."""
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_a.sql").write_text("SELECT 1;")
    (mig_dir / "002_b.sql").write_text("SELECT 2;")  # pending
    monkeypatch.setattr("scripts.apply_migrations.MIGRATIONS_DIR", mig_dir)

    conn = FakeConn(rows=[{"filename": "001_a.sql", "success": True}])
    monkeypatch.setattr("scripts.apply_migrations.get_connection",
                        _returning(conn))
    with pytest.raises(SystemExit) as exc:
        await cmd_validate()
    assert exc.value.code == 1
    assert "DRIFT DETECTED" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_validate_tolerate_missing_only_forgives_missing(monkeypatch, tmp_path):
    """--tolerate-missing exists for the older-tag ROLLBACK path (#516): a
    ledger row whose file is absent from the checkout passes, but pending
    drift still fails even with the flag."""
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_a.sql").write_text("SELECT 1;")
    monkeypatch.setattr("scripts.apply_migrations.MIGRATIONS_DIR", mig_dir)

    # 002 recorded applied but not on disk (rollback checkout) → tolerated.
    conn = FakeConn(rows=[{"filename": "001_a.sql", "success": True},
                          {"filename": "002_newer.sql", "success": True}])
    monkeypatch.setattr("scripts.apply_migrations.get_connection",
                        _returning(conn))
    await cmd_validate(tolerate_missing=True)  # no SystemExit
    with pytest.raises(SystemExit):
        await cmd_validate()  # without the flag it is still drift

    # Pending drift is NEVER tolerated, flag or not.
    (mig_dir / "003_pending.sql").write_text("SELECT 3;")
    conn2 = FakeConn(rows=[{"filename": "001_a.sql", "success": True},
                           {"filename": "002_newer.sql", "success": True}])
    monkeypatch.setattr("scripts.apply_migrations.get_connection",
                        _returning(conn2))
    with pytest.raises(SystemExit):
        await cmd_validate(tolerate_missing=True)


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


@pytest.mark.asyncio
async def test_apply_records_success_inside_migration_transaction(monkeypatch, tmp_path):
    """Migration SQL and the ledger success row must share one transaction."""
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_atomic.sql").write_text("BEGIN;\nSELECT 1;\nCOMMIT;")
    (mig_dir / "000_seed.sql").write_text("SELECT 1;")  # applied seed needs a file

    conn = FakeConn(rows=[{"filename": "000_seed.sql", "success": True}])
    monkeypatch.setattr("scripts.apply_migrations.MIGRATIONS_DIR", mig_dir)
    monkeypatch.setattr("scripts.apply_migrations.get_connection",
                        _returning(conn))
    await cmd_apply()

    depths = {q: d for q, d in conn.execution_depths
              if "SELECT 1" in q or "INSERT INTO schema_migrations" in q}
    assert all(d == 1 for d in depths.values()), (
        f"expected migration SQL + ledger insert at txn depth 1, got {depths}"
    )


@pytest.mark.asyncio
async def test_apply_failure_rolls_back_and_exits_nonzero(monkeypatch, tmp_path, capsys):
    """On migration error: rollback, failure row in a NEW transaction, exit 1
    (the old runner returned normally → deploy scripts saw success)."""
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_boom.sql").write_text("SELECT kaboom;")
    (mig_dir / "000_seed.sql").write_text("SELECT 1;")  # applied seed needs a file

    conn = FakeConn(rows=[{"filename": "000_seed.sql", "success": True}],
                    fail_on_sql="kaboom")
    monkeypatch.setattr("scripts.apply_migrations.MIGRATIONS_DIR", mig_dir)
    monkeypatch.setattr("scripts.apply_migrations.get_connection",
                        _returning(conn))
    with pytest.raises(SystemExit) as exc:
        await cmd_apply()
    assert exc.value.code == 1
    assert conn.rolled_back == 1, "migration transaction must roll back"

    failure_writes = [(q, d) for q, d in conn.execution_depths
                      if "INSERT INTO schema_migrations" in q]
    assert failure_writes, "failure row was not recorded"
    assert failure_writes[-1][1] == 0, (
        "failure row must be written OUTSIDE the rolled-back transaction"
    )


@pytest.mark.asyncio
async def test_apply_refuses_on_checksum_drift(monkeypatch, tmp_path, capsys):
    """An applied file changed on disk → refuse to apply anything, exit 1."""
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_done.sql").write_text("SELECT 'edited after apply';")
    (mig_dir / "002_new.sql").write_text("SELECT 2;")

    conn = FakeConn(rows=[{"filename": "001_done.sql", "success": True,
                           "checksum": "recorded-checksum-does-not-match"}])
    monkeypatch.setattr("scripts.apply_migrations.MIGRATIONS_DIR", mig_dir)
    monkeypatch.setattr("scripts.apply_migrations.get_connection",
                        _returning(conn))
    with pytest.raises(SystemExit) as exc:
        await cmd_apply()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "checksum mismatch" in out
    assert not any("INSERT INTO schema_migrations" in q for q, _ in conn.executed)


@pytest.mark.asyncio
async def test_apply_only_filters_and_validates_names(monkeypatch, tmp_path, capsys):
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_a.sql").write_text("SELECT 1;")
    (mig_dir / "002_b.sql").write_text("SELECT 2;")

    # 001_a already applied → 002_b is the only pending file, so a targeted
    # --only apply has no unrelated drift to refuse. (Both applied rows must
    # correspond to on-disk files, or the new missing-file guard trips.)
    conn = FakeConn(rows=[
        {"filename": "001_a.sql", "success": True},
    ])
    monkeypatch.setattr("scripts.apply_migrations.MIGRATIONS_DIR", mig_dir)
    monkeypatch.setattr("scripts.apply_migrations.get_connection",
                        _returning(conn))
    await cmd_apply(only=["002_b.sql"])
    applied_sql = [q for q, _ in conn.executed if "SELECT" in q and "schema_migrations" not in q]
    assert any("SELECT 2" in q for q in applied_sql)
    assert not any("SELECT 1;" in q for q in applied_sql)

    # Unknown --only name → exit 1 before touching anything. (Applied row 001_a
    # has an on-disk file so the missing-file guard doesn't trip first.)
    conn2 = FakeConn(rows=[{"filename": "001_a.sql", "success": True}])
    monkeypatch.setattr("scripts.apply_migrations.get_connection",
                        _returning(conn2))
    with pytest.raises(SystemExit) as exc:
        await cmd_apply(only=["999_nope.sql"])
    assert exc.value.code == 1


@pytest.mark.asyncio
async def test_full_apply_refuses_missing_ledger_file(monkeypatch, tmp_path, capsys):
    """A full (non---only) apply refuses when a ledger row references a file that
    is gone from the checkout, matching the --only preflight (Codex #509)."""
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_a.sql").write_text("SELECT 1;")
    conn = FakeConn(rows=[
        {"filename": "001_a.sql", "success": True},
        {"filename": "099_deleted.sql", "success": True},  # applied, file gone
    ])
    monkeypatch.setattr("scripts.apply_migrations.MIGRATIONS_DIR", mig_dir)
    monkeypatch.setattr("scripts.apply_migrations.get_connection",
                        _returning(conn))
    with pytest.raises(SystemExit) as exc:
        await cmd_apply()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "missing from" in out and "099_deleted.sql" in out
    assert not any("INSERT INTO schema_migrations" in q for q, _ in conn.executed)


@pytest.mark.asyncio
async def test_apply_only_refuses_unrelated_pending_drift(monkeypatch, tmp_path, capsys):
    """--only must abort when a migration OUTSIDE the requested set is still
    pending/failed — the deploy-time guard against advancing the DB for a
    release's new files while (e.g.) 052-060 stay unreconciled (Codex #509)."""
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_a.sql").write_text("SELECT 1;")   # left pending (unrelated)
    (mig_dir / "002_b.sql").write_text("SELECT 2;")
    (mig_dir / "000_seed.sql").write_text("SELECT 1;")  # applied seed needs a file

    conn = FakeConn(rows=[{"filename": "000_seed.sql", "success": True}])
    monkeypatch.setattr("scripts.apply_migrations.MIGRATIONS_DIR", mig_dir)
    monkeypatch.setattr("scripts.apply_migrations.get_connection",
                        _returning(conn))
    with pytest.raises(SystemExit) as exc:
        await cmd_apply(only=["002_b.sql"])
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "unrelated ledger drift" in out
    assert "001_a.sql" in out
    # Nothing was applied — no ledger write happened.
    assert not any("INSERT INTO schema_migrations" in q for q, _ in conn.executed)
