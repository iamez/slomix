"""Live view S1: ingest + feed contract for website/backend/routers/live.py.

Runs the router on a bare FastAPI app (no site middleware, no DB) — the
contract under test is the ring buffer, the cursor semantics and the
internal-secret gate, all process-local.
"""

from __future__ import annotations

import importlib
import os
from copy import deepcopy
from io import BytesIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

live = importlib.import_module("website.backend.routers.live")


@pytest.fixture()
def client(monkeypatch):
    # Fresh buffer per test — the module is process-global by design.
    monkeypatch.setattr(live, "_events", type(live._events)(maxlen=live._BUFFER_MAX))  # noqa: SLF001
    monkeypatch.setattr(live, "_UPSTREAM", "")
    monkeypatch.setattr(live, "_state", live.LiveStateReducer())
    monkeypatch.setattr(live, "_recent_livex_kills", {})
    monkeypatch.setattr(live, "_evicted_by_type", {})
    monkeypatch.setattr(live, "_seq", 0)  # noqa: SLF001
    monkeypatch.setenv("INTERNAL_API_SECRET", "test-secret")
    app = FastAPI()
    app.include_router(live.router, prefix="/api/live")
    return TestClient(app)


_FROM_ENV = object()


def _post(client, events, token=_FROM_ENV):
    # The secret is whatever the `client` fixture put in the environment —
    # read back here, never spelled in the file (pre-push scans for that).
    if token is _FROM_ENV:
        token = os.environ["INTERNAL_API_SECRET"]
    headers = {"X-Internal-Token": token} if token else {}
    return client.post("/api/live/events", json={"events": events}, headers=headers)


def test_ingest_requires_internal_secret(client):
    assert _post(client, [{"type": "KILL"}], token=None).status_code in (401, 403)
    assert _post(client, [{"type": "KILL"}], token="wrong").status_code in (401, 403)


def test_feed_cursor_semantics(client):
    r = _post(client, [
        {"type": "ROUND_START", "level_ms": 1000},
        {"type": "KILL", "level_ms": 2000, "fields": {"killer": "a", "victim": "b", "mod": "MOD_MP40"}},
    ])
    assert r.status_code == 200 and r.json()["accepted"] == 2

    page1 = client.get("/api/live/feed?since=0").json()
    assert [e["type"] for e in page1["events"]] == ["ROUND_START", "KILL"]
    assert page1["events"][1]["killer"] == "a"

    cursor = page1["last_seq"]
    assert client.get(f"/api/live/feed?since={cursor}").json()["events"] == []

    _post(client, [{"type": "ROUND_END"}])
    page2 = client.get(f"/api/live/feed?since={cursor}").json()
    assert [e["type"] for e in page2["events"]] == ["ROUND_END"]


def test_unknown_types_are_dropped_not_stored(client):
    r = _post(client, [
        {"type": "TEAM_CHAT_REDACTED"},
        {"type": "TOTALLY_MADE_UP"},
        {"type": "POPUP", "fields": {"team": "allies", "verb": "stole", "objective": "Gold"}},
    ])
    assert r.json()["accepted"] == 1
    events = client.get("/api/live/feed").json()["events"]
    assert [e["type"] for e in events] == ["POPUP"]


def test_batch_size_cap(client):
    r = _post(client, [{"type": "KILL"}] * (live._POST_MAX_EVENTS + 1))  # noqa: SLF001
    assert r.status_code == 413


