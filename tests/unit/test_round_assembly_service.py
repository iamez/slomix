from __future__ import annotations

from datetime import datetime

import pytest

from bot.services.round_correlation_service import RoundCorrelationService


class _MemoryAssemblerDb:
    def __init__(self, rounds: list[dict]):
        self.rounds = {int(row["id"]): dict(row) for row in rounds}
        self.round_assemblies: dict[tuple[int, str, int], dict] = {}
        self.round_assembly_events: dict[int, dict] = {}
        self.round_correlations: dict[str, dict] = {}
        self.next_assembly_id = 1
        self.next_event_id = 1

    async def fetch_all(self, query, params=None):
        q = self._normalize(query)
        params = params or ()

        if "from information_schema.columns" in q:
            return [
                (table_name, column_name)
                for table_name, columns in RoundCorrelationService.REQUIRED_SCHEMA.items()
                for column_name in sorted(columns)
            ]

        if q.startswith("select id, round_date, round_time from rounds"):
            session_id, map_name = params
            rows = [
                (
                    row["id"],
                    row.get("round_date"),
                    row.get("round_time"),
                )
                for row in self.rounds.values()
                if row.get("gaming_session_id") == session_id
                and self._map(row.get("map_name")) == self._map(map_name)
                and int(row.get("round_number") or 0) == 1
            ]
            return sorted(rows, key=lambda item: (item[1] or "", item[2] or "", item[0]))

        if q.startswith("select id, assembly_key, map_play_seq, r1_round_id, r2_round_id from round_assemblies"):
            session_id, map_name = params
            rows = [
                (
                    row["id"],
                    row["assembly_key"],
                    row["map_play_seq"],
                    row.get("r1_round_id"),
                    row.get("r2_round_id"),
                )
                for row in self.round_assemblies.values()
                if row["gaming_session_id"] == session_id
                and row["map_name"] == self._map(map_name)
            ]
            return sorted(rows, key=lambda item: item[2])

        if q.startswith("select map_play_seq from round_assemblies"):
            session_id, map_name = params
            rows = [
                (row["map_play_seq"],)
                for row in self.round_assemblies.values()
                if row["gaming_session_id"] == session_id
                and row["map_name"] == self._map(map_name)
            ]
            return sorted(rows, key=lambda item: item[0])

        if q.startswith("select id, source_type, lua_teams_id from round_assembly_events where round_id ="):
            round_id = int(params[0])
            rows = [
                (row["id"], row["source_type"], row.get("lua_teams_id"))
                for row in self.round_assembly_events.values()
                if row.get("round_id") == round_id
            ]
            return sorted(rows, key=lambda item: item[0])

        if "select status, count(*) as cnt from round_correlations" in q:
            counts: dict[str, int] = {}
            for row in self.round_correlations.values():
                counts[row["status"]] = counts.get(row["status"], 0) + 1
            return sorted(counts.items(), key=lambda item: item[0])

        if "select correlation_id, match_id, map_name, status" in q:
            rows = [
                (
                    row["correlation_id"],
                    row["match_id"],
                    row["map_name"],
                    row["status"],
                    row["completeness_pct"],
                    row["created_at"],
                )
                for row in self.round_correlations.values()
            ]
            rows.sort(key=lambda item: item[5], reverse=True)
            return rows[:10]

        if "select source_type, match_id, map_name, round_number, coalesce(event_at, created_at) as event_time from round_assembly_events" in q:
            rows = [
                (
                    row["source_type"],
                    row["match_id"],
                    row["map_name"],
                    row["round_number"],
                    row.get("event_at") or row["created_at"],
                )
                for row in self.round_assembly_events.values()
                if row["attachment_status"] == "pending"
            ]
            rows.sort(key=lambda item: (item[4],), reverse=True)
            return rows[:5]

        if "select gaming_session_id, map_name, map_play_seq, r2_round_id, updated_at from round_assemblies" in q:
            rows = [
                (
                    row["gaming_session_id"],
                    row["map_name"],
                    row["map_play_seq"],
                    row.get("r2_round_id"),
                    row.get("updated_at") or row["created_at"],
                )
                for row in self.round_assemblies.values()
                if row.get("orphan_r2") and row.get("r1_round_id") is None and row.get("r2_round_id") is not None
            ]
            rows.sort(key=lambda item: ((item[4] or datetime.min), item[3] or 0), reverse=True)
            return rows[:5]

        raise AssertionError(f"Unhandled fetch_all query: {query}")

    async def fetch_one(self, query, params=None):
        q = self._normalize(query)
        params = params or ()

        if q.startswith("select id, match_id, map_name, round_number, gaming_session_id, round_date, round_time, created_at, map_play_seq from rounds where id ="):
            row = self.rounds.get(int(params[0]))
            if not row:
                return None
            return (
                row["id"],
                row.get("match_id"),
                row.get("map_name"),
                row.get("round_number"),
                row.get("gaming_session_id"),
                row.get("round_date"),
                row.get("round_time"),
                row.get("created_at"),
                row.get("map_play_seq"),
            )

        if q.startswith("select id, lua_teams_id from round_assembly_events where attachment_status = 'pending'"):
            source_type, round_number, map_name = params
            rows = [
                row
                for row in self.round_assembly_events.values()
                if row["attachment_status"] == "pending"
                and row.get("round_id") is None
                and row["source_type"] == source_type
                and row["round_number"] == round_number
                and row["map_name"] == self._map(map_name)
            ]
            if not rows:
                return None
            rows.sort(key=lambda row: (row.get("event_at") or row["created_at"], row["id"]))
            first = rows[0]
            return (first["id"], first.get("lua_teams_id"))

        if q.startswith("select has_r1_lua_teams, has_r2_lua_teams, has_r1_gametime, has_r2_gametime, has_r1_endstats, has_r2_endstats from round_assemblies"):
            session_id, map_name, map_play_seq = params
            row = self._assembly(session_id, map_name, map_play_seq)
            if not row:
                return None
            return (
                row.get("has_r1_lua_teams", False),
                row.get("has_r2_lua_teams", False),
                row.get("has_r1_gametime", False),
                row.get("has_r2_gametime", False),
                row.get("has_r1_endstats", False),
                row.get("has_r2_endstats", False),
            )

        if q.startswith("select id, has_r1_stats, has_r2_stats, has_r1_lua_teams"):
            session_id, map_name, map_play_seq = params
            row = self._assembly(session_id, map_name, map_play_seq)
            if not row:
                return None
            return (
                row["id"],
                row.get("has_r1_stats", False),
                row.get("has_r2_stats", False),
                row.get("has_r1_lua_teams", False),
                row.get("has_r2_lua_teams", False),
                row.get("has_r1_gametime", False),
                row.get("has_r2_gametime", False),
                row.get("has_r1_endstats", False),
                row.get("has_r2_endstats", False),
            )

        if q.startswith("select a.assembly_key, coalesce(r1.match_id, r2.match_id, rs.match_id, a.assembly_key) as match_id"):
            session_id, map_name, map_play_seq = params
            row = self._assembly(session_id, map_name, map_play_seq)
            if not row:
                return None
            r1 = self.rounds.get(row.get("r1_round_id"))
            r2 = self.rounds.get(row.get("r2_round_id"))
            rs = self.rounds.get(row.get("summary_round_id"))
            return (
                row["assembly_key"],
                (r1 or r2 or rs or {}).get("match_id", row["assembly_key"]),
                row["map_name"],
                row.get("r1_round_id"),
                row.get("r2_round_id"),
                row.get("summary_round_id"),
                row.get("r1_lua_teams_id"),
                row.get("r2_lua_teams_id"),
                row.get("has_r1_stats", False),
                row.get("has_r2_stats", False),
                row.get("has_r1_lua_teams", False),
                row.get("has_r2_lua_teams", False),
                row.get("has_r1_gametime", False),
                row.get("has_r2_gametime", False),
                row.get("has_r1_endstats", False),
                row.get("has_r2_endstats", False),
                row.get("status", "pending"),
                row.get("completeness_pct", 0),
                (r1 or {}).get("created_at"),
                (r2 or {}).get("created_at"),
                row.get("completed_at"),
            )

        if q.startswith("select has_r1_stats, has_r2_stats, has_r1_lua_teams"):
            row = self.round_correlations.get(params[0])
            if not row:
                return None
            return (
                row.get("has_r1_stats", False),
                row.get("has_r2_stats", False),
                row.get("has_r1_lua_teams", False),
                row.get("has_r2_lua_teams", False),
                row.get("has_r1_gametime", False),
                row.get("has_r2_gametime", False),
                row.get("has_r1_endstats", False),
                row.get("has_r2_endstats", False),
            )

        return None

    async def fetch_val(self, query, params=None):
        q = self._normalize(query)
        params = params or ()

        if q.startswith("insert into round_assembly_events"):
            (
                event_key,
                source_type,
                match_id,
                map_name,
                round_number,
                round_id,
                lua_teams_id,
                event_unix,
                event_at,
            ) = params
            existing = next(
                (row for row in self.round_assembly_events.values() if row["event_key"] == event_key),
                None,
            )
            if existing:
                existing["match_id"] = match_id
                existing["map_name"] = self._map(map_name)
                existing["round_number"] = round_number
                if round_id is not None:
                    existing["round_id"] = round_id
                if lua_teams_id is not None:
                    existing["lua_teams_id"] = lua_teams_id
                if event_unix is not None:
                    existing["event_unix"] = event_unix
                if event_at is not None:
                    existing["event_at"] = event_at
                return existing["id"]

            event_id = self.next_event_id
            self.next_event_id += 1
            self.round_assembly_events[event_id] = {
                "id": event_id,
                "event_key": event_key,
                "source_type": source_type,
                "match_id": match_id,
                "gaming_session_id": None,
                "map_name": self._map(map_name),
                "round_number": round_number,
                "round_id": round_id,
                "lua_teams_id": lua_teams_id,
                "event_unix": event_unix,
                "event_at": event_at,
                "attachment_status": "pending",
                "assembly_id": None,
                "created_at": datetime(2026, 3, 8, 12, 0, event_id),
                "attached_at": None,
            }
            return event_id

        if q.startswith("select id from round_assemblies"):
            session_id, map_name, map_play_seq = params
            row = self._assembly(session_id, map_name, map_play_seq)
            return row["id"] if row else None

        if "select count(*) from round_assembly_events" in q:
            return sum(1 for row in self.round_assembly_events.values() if row["attachment_status"] == "pending")

        if "select count(*) from round_assemblies" in q and "orphan_r2 = true" in q:
            return sum(
                1
                for row in self.round_assemblies.values()
                if row.get("orphan_r2") and row.get("r1_round_id") is None and row.get("r2_round_id") is not None
            )

        raise AssertionError(f"Unhandled fetch_val query: {query}")

    async def execute(self, query, params=None, *extra):
        q = self._normalize(query)
        if extra:
            params = tuple(params or ()) + tuple(extra)
        params = params or ()

        if q.startswith("update rounds set map_play_seq ="):
            map_play_seq, round_id = params
            self.rounds[int(round_id)]["map_play_seq"] = int(map_play_seq)
            return

        if q.startswith("insert into round_assemblies"):
            self._upsert_assembly(q, params)
            return

        if q.startswith("update round_assembly_events set assembly_id ="):
            assembly_id, session_id, round_id, event_id = params
            row = self.round_assembly_events[int(event_id)]
            row["assembly_id"] = int(assembly_id)
            row["gaming_session_id"] = int(session_id)
            row["round_id"] = row.get("round_id") or int(round_id)
            row["attachment_status"] = "attached"
            row["attached_at"] = datetime(2026, 3, 8, 13, 0, int(event_id))
            return

        if q.startswith("update round_assemblies set has_r"):
            self._update_assembly_source_flag(q, params)
            return

        if q.startswith("update round_assemblies set status ="):
            status, pct, completed_at, assembly_id = params
            row = self._assembly_by_id(int(assembly_id))
            row["status"] = status
            row["completeness_pct"] = int(pct)
            row["completed_at"] = completed_at
            return

        if q.startswith("insert into round_correlations"):
            self._upsert_correlation(params)
            return

        if q.startswith("update round_correlations set"):
            correlation_id = params[-1]
            row = self.round_correlations.setdefault(
                correlation_id,
                {
                    "correlation_id": correlation_id,
                    "match_id": correlation_id,
                    "map_name": "unknown",
                    "created_at": datetime(2026, 3, 8, 12, 0, 0),
                },
            )
            columns = []
            set_clause = q.split("set", 1)[1].split("where", 1)[0]
            for entry in set_clause.split(","):
                columns.append(entry.strip().split(" = ", 1)[0])
            for column, value in zip(columns, params[:-1], strict=False):
                row[column] = value
            return

        if q.startswith("update round_correlations set summary_round_id ="):
            summary_round_id, match_id = params
            for row in self.round_correlations.values():
                if row.get("match_id") == match_id:
                    row["summary_round_id"] = summary_round_id
            return

        raise AssertionError(f"Unhandled execute query: {query}")

    def _upsert_assembly(self, query_text: str, params: tuple):
        is_r1 = "r1_round_id" in query_text and "r2_round_id" not in query_text
        assembly_key = params[0]
        session_id = int(params[1])
        map_name = self._map(params[2])
        map_play_seq = int(params[3])
        key = (session_id, map_name, map_play_seq)
        row = self.round_assemblies.get(key)
        if row is None:
            row = {
                "id": self.next_assembly_id,
                "assembly_key": assembly_key,
                "gaming_session_id": session_id,
                "map_name": map_name,
                "map_play_seq": map_play_seq,
                "r1_round_id": None,
                "r2_round_id": None,
                "summary_round_id": None,
                "r1_lua_teams_id": None,
                "r2_lua_teams_id": None,
                "has_r1_stats": False,
                "has_r2_stats": False,
                "has_r1_lua_teams": False,
                "has_r2_lua_teams": False,
                "has_r1_gametime": False,
                "has_r2_gametime": False,
                "has_r1_endstats": False,
                "has_r2_endstats": False,
                "orphan_r2": False,
                "status": "pending",
                "completeness_pct": 0,
                "completed_at": None,
                "created_at": params[-1],
                "updated_at": params[-1],
            }
            self.round_assemblies[key] = row
            self.next_assembly_id += 1

        row["assembly_key"] = assembly_key
        row["updated_at"] = params[-1]
        if is_r1:
            row["r1_round_id"] = int(params[4])
            row["has_r1_stats"] = True
            row["orphan_r2"] = False
        else:
            row["r2_round_id"] = int(params[4])
            row["has_r2_stats"] = True
            row["orphan_r2"] = bool(row.get("orphan_r2")) or bool(params[5])

    def _update_assembly_source_flag(self, query_text: str, params: tuple):
        if "where id = $2" in query_text:
            value, assembly_id = params
        else:
            value = None
            assembly_id = params[0]
        row = self._assembly_by_id(int(assembly_id))
        if "has_r1_lua_teams" in query_text:
            row["has_r1_lua_teams"] = True
            row["r1_lua_teams_id"] = value if value is not None else row.get("r1_lua_teams_id")
        elif "has_r2_lua_teams" in query_text:
            row["has_r2_lua_teams"] = True
            row["r2_lua_teams_id"] = value if value is not None else row.get("r2_lua_teams_id")
        elif "has_r1_gametime" in query_text:
            row["has_r1_gametime"] = True
        elif "has_r2_gametime" in query_text:
            row["has_r2_gametime"] = True
        elif "has_r1_endstats" in query_text:
            row["has_r1_endstats"] = True
        elif "has_r2_endstats" in query_text:
            row["has_r2_endstats"] = True

    def _upsert_correlation(self, params: tuple):
        correlation_id = params[0]
        self.round_correlations[correlation_id] = {
            "correlation_id": correlation_id,
            "match_id": params[1],
            "map_name": params[2],
            "r1_round_id": params[3],
            "r2_round_id": params[4],
            "summary_round_id": params[5],
            "r1_lua_teams_id": params[6],
            "r2_lua_teams_id": params[7],
            "has_r1_stats": params[8],
            "has_r2_stats": params[9],
            "has_r1_lua_teams": params[10],
            "has_r2_lua_teams": params[11],
            "has_r1_gametime": params[12],
            "has_r2_gametime": params[13],
            "has_r1_endstats": params[14],
            "has_r2_endstats": params[15],
            "status": params[16],
            "completeness_pct": params[17],
            "r1_arrived_at": params[18],
            "r2_arrived_at": params[19],
            "completed_at": params[20],
            "created_at": self.round_correlations.get(correlation_id, {}).get(
                "created_at", datetime(2026, 3, 8, 12, 0, 0)
            ),
        }

    def _assembly(self, session_id: int, map_name: str, map_play_seq: int):
        return self.round_assemblies.get((int(session_id), self._map(map_name), int(map_play_seq)))

    def _assembly_by_id(self, assembly_id: int):
        for row in self.round_assemblies.values():
            if row["id"] == assembly_id:
                return row
        raise KeyError(assembly_id)

    @staticmethod
    def _normalize(query: str) -> str:
        return " ".join(str(query).lower().split())

    @staticmethod
    def _map(value) -> str:
        return str(value or "unknown").strip().lower()


