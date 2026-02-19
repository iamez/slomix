import types

import pytest

import postgresql_database_manager as pgm_module
from postgresql_database_manager import PostgreSQLDatabaseManager


class FakeConn:
    def __init__(self, earlier_rounds=None, counterpart_rows=None):
        self.earlier_rounds = earlier_rounds or []
        self.counterpart_rows = counterpart_rows or []
        self.fetch_calls = []
        self.execute_calls = []

    async def fetch(self, query, *args):
        self.fetch_calls.append((query, args))
        if "AND round_status = 'completed'" in query:
            return self.earlier_rounds
        if "AND (round_status IN ('completed', 'substitution') OR round_status IS NULL)" in query:
            return self.counterpart_rows
        raise AssertionError(f"Unexpected fetch query: {query}")

    async def execute(self, query, *args):
        self.execute_calls.append((query, args))
        return "UPDATE 1"


@pytest.fixture
def db_manager(monkeypatch):
    monkeypatch.setattr(
        pgm_module,
        "load_config",
        lambda: types.SimpleNamespace(database_type="postgresql"),
    )
    return PostgreSQLDatabaseManager()


@pytest.mark.asyncio
async def test_counterpart_detection_requires_correct_round_order(db_manager):
    conn = FakeConn(
        counterpart_rows=[
            {"id": 2, "round_date": "2026-02-18", "round_time": "223128"},
        ]
    )
    assert await db_manager._has_valid_counterpart_round(
        conn,
        gaming_session_id=90,
        map_name="te_escape2",
        round_number=1,
        reference_round_id=1,
        reference_date="2026-02-18",
        reference_time="222647",
        pair_window_minutes=20,
    )

    conn.counterpart_rows = [
        {"id": 3, "round_date": "2026-02-18", "round_time": "221128"},
    ]
    assert not await db_manager._has_valid_counterpart_round(
        conn,
        gaming_session_id=90,
        map_name="te_escape2",
        round_number=1,
        reference_round_id=1,
        reference_date="2026-02-18",
        reference_time="222647",
        pair_window_minutes=20,
    )


@pytest.mark.asyncio
async def test_restart_detector_preserves_slow_map_replay_with_valid_pair(db_manager):
    conn = FakeConn(
        earlier_rounds=[
            {
                "id": 9882,
                "round_date": "2026-02-18",
                "round_time": "222647",
                "match_id": "2026-02-18-222647-te_escape2-round-1",
            }
        ],
        counterpart_rows=[
            {
                "id": 9883,
                "round_date": "2026-02-18",
                "round_time": "223128",
            }
        ],
    )

    await db_manager._detect_and_mark_restarts(
        conn,
        current_round_id=9885,
        gaming_session_id=90,
        map_name="te_escape2",
        round_number=1,
        current_date="2026-02-18",
        current_time="223927",
        current_player_guids=None,
    )

    assert conn.execute_calls == []


@pytest.mark.asyncio
async def test_restart_detector_still_cancels_quick_duplicate_rounds(db_manager):
    conn = FakeConn(
        earlier_rounds=[
            {
                "id": 9882,
                "round_date": "2026-02-18",
                "round_time": "222647",
                "match_id": "2026-02-18-222647-te_escape2-round-1",
            }
        ],
        counterpart_rows=[
            {
                "id": 9883,
                "round_date": "2026-02-18",
                "round_time": "223128",
            }
        ],
    )

    await db_manager._detect_and_mark_restarts(
        conn,
        current_round_id=9890,
        gaming_session_id=90,
        map_name="te_escape2",
        round_number=1,
        current_date="2026-02-18",
        current_time="222847",
        current_player_guids=None,
    )

    assert len(conn.execute_calls) == 1
    assert conn.execute_calls[0][1] == ("cancelled", 9882)