@pytest.mark.parametrize("invalid", [
    {"type": "MAP", "fields": {"map_name": ["supply"]}},
    {"type": "LIVE_AGGREGATE", "fields": {
        "slot": 3, "kills": 7, "damage_given": "invalid"}},
    {"type": "KILL", "fields": {"killer_slot": [], "victim_slot": 5}},
    {"type": "LIVE_MOVEMENT", "fields": {"players": 17}},
])
def test_invalid_batch_publishes_nothing_and_next_batch_recovers(client, monkeypatch, invalid):
    """A rejected batch cannot consume cursors, evict rows or apply deltas."""
    monkeypatch.setattr(live.time, "time", lambda: 1000.0)
    monkeypatch.setattr(live, "_events", type(live._events)(maxlen=2))  # noqa: SLF001
    assert _post(client, [
        {"type": "MAP", "fields": {"map_name": "supply"}},
        {"type": "CONNECT", "fields": {"slot": 3, "name": "fixture"}},
    ]).status_code == 200
    before = deepcopy((list(live._events), live._seq, live._state.__dict__,  # noqa: SLF001
                       live._recent_livex_kills, live._evicted_by_type))  # noqa: SLF001
    response = _post(client, [
        {"type": "LIVE_KILL", "fields": {"killer_slot": 3, "victim_slot": 5}},
        {"type": "LIVE_AGGREGATE", "fields": {"slot": 3, "kills": 2}},
        invalid,
    ])
    assert response.status_code == 422
    assert (list(live._events), live._seq, live._state.__dict__,  # noqa: SLF001
            live._recent_livex_kills, live._evicted_by_type) == before  # noqa: SLF001
    assert client.get("/api/live/state").status_code == 200
    recovery = _post(client, [{"type": "KILL", "fields": {
        "killer_slot": 3, "victim_slot": 5}}])
    assert recovery.json()["accepted"] == 1  # no poisoned duplicate latch
    assert recovery.json()["last_seq"] == 3
    assert client.get("/api/live/feed").json()["events"][-1]["seq"] == 3


def test_nonfinite_payload_cannot_poison_feed(client):
    response = client.post("/api/live/events", content=(
        '{"events":[{"type":"SAY","fields":{"text":NaN}}]}'
    ), headers={"Content-Type": "application/json",
                "X-Internal-Token": os.environ["INTERNAL_API_SECRET"]})
    assert response.status_code == 422
    assert client.get("/api/live/feed").json()["last_seq"] == 0


def test_kill_duplicate_cache_has_a_hard_bound(client, monkeypatch):
    monkeypatch.setattr(live.time, "time", lambda: 1000.0)
    for start in range(0, 1200, 200):
        assert _post(client, [
            {"type": "LIVE_KILL", "fields": {"killer_slot": n, "victim_slot": 1}}
            for n in range(start, start + 200)
        ]).status_code == 200
    assert len(live._recent_livex_kills) <= live._BUFFER_MAX  # noqa: SLF001
    assert _post(client, [{"type": "KILL", "fields": {
        "killer_slot": 1199, "victim_slot": 1}}]).json()["accepted"] == 0


@pytest.mark.parametrize("payload", [b'[]', b'17', b'{}' + b' ' * 80,
                                    b'{"n":NaN}', b'{"n":Infinity}', b'{"n":1e400}'])
def test_upstream_nonobject_or_oversized_body_is_unavailable(client, monkeypatch, payload):
    monkeypatch.setattr(live, "_UPSTREAM", "https://fixture.invalid/api/live")
    monkeypatch.setattr(live, "_PROXY_MAX_BYTES", 64, raising=False)
    monkeypatch.setattr(live.urllib.request, "urlopen", lambda *a, **kw: BytesIO(payload))
    assert client.get("/api/live/feed").status_code == 503


def test_upstream_valid_object_at_size_limit_remains_available(client, monkeypatch):
    monkeypatch.setattr(live, "_UPSTREAM", "https://fixture.invalid/api/live")
    monkeypatch.setattr(live, "_PROXY_MAX_BYTES", 64)
    reads = []

    class Response(BytesIO):
        def read(self, size=-1):
            reads.append(size)
            return super().read(size)

    payload = b'{"status":"ok","events":[]}'.ljust(64, b' ')
    monkeypatch.setattr(live.urllib.request, "urlopen", lambda *a, **kw: Response(payload))
    response = client.get("/api/live/feed")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "events": []}
    assert reads == [65]