def _round(round_id: int, match_id: str, round_number: int, time_text: str) -> dict:
    return {
        "id": round_id,
        "match_id": match_id,
        "map_name": "te_escape2",
        "round_number": round_number,
        "gaming_session_id": 77,
        "round_date": "2026-03-08",
        "round_time": time_text,
        "created_at": datetime.strptime(f"2026-03-08 {time_text}", "%Y-%m-%d %H%M%S"),
        "map_play_seq": None,
    }


@pytest.mark.asyncio
async def test_repeated_same_map_rounds_assign_fifo_map_play_seq():
    db = _MemoryAssemblerDb(
        [
            _round(1, "m1", 1, "120000"),
            _round(2, "m1", 2, "121500"),
            _round(3, "m2", 1, "123000"),
            _round(4, "m2", 2, "124500"),
            _round(5, "m3", 1, "130000"),
            _round(6, "m3", 2, "131500"),
            _round(7, "m4", 1, "133000"),
            _round(8, "m4", 2, "134500"),
        ]
    )
    svc = RoundCorrelationService(db, dry_run=False)
    await svc.initialize()

    for round_id in range(1, 9):
        row = db.rounds[round_id]
        await svc.on_round_imported(
            match_id=row["match_id"],
            round_number=row["round_number"],
            round_id=round_id,
            map_name=row["map_name"],
        )

    assert db.rounds[1]["map_play_seq"] == 1
    assert db.rounds[2]["map_play_seq"] == 1
    assert db.rounds[3]["map_play_seq"] == 2
    assert db.rounds[4]["map_play_seq"] == 2
    assert db.rounds[5]["map_play_seq"] == 3
    assert db.rounds[6]["map_play_seq"] == 3
    assert db.rounds[7]["map_play_seq"] == 4
    assert db.rounds[8]["map_play_seq"] == 4

    assert db.round_assemblies[(77, "te_escape2", 1)]["r1_round_id"] == 1
    assert db.round_assemblies[(77, "te_escape2", 1)]["r2_round_id"] == 2
    assert db.round_assemblies[(77, "te_escape2", 4)]["r1_round_id"] == 7
    assert db.round_assemblies[(77, "te_escape2", 4)]["r2_round_id"] == 8
    assert set(db.round_correlations) == {
        "asm:77:te_escape2:1",
        "asm:77:te_escape2:2",
        "asm:77:te_escape2:3",
        "asm:77:te_escape2:4",
    }


