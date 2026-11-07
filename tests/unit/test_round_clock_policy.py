"""Every resolved source must vote; silence never establishes a clock basis."""
import json

import pytest

from website.backend.services.round_web_service import get_round_snapshot, load_capture_policy

KNOWN = {"status": "declared", "value": "level_time_offset_v1"}


class ManifestDB:
    def __init__(self, values):
        self.values = values

    async def fetch_all(self, sql, params):
        assert "f.capabilities" in sql and "FROM rounds r" in sql
        assert params == (1,)
        return [(value,) for value in self.values]


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [
    None, "null", "invalid-json", [], {},
    {"event_time_basis": None},
    {"event_time_basis": {"status": "missing", "value": None}},
    {"event_time_basis": {"status": "conflicting", "value": None}},
    {"event_time_basis": {"status": "unsupported", "value": None}},
    {"event_time_basis": {"status": "declared", "value": "active_time_v2"}},
    {"event_time_basis": KNOWN["value"]},
    {"event_time_basis": {"status": "declared", "value": []}},
])
async def test_missing_or_invalid_sibling_prevents_clock_claim(bad):
    good = {"source": "declared", "event_time_basis": KNOWN}
    for values in [[good, bad], [bad, good]]:
        policy = await load_capture_policy(ManifestDB(values), 1)
        assert policy.event_time_basis is None


@pytest.mark.asyncio
async def test_all_explicit_clocks_agree_independently_of_feature_source():
    values = [{"source": "sections_observed", "event_time_basis": KNOWN},
              json.dumps({"source": "declared", "event_time_basis": KNOWN})]
    policy = await load_capture_policy(ManifestDB(values), 1)
    assert policy.event_time_basis == KNOWN["value"]
    assert (await load_capture_policy(ManifestDB([]), 1)).event_time_basis is None


@pytest.mark.asyncio
@pytest.mark.parametrize("sibling", [{"event_time_basis": KNOWN}, None])
@pytest.mark.parametrize("empty", [False, True])
async def test_snapshot_publishes_agreement_without_changing_positions(sibling, empty):
    from tests.unit.test_round_web_service import _SnapshotStubDb, _stub_track

    class SnapshotDB(_SnapshotStubDb):
        async def fetch_all(self, sql, params=None):
            if "f.capabilities" in sql:
                return [({"event_time_basis": KNOWN},), (sibling,)]
            return await super().fetch_all(sql, params)

    payload = await get_round_snapshot(
        SnapshotDB(tracks=[] if empty else [_stub_track("A", 123.0)]), 1, 5000)
    expected = KNOWN if sibling else {"status": "unknown", "value": None}
    assert payload["capture_policy"]["event_time_basis"] == expected
    assert payload["t_ms"] == 5000
    assert payload["player_count"] == (0 if empty else 1)
    if not empty:
        assert payload["players"][0]["x"] == 123.0
    print("SNAPSHOT CLOCK PROOF:", json.dumps(payload["capture_policy"]["event_time_basis"]))