def test_status_reports_freshness(client):
    s0 = client.get("/api/live/status").json()
    assert s0["buffered"] == 0 and s0["newest_age_seconds"] is None
    _post(client, [{"type": "MAP", "fields": {"map_name": "supply"}}])
    s1 = client.get("/api/live/status").json()
    assert s1["buffered"] == 1
    assert s1["newest_age_seconds"] is not None and s1["newest_age_seconds"] < 5



def test_livex_types_ingest_and_feed_through(client):
    """LIVEX events (from live_events.lua via slomix-live.log) must survive
    ingest and appear in the feed — the two-tailer path end to end."""
    r = _post(client, [
        {"type": "LIVE_KILL", "level_ms": 1786480915000, "fields": {
            "killer_slot": 3, "victim_slot": 5, "mod_id": 34,
            "killer_pos": {"x": 1024, "y": -512, "z": 64}, "distance": 137}},
        {"type": "LIVE_AGGREGATE", "level_ms": 1786480920000, "fields": {
            "slot": 3, "damage_given": 640, "damage_received": 120,
            "kills": 2, "deaths": 0}},
        {"type": "LIVE_MOVEMENT", "level_ms": 1786480920000, "fields": {
            "players": [{"slot": 3, "x": 1024, "y": -512}]}},
        {"type": "LIVE_MAP", "level_ms": 1786480914000, "fields": {"map_name": "supply"}},
        # a legacy KILL alongside, as the two-tailer setup produces
        {"type": "KILL", "level_ms": 1, "fields": {"killer": "vid", "victim": "lgz", "mod": "MOD_MP40"}},
    ])
    assert r.status_code == 200 and r.json()["accepted"] == 5
    # Default feed hides the high-volume LIVEX telemetry (2026-08-18): it
    # drowned the page/buffer while rendering as nothing.
    types = [e["type"] for e in client.get("/api/live/feed").json()["events"]]
    assert types == ["LIVE_KILL", "LIVE_MAP", "KILL"]
    hidden = [e["type"] for e in client.get(
        "/api/live/feed?types=LIVE_AGGREGATE,LIVE_MOVEMENT").json()["events"]]
    assert hidden == ["LIVE_AGGREGATE", "LIVE_MOVEMENT"]
    # LIVE_KILL carries its enriched fields through unchanged
    lk = client.get("/api/live/feed").json()["events"][0]
    assert lk["distance"] == 137 and lk["killer_slot"] == 3


def test_feed_pages_from_the_newest_end(client):
    """A cold load (since=0) must see the NEWEST events — before 2026-08-18
    it returned the oldest page of the ring (a stale revive) while fresh
    kills fell outside the limit."""
    _post(client, [
        {"type": "SAY", "level_ms": i, "fields": {"text": f"m{i}"}}
        for i in range(30)
    ])
    body = client.get("/api/live/feed?limit=10").json()
    texts = [e["text"] for e in body["events"]]
    assert texts == [f"m{i}" for i in range(20, 30)]  # newest ten, oldest first
    assert body["oldest_seq"] == body["events"][0]["seq"]
    assert body["oldest_seq"] > 1  # gap detectable: events 1..20 were skipped


def test_legacy_kill_deduped_against_livex(client):
    """Both tailers report the same obituary — the legacy copy is suppressed
    when the LIVEX one already landed (same slots, within the window)."""
    _post(client, [
        {"type": "LIVE_KILL", "level_ms": 1786480915000,
         "fields": {"killer_slot": 3, "victim_slot": 5, "mod_id": 34}},
        {"type": "KILL", "level_ms": 100,
         "fields": {"killer_slot": 3, "victim_slot": 5,
                    "killer": "vid", "victim": "lgz", "mod": "MOD_MP40"}},
        # different pair still goes through
        {"type": "KILL", "level_ms": 101,
         "fields": {"killer_slot": 1, "victim_slot": 2,
                    "killer": "a", "victim": "b", "mod": "MOD_MP40"}},
    ])
    types = [e["type"] for e in client.get("/api/live/feed").json()["events"]]
    assert types == ["LIVE_KILL", "KILL"]