@pytest.mark.asyncio
async def test_pending_non_stats_events_attach_fifo_on_anchor_arrival():
    db = _MemoryAssemblerDb(
        [
            _round(1, "m1", 1, "120000"),
            _round(3, "m2", 1, "123000"),
        ]
    )
    svc = RoundCorrelationService(db, dry_run=False)
    await svc.initialize()

    await svc.on_lua_teams_stored(
        match_id="lua-a",
        round_number=1,
        lua_teams_id=501,
        map_name="te_escape2",
    )
    await svc.on_lua_teams_stored(
        match_id="lua-b",
        round_number=1,
        lua_teams_id=502,
        map_name="te_escape2",
    )

    await svc.on_round_imported("m1", 1, 1, "te_escape2")
    await svc.on_round_imported("m2", 1, 3, "te_escape2")

    assert db.round_assemblies[(77, "te_escape2", 1)]["r1_lua_teams_id"] == 501
    assert db.round_assemblies[(77, "te_escape2", 2)]["r1_lua_teams_id"] == 502
    assert db.round_assembly_events[1]["attachment_status"] == "attached"
    assert db.round_assembly_events[2]["attachment_status"] == "attached"


@pytest.mark.asyncio
async def test_r2_without_open_r1_creates_orphan_then_late_r1_claims_same_seq():
    db = _MemoryAssemblerDb(
        [
            _round(1, "m1", 1, "120000"),
            _round(2, "m1", 2, "121500"),
        ]
    )
    svc = RoundCorrelationService(db, dry_run=False)
    await svc.initialize()

    await svc.on_round_imported("m1", 2, 2, "te_escape2")

    orphan = db.round_assemblies[(77, "te_escape2", 1)]
    assert orphan["r1_round_id"] is None
    assert orphan["r2_round_id"] == 2
    assert orphan["orphan_r2"] is True

    await svc.on_round_imported("m1", 1, 1, "te_escape2")

    repaired = db.round_assemblies[(77, "te_escape2", 1)]
    assert repaired["r1_round_id"] == 1
    assert repaired["r2_round_id"] == 2
    assert repaired["orphan_r2"] is False
    assert repaired["status"] == "complete"


@pytest.mark.asyncio
async def test_status_summary_includes_pending_and_orphan_details():
    db = _MemoryAssemblerDb(
        [
            _round(1, "m1", 2, "121500"),
        ]
    )
    svc = RoundCorrelationService(db, dry_run=False)
    await svc.initialize()

    await svc.on_lua_teams_stored(
        match_id="lua-pending",
        round_number=1,
        lua_teams_id=900,
        map_name="supply",
    )
    await svc.on_round_imported("m1", 2, 1, "te_escape2")

    summary = await svc.get_status_summary()

    assert summary["pending_events"] == 1
    assert summary["orphan_r2_open"] == 1
    assert summary["pending_event_rows"][0][1] == "lua-pending"
    assert summary["orphan_r2_rows"][0][0] == 77
    assert summary["orphan_r2_rows"][0][1] == "te_escape2"
