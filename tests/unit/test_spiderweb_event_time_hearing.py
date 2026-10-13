"""Historical gunfire admission must not depend on the replay slider position."""

import pytest

from website.backend.services.round_web_service import (
    CapturePolicy,
    build_snapshot,
    load_round_information_state,
)


def point(t, x):
    return {"time": t, "x": x, "y": 0, "z": 0, "health": 100}


def life(path, *, start=0, end=None, identity=1):
    return ("H", "Holder", "AXIS", "MEDIC", start, end, path, "supply", identity)


class ShotDB:
    async def fetch_all(self, query, params):
        if "FROM proximity_shot_fired" in query:
            return [("S", 1000, 0, 0, 0)]
        if "FROM rounds r" in query:
            return [(100,)]
        return []


@pytest.mark.asyncio
@pytest.mark.parametrize("lives,heard", [
    pytest.param([life([point(1000, 2000), point(5000, 100)])], False, id="walked-in"),
    pytest.param([life([point(1000, 100), point(5000, 2000)])], True, id="walked-out"),
    pytest.param([life([point(4000, 100)], start=4000)], False, id="joined-after-shot"),
    pytest.param([life([point(1100, 100)])], False, id="only-future-sample"),
    pytest.param([life([point(1000, 100)], end=1000)], False, id="death-boundary"),
    pytest.param([life([point(100, 100)])], False, id="stale-listener"),
    pytest.param([life([point(1000, 100)]),
                  life([point(1000, 100)], identity=2)], False, id="overlap-conflict"),
    pytest.param([life([point(0, 100)], end=900),
                  life([point(4000, 100)], start=4000, identity=2)], False,
                 id="dead-at-shot"),
    pytest.param([life([point(1000, 100)], end=2000),
                  life([point(4000, 2000)], start=4000, identity=2)], True,
                 id="heard-in-previous-life"),
])
async def test_listener_is_located_at_shot_time(lives, heard):
    tracks = {"H": lives}
    payload = await load_round_information_state(
        ShotDB(), 1, 5000, build_snapshot(tracks, 5000), {},
        CapturePolicy(capabilities={"shot_fired": "enabled"}), tracks,
    )
    beliefs = [b for b in payload["holders"]["H"]["beliefs"] if b["source"] == "gunfire"]
    assert bool(beliefs) is heard
    if beliefs:
        assert beliefs[0]["t_observed"] == 1000
        assert beliefs[0]["subject_guid"] is None


@pytest.mark.parametrize("region,heard", [
    pytest.param(None, False, id="unknown"),
    pytest.param((100, 0, 0, 44), True, id="fresh"),
    pytest.param((100, 0, 0, 1700), False, id="stale-region"),
    pytest.param((100, 0, 0, 2500), False, id="conflicted-region"),
    pytest.param((1286, 0, 0, 44), True, id="inclusive-boundary"),
    pytest.param((1287, 0, 0, 44), False, id="uncertainty-crosses-boundary"),
    pytest.param((float("nan"), 0, 0, 0), False, id="invalid-position"),
    pytest.param((0, 0, 0, -1), False, id="invalid-radius"),
])
def test_admission_respects_listener_uncertainty(region, heard):
    from website.backend.services.information_state import Region, gunfire_beliefs

    calls = []

    def locate(guid, time):
        calls.append((guid, time))
        return Region(*region) if region is not None else None

    beliefs = gunfire_beliefs(
        [("S", 1000, 0, 0, 0), ("S", 1200, 0, 0, 0)],
        iter(["H", "S"]), audible_radius=1330, locate=locate,
    )
    assert calls == [("H", 1000), ("H", 1200)]
    assert len(beliefs) == (2 if heard else 0)


@pytest.mark.asyncio
async def test_missing_tracks_do_not_fall_back_to_snapshot_position():
    tracks = {"H": [life([point(1000, 100), point(5000, 100)])]}
    payload = await load_round_information_state(
        ShotDB(), 1, 5000, build_snapshot(tracks, 5000), {},
        CapturePolicy(capabilities={"shot_fired": "enabled"}), None,
    )
    assert payload["holders"]["H"]["beliefs"] == []


def test_listener_life_gate_preserves_default_subject_localization():
    from website.backend.services.round_web_service import make_locator

    tracks = {"H": [life([point(1000, 100)], end=1000)]}
    assert make_locator(tracks)("H", 1000) is not None
    assert make_locator(tracks, require_alive=True)("H", 1000) is None


def test_historical_lookup_does_not_scan_every_sample_per_shot():
    from website.backend.services.round_web_service import find_position_floor

    class Sample(dict):
        reads = 0

        def get(self, key, default=None):
            type(self).reads += 1
            return super().get(key, default)

    path = [Sample(time=i * 200, x=i) for i in range(8192)]
    sample, stale, index = find_position_floor(path, 1_000_099)
    assert (sample["x"], stale, index) == (5000, 99, 5000)
    assert Sample.reads <= 16, "each shot must use a binary lookup, not scan the path"