def test_records_carry_source_and_clock(client):
    _post(client, [
        {"type": "LIVE_MAP", "level_ms": 1786480914000,
         "fields": {"map_name": "supply"}},
        {"type": "MAP", "level_ms": 10, "fields": {"map_name": "supply"}},
    ])
    events = client.get("/api/live/feed").json()["events"]
    assert [e["clock"] for e in events] == ["epoch", "level"]
    assert all(e["source"] == "tailer" for e in events)


def test_feed_retention_hides_stale_events(client, monkeypatch):  # noqa: ARG001
    import website.backend.routers.live as live_mod  # noqa: PLC0415
    _post(client, [{"type": "SAY", "level_ms": 1, "fields": {"text": "old"}}])
    # age the ring artificially past the retention window
    for e in live_mod._events:  # noqa: SLF001 — aging the ring is the point
        e["received_at"] -= live_mod._FEED_RETENTION_SECONDS + 5  # noqa: SLF001
    assert client.get("/api/live/feed").json()["events"] == []


def test_state_reports_the_last_half_from_a_replayed_evening(client, monkeypatch):
    """The recorded evening of 2026-09-07 (chat stripped) through the real
    ingest path: after the replay, /api/live/state names how the last half
    ended. Wall-clock durations are ~0 here because the batch lands in one
    second; the reducer test covers the level-time durations."""
    from pathlib import Path

    from vps_scripts.liveview_parser import parse_line
    from website.backend.services.live_state import LiveStateReducer
    c = client
    monkeypatch.setattr(live, "_state", LiveStateReducer())  # noqa: SLF001
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "liveview" / "legacy3_evening_2026-09-07.txt"
    batch = []
    for line in fixture.read_text(encoding="utf-8", errors="ignore").splitlines():
        ev = parse_line(line)
        if ev is None:
            continue
        batch.append({"type": ev.type, "level_ms": ev.level_ms, "fields": ev.fields})
        if len(batch) == 200:
            assert _post(c, batch).status_code == 200
            batch = []
    if batch:
        assert _post(c, batch).status_code == 200
    snap = c.get("/api/live/state").json()
    last = snap["last_round_result"]
    assert last is not None
    assert last["reason"] in ("timelimit", "surrender", "objective")
    assert "attacking_side" in snap and "time_to_beat_seconds" in snap


def test_feed_recovers_cursor_from_previous_worker(client):
    _post(client, [{"type": "ROUND_START"}])
    page = client.get('/api/live/feed?since=9000').json()
    assert [e['type'] for e in page['events']] == ['ROUND_START']
    assert page['cursor_reset'] is True
    assert page['last_seq'] == 1
    assert page['stream_id'] == client.get('/api/live/feed').json()['stream_id']


def test_hidden_telemetry_is_not_a_delivery_gap(client):
    _post(client, [{"type": "ROUND_START"}])
    _post(client, [{"type": "LIVE_MOVEMENT", "fields": {"players": []}}] * 10)
    _post(client, [{"type": "ROUND_END"}])
    page = client.get('/api/live/feed?since=1').json()
    assert page['oldest_seq'] == 12
    assert page['gap'] is False


def test_page_truncation_reports_a_real_gap(client):
    _post(client, [{"type": "ROUND_START"}] * 5)
    page = client.get('/api/live/feed?since=1&limit=2').json()
    assert page['gap'] is True


def test_event_payload_cannot_replace_transport_identity(client):
    _post(client, [{"type": "ROUND_START", "fields": {
        'seq': 9000, 'type': 'TEAM_CHAT_REDACTED', 'received_at': 0,
        'source': 'forged', 'clock': 'forged', 'level_ms': 999,
    }}])
    event = client.get('/api/live/feed').json()['events'][0]
    assert event['seq'] == 1 and event['type'] == 'ROUND_START'
    assert event['source'] == 'tailer' and event['clock'] == 'level'
    assert event['level_ms'] is None and event['received_at'] > 0


