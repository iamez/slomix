from __future__ import annotations

import types

import pytest

from bot.services.round_publisher_service import RoundPublisherService


class _FakeChannel:
    def __init__(self):
        self.name = "unit-test-channel"
        self.sent_embeds = []

    async def send(self, *, embed):
        self.sent_embeds.append(embed)


class _FakeDB:
    def __init__(self, top_rows=None):
        self.fetch_one_calls = []
        self.fetch_all_calls = []
        self.top_rows = top_rows or [("Alpha", 30, 20, 8000, 40.0, 1, 0)]

    async def fetch_one(self, query, params):
        self.fetch_one_calls.append((query, params))
        normalized = " ".join(query.split()).lower()

        if "sum(kills) as total_kills" in normalized:
            return (2, 8, 100, 90, 25000, 50, 38.5)
        if "count(distinct round_number)" in normalized and "from rounds" in normalized:
            return (2, 2)
        if normalized.startswith("select gaming_session_id from rounds where id ="):
            return (88,)
        return None

    async def fetch_all(self, query, params):
        self.fetch_all_calls.append((query, params))
        return self.top_rows


class _ScopeService(RoundPublisherService):
    def __init__(self, db):
        super().__init__(
            bot=None,
            config=types.SimpleNamespace(production_channel_id=0),
            db_adapter=db,
        )
        self.map_summary_calls = []

    async def _post_map_summary(self, round_id: int, map_name: str, channel):
        self.map_summary_calls.append((round_id, map_name, channel))


@pytest.mark.asyncio
async def test_check_map_completion_uses_rounds_session_scope():
    db = _FakeDB()
    service = _ScopeService(db)
    channel = _FakeChannel()

    await service._check_and_post_map_completion(9819, "supply", 2, channel)

    assert len(db.fetch_one_calls) >= 1
    query, params = db.fetch_one_calls[0]
    assert "FROM rounds" in query
    assert "gaming_session_id" in query
    assert params == (9819, "supply")
    assert len(service.map_summary_calls) == 1


@pytest.mark.asyncio
async def test_post_map_summary_aggregates_map_pair_not_single_round():
    db = _FakeDB()
    service = RoundPublisherService(
        bot=None,
        config=types.SimpleNamespace(production_channel_id=0),
        db_adapter=db,
    )
    channel = _FakeChannel()

    await service._post_map_summary(9819, "supply", channel)

    # First fetch_one resolves the session id.
    assert "SELECT gaming_session_id FROM rounds" in db.fetch_one_calls[0][0]
    assert db.fetch_one_calls[0][1] == (9819,)

    # Second fetch_one must aggregate over map pair scope using rounds subquery.
    map_query, map_params = db.fetch_one_calls[1]
    assert "WHERE round_id IN (" in map_query
    assert "gaming_session_id = ?" in map_query
    assert "round_number IN (1, 2)" in map_query
    assert map_params == (88, "supply")

    # Top players query must use the same map-pair scope.
    top_query, top_params = db.fetch_all_calls[0]
    assert "WHERE round_id IN (" in top_query
    assert "gaming_session_id = ?" in top_query
    assert "round_number IN (1, 2)" in top_query
    assert "SUM(CASE WHEN team = 1 THEN 1 ELSE 0 END) as axis_rows" in top_query
    assert "SUM(CASE WHEN team = 2 THEN 1 ELSE 0 END) as allies_rows" in top_query
    assert top_params == (88, "supply")

    assert len(channel.sent_embeds) == 1
    embed = channel.sent_embeds[0]
    top_field = next(f for f in embed.fields if f.name == "🏆 Top Performers (All Rounds)")
    assert "[AXIS] **Alpha**" in top_field.value
    side_note_field = next(f for f in embed.fields if f.name == "🧭 Side Markers")
    assert "[AXIS]=Axis" in side_note_field.value
    assert "[MIXED]/[UNK]=ambiguous side data" in side_note_field.value


@pytest.mark.asyncio
async def test_post_map_summary_annotates_mixed_side_players():
    db = _FakeDB(top_rows=[("Switcher", 22, 12, 6200, 33.3, 1, 1)])
    service = RoundPublisherService(
        bot=None,
        config=types.SimpleNamespace(production_channel_id=0),
        db_adapter=db,
    )
    channel = _FakeChannel()

    await service._post_map_summary(9819, "supply", channel)

    assert len(channel.sent_embeds) == 1
    embed = channel.sent_embeds[0]
    top_field = next(f for f in embed.fields if f.name == "🏆 Top Performers (All Rounds)")
    assert "[MIXED] **Switcher**" in top_field.value
    side_note_field = next(f for f in embed.fields if f.name == "🧭 Side Markers")
    assert "1 ambiguous player(s)" in side_note_field.value
