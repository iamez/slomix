"""Real parser column writer and isolated PostgreSQL late candidate replay."""

# ruff: noqa: SLF001 -- actual internal persistence boundary
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from proximity.parser import ProximityParserV4
from tests.integration.proximity_adapter_helpers import pg_query
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401
from tests.unit.test_relinker_fuzzy_fallback import _relinker


async def test_filename_origin_survives_late_stats_without_touching_unknown(journal_db, monkeypatch):  # noqa: F811
    import bot.cogs.proximity_mixins.relinker_mixin as module

    writer, observer = journal_db
    await writer.execute("""ALTER TABLE rounds ADD COLUMN map_name TEXT,
        ADD COLUMN round_start_unix BIGINT, ADD COLUMN round_date TEXT,
        ADD COLUMN round_time TEXT, ADD COLUMN created_at TIMESTAMP,
        ADD COLUMN round_canonical_id TEXT""")
    await writer.execute("""CREATE TABLE player_track(id SERIAL PRIMARY KEY,
        map_name TEXT,round_number INTEGER,session_date DATE,round_start_unix BIGINT,
        round_id INTEGER,round_link_source VARCHAR(32),round_link_reason VARCHAR(64),
        round_linked_at TIMESTAMP)""")
    await writer.execute("""CREATE TABLE lua_round_teams(map_name TEXT,
        round_number INTEGER,round_start_unix BIGINT,round_id INTEGER)""")

    async def fetch_all(q, p=None):
        return await writer.fetch(pg_query(q), *(p or ()))

    async def fetch_one(q, p=None):
        return await writer.fetchrow(pg_query(q), *(p or ()))

    async def execute(q, p=None):
        return await writer.execute(pg_query(q), *(p or ()))

    db = SimpleNamespace(fetch_all=fetch_all, fetch_one=fetch_one, execute=execute)
    parser = ProximityParserV4(db_adapter=db)
    now = datetime.now().astimezone()
    assert parser.parse_file(
        now.strftime("%Y-%m-%d-%H%M%S-fixture-round-1_engagements.txt"), source_bytes=b"# map=fixture\n# round=1\n"
    )
    assert parser.metadata["round_start_is_fallback"]
    clock = parser.metadata["round_start_unix"]
    await parser._resolve_round_link_context(now.date())
    columns = ["map_name", "round_number", "session_date", "round_start_unix"]
    values = ["fixture", 1, now.date(), clock]
    await parser._append_round_link_columns("player_track", columns, values)
    await writer.execute(
        "INSERT INTO player_track("
        + ",".join(columns)
        + ") VALUES ("
        + ",".join("$" + str(i + 1) for i in range(len(values)))
        + ")",
        *values,
    )
    await writer.execute(
        """INSERT INTO player_track(map_name,round_number,session_date,round_start_unix)
        VALUES ('fixture',1,$1,$2)""",
        now.date(),
        clock,
    )
    await writer.execute(
        """INSERT INTO rounds(id,round_number,map_name,round_start_unix,
        round_date,round_time,created_at) VALUES (42,1,'fixture',$1,$2,$3,CURRENT_TIMESTAMP)""",
        clock - 60,
        str(now.date()),
        datetime.fromtimestamp(clock - 60).astimezone().strftime("%H%M%S"),
    )
    monkeypatch.setattr(module, "_DETECTION_TABLES", ("player_track",))
    svc = _relinker(db)
    await svc._relink_null_round_ids()
    rows = [dict(r) for r in await observer.fetch("SELECT * FROM player_track ORDER BY id")]
    receipt = dict(
        module_path=module.__file__,
        module_sha256=hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
        version=await observer.fetchval("SHOW server_version_num"),
        rows=rows,
        count=await observer.fetchval("SELECT COUNT(*) FROM player_track"),
        lua_count=await observer.fetchval("SELECT COUNT(*) FROM lua_round_teams"),
    )
    if "NATIVE_PROOF_ROOT" in os.environ:
        Path(os.environ["NATIVE_PROOF_ROOT"], os.environ["NATIVE_LABEL"] + "-origin.json").write_text(
            json.dumps(receipt, indent=2, default=str) + "\n"
        )
    assert rows[0]["round_link_source"] == "filename_clock_v1"
    assert rows[0]["round_id"] == 42
    assert rows[1]["round_id"] is None and rows[1]["round_link_source"] is None
    assert all(r["round_start_unix"] == clock for r in rows)
    before = rows
    await svc._relink_null_round_ids()
    assert [dict(r) for r in await observer.fetch("SELECT * FROM player_track ORDER BY id")] == before
    assert receipt["count"] == len(rows) == 2 and receipt["lua_count"] == 0