@pytest.mark.parametrize('route', ['feed', 'state', 'status'])
def test_configured_upstream_failure_is_unavailable(client, monkeypatch, route):
    from unittest.mock import AsyncMock
    monkeypatch.setattr(live, '_UPSTREAM', 'http://unused.invalid/api/live')
    monkeypatch.setattr(live, '_proxy', AsyncMock(return_value=None))
    response = client.get('/api/live/' + route)
    assert response.status_code == 503
    assert response.json()['detail'] == 'Live upstream unavailable'


def test_ring_eviction_and_retention_report_gaps(client, monkeypatch):
    from collections import deque
    monkeypatch.setattr(live, '_events', deque(maxlen=2))
    _post(client, [{'type': 'ROUND_START'}] * 4)
    assert client.get('/api/live/feed?since=1').json()['gap'] is True
    for event in live._events:  # noqa: SLF001 -- explicit ring aging
        event['received_at'] -= live._FEED_RETENTION_SECONDS + 1  # noqa: SLF001
    assert client.get('/api/live/feed?since=3').json()['gap'] is True


@pytest.mark.parametrize('hidden_type', ['LIVE_MOVEMENT', 'LIVE_AGGREGATE'])
def test_evicted_hidden_telemetry_only_gaps_when_requested(client, monkeypatch, hidden_type):
    from collections import deque
    monkeypatch.setattr(live, '_events', deque(maxlen=3))
    assert _post(client, [{'type': 'ROUND_START'}]).status_code == 200
    assert _post(client, [{'type': hidden_type}] * 5).status_code == 200
    default = client.get('/api/live/feed?since=1').json()
    assert default['events'] == []
    assert default['gap'] is False
    assert client.get('/api/live/feed?since=1&types=ROUND_END').json()['gap'] is False
    assert client.get('/api/live/feed?since=1&types=' + hidden_type).json()['gap'] is True


def test_evicted_visible_event_only_gaps_for_matching_filter(client, monkeypatch):
    from collections import deque
    monkeypatch.setattr(live, '_events', deque(maxlen=3))
    _post(client, [{'type': 'ROUND_START'}, {'type': 'ROUND_END'}])
    _post(client, [{'type': 'LIVE_MOVEMENT'}] * 4)
    assert client.get('/api/live/feed?since=1').json()['gap'] is True
    assert client.get('/api/live/feed?since=1&types=ROUND_START').json()['gap'] is False
    assert client.get('/api/live/feed?since=1&types=ROUND_END').json()['gap'] is True


@pytest.mark.asyncio
async def test_feed_freezes_event_names_before_later_slot_reuse(monkeypatch):
    """The real ASGI feed must carry identity, not require a current roster join."""
    import httpx

    monkeypatch.setattr(live, '_events', type(live._events)(maxlen=live._BUFFER_MAX))  # noqa: SLF001
    monkeypatch.setattr(live, '_state', live.LiveStateReducer())
    monkeypatch.setattr(live, '_UPSTREAM', '')
    monkeypatch.setattr(live, '_recent_livex_kills', {})
    monkeypatch.setattr(live, '_evicted_by_type', {})
    monkeypatch.setattr(live, '_seq', 0)
    monkeypatch.setenv('INTERNAL_API_SECRET', 'fixture-local-only')
    app = FastAPI()
    app.include_router(live.router, prefix='/api/live')
    headers = {'X-Internal-Token': os.environ['INTERNAL_API_SECRET']}
    snapshots = []
    original_snapshot = live.LiveStateReducer.snapshot

    def counted_snapshot(self, *args, **kwargs):
        snapshots.append(1)
        return original_snapshot(self, *args, **kwargs)

    monkeypatch.setattr(live.LiveStateReducer, 'snapshot', counted_snapshot)
    batch = [
        {'type': 'TEAM_CHANGE', 'fields': {'slot': 3, 'team': 1, 'name': 'original'}},
        {'type': 'TEAM_CHANGE', 'fields': {'slot': 4, 'team': 2, 'name': 'victim'}},
        {'type': 'LIVE_KILL', 'fields': {'killer_slot': 3, 'victim_slot': 4}},
        {'type': 'DISCONNECT', 'fields': {'slot': 3}},
        {'type': 'LIVE_KILL', 'fields': {'killer_slot': 3, 'victim_slot': 4}},
        {'type': 'TEAM_CHANGE', 'fields': {'slot': 3, 'team': 1, 'name': 'replacement'}},
        {'type': 'LIVE_KILL', 'fields': {'killer_slot': 3, 'victim_slot': 4}},
        {'type': 'KILL', 'fields': {'killer_slot': 8, 'victim_slot': 9,
                                  'killer': 'source killer', 'victim': 'source victim'}},
        {'type': 'SAY', 'fields': {'name': 'source speaker', 'text': 'hello'}},
        {'type': 'DYNAMITE', 'fields': {'slot': 3, 'action': 'plant', 'objective': 'fixture'}},
        {'type': 'LIVE_KILL', 'fields': {'killer_slot': 64, 'victim_slot': -1}},
        *[{'type': kind, 'fields': {'slots': '3 4'}} for kind in ('REVIVE', 'SUPPLY', 'SHOVE')],
    ]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as c:
        result = await c.post('/api/live/events', json={'events': batch}, headers=headers)
        assert result.status_code == 200, result.text
        assert len(snapshots) == 1  # existing batch validation, never a snapshot per event
        before = (await c.get('/api/live/feed')).json()['events']
        kills = [e for e in before if e['type'] in {'KILL', 'LIVE_KILL'}]
        assert [(e['killer'], e['victim']) for e in kills] == [
            ('original', 'victim'), (None, 'victim'), ('replacement', 'victim'),
            ('source killer', 'source victim'), (None, None),
        ]
        assert next(e for e in before if e['type'] == 'DISCONNECT')['name'] == 'original'
        assert next(e for e in before if e['type'] == 'SAY')['name'] == 'source speaker'
        assert next(e for e in before if e['type'] == 'DYNAMITE')['name'] == 'replacement'
        for event in [e for e in before if e['type'] in {'REVIVE', 'SUPPLY', 'SHOVE'}]:
            assert (event['actor_name'], event['target_name']) == ('replacement', 'victim')
        result = await c.post('/api/live/events', json={'events': [
            {'type': 'TEAM_CHANGE', 'fields': {'slot': 3, 'team': 1, 'name': 'later rename'}},
        ]}, headers=headers)
        assert result.status_code == 200
        after = (await c.get('/api/live/feed')).json()['events']
        assert after[:len(before)] == before


def _dedup_kill(kind, killer=3, victim=5):
    return {'type': kind, 'fields': {'killer_slot': killer, 'victim_slot': victim}}


@pytest.mark.parametrize('kind', ['CONNECT', 'DISCONNECT'])
@pytest.mark.parametrize('slot', [3, 5, '3', '5'])
def test_dedup_does_not_cross_slot_lifecycle(client, kind, slot):
    events = [_dedup_kill('LIVE_KILL'), {'type': kind, 'fields': {'slot': slot}},
              _dedup_kill('KILL')]
    response = _post(client, events)
    assert response.status_code == 200
    assert response.json()['accepted'] == 3
    assert [e['type'] for e in client.get('/api/live/feed').json()['events']] == [
        'LIVE_KILL', kind, 'KILL',
    ]


def test_dedup_lifecycle_preserves_other_pairs(client):
    response = _post(client, [_dedup_kill('LIVE_KILL'), _dedup_kill('LIVE_KILL', 7, 8),
                             {'type': 'DISCONNECT', 'fields': {'slot': 3}},
                             _dedup_kill('KILL'), _dedup_kill('KILL', 7, 8)])
    assert response.json()['accepted'] == 4
    assert [e['killer_slot'] for e in client.get('/api/live/feed').json()['events']
            if e['type'] == 'KILL'] == [3]


@pytest.mark.parametrize('boundary', ['MAP', 'LIVE_MAP', 'ROUND_START', 'INIT_GAME'])
def test_dedup_does_not_cross_accepted_map_or_round_reset(client, boundary):
    _post(client, [{'type': 'MAP', 'fields': {'map_name': 'supply'}}])
    response = _post(client, [_dedup_kill('LIVE_KILL'),
                             {'type': boundary, 'fields': {'map_name': 'radar'}},
                             _dedup_kill('KILL')])
    assert response.status_code == 200 and response.json()['accepted'] == 3


@pytest.mark.parametrize('confirmation', ['same', 'rejected_flipback', 'empty'])
def test_dedup_survives_map_confirmation_or_rejected_change(client, confirmation):
    _post(client, [{'type': 'MAP', 'fields': {'map_name': 'radar'}},
                   {'type': 'MAP', 'fields': {'map_name': 'supply'}}])
    name = {'same': 'supply', 'rejected_flipback': 'radar', 'empty': ''}[confirmation]
    response = _post(client, [_dedup_kill('LIVE_KILL'),
                             {'type': 'LIVE_MAP', 'fields': {'map_name': name}},
                             _dedup_kill('KILL')])
    assert response.status_code == 200 and response.json()['accepted'] == 2


@pytest.mark.parametrize('action', ['lifecycle', 'map', 'round'])
def test_rejected_batch_retains_unconsumed_dedup_state(client, action):
    _post(client, [{'type': 'MAP', 'fields': {'map_name': 'supply'}}, _dedup_kill('LIVE_KILL')])
    event = {'lifecycle': {'type': 'DISCONNECT', 'fields': {'slot': 3}},
             'map': {'type': 'MAP', 'fields': {'map_name': 'radar'}},
             'round': {'type': 'ROUND_START'}}[action]
    response = _post(client, [event, {'type': 'MAP', 'fields': {'map_name': ['invalid']}}])
    assert response.status_code == 422
    assert _post(client, [_dedup_kill('KILL')]).json()['accepted'] == 0


def test_dedup_reconnected_player_kill_remains_in_actual_feed(client):
    events = [
        {'type': 'TEAM_CHANGE', 'fields': {'slot': 3, 'team': 1, 'name': 'first occupant'}},
        _dedup_kill('LIVE_KILL'),
        {'type': 'DISCONNECT', 'fields': {'slot': 3}},
        {'type': 'CONNECT', 'fields': {'slot': 3}},
        {'type': 'TEAM_CHANGE', 'fields': {'slot': 3, 'team': 1, 'name': 'next occupant'}},
        {**_dedup_kill('KILL'), 'fields': {'killer_slot': 3, 'victim_slot': 5,
                                        'killer': 'next occupant', 'victim': 'victim'}},
    ]
    response = _post(client, events)
    assert response.status_code == 200 and response.json()['accepted'] == 6
    kills = [e for e in client.get('/api/live/feed').json()['events'] if e['type'] in {'KILL', 'LIVE_KILL'}]
    assert [(e['type'], e['killer']) for e in kills] == [
        ('LIVE_KILL', 'first occupant'), ('KILL', 'next occupant'),
    ]
    print('ASGI lifecycle proof: accepted=6, feed kills=2, distinct occupant names retained')


def test_dedup_keeps_same_context_retransmission_suppression(client):
    response = _post(client, [_dedup_kill('LIVE_KILL'), _dedup_kill('KILL'), _dedup_kill('KILL')])
    assert response.status_code == 200 and response.json()['accepted'] == 1


def test_dedup_init_game_same_map_starts_new_context(client):
    _post(client, [{'type': 'MAP', 'fields': {'map_name': 'supply'}}, {'type': 'ROUND_START'}])
    response = _post(client, [_dedup_kill('LIVE_KILL'), {'type': 'INIT_GAME'},
                             {'type': 'LIVE_MAP', 'fields': {'map_name': 'supply'}}, _dedup_kill('KILL')])
    assert response.json()['accepted'] == 4
    assert client.get('/api/live/state').json()['current_map'] == 'supply'
