"""`/proximity/player/{guid}/profile` and `/radar` gained response models
on 2026-09-06 (the open half of #945).

Both routes serialise with `response_model_exclude_unset`, because two of
their keys exist only on some forms: `requested_guid` was added to the
profile after the recording below was made, and the radar's two
`teamplay_*` fallback fields exist only on the CF/TR form. Under that rule
a recording round-trips byte-for-byte; the plain dump would add the
defaulted keys, which is why these three recordings are checked here and
not in test_response_models_drop_nothing's strict list.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from website.backend.routers.proximity_player import ProxPlayerProfile, ProxPlayerRadar

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "api_responses"

CASES = [
    ("api_proximity_player_guid_profile.json", ProxPlayerProfile),
    ("api_proximity_player_guid_radar.json", ProxPlayerRadar),
    ("api_proximity_player_radar_fallback_form.json", ProxPlayerRadar),
]


@pytest.mark.parametrize(("fixture", "model"), CASES, ids=[f for f, _ in CASES])
def test_the_recording_round_trips_under_the_routes_own_serialisation(fixture, model):
    raw = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
    out = model.model_validate(raw).model_dump(mode="json", exclude_unset=True)
    assert out == raw, {"missing": sorted(set(raw) - set(out)), "invented": sorted(set(out) - set(raw))}


def test_the_fallback_radar_alone_carries_the_two_fallback_fields():
    healthy = json.loads((FIXTURES / "api_proximity_player_guid_radar.json").read_text(encoding="utf-8"))
    fallback = json.loads((FIXTURES / "api_proximity_player_radar_fallback_form.json").read_text(encoding="utf-8"))
    assert "teamplay_sample_count" not in healthy and "teamplay_fallback_reason" not in healthy
    assert fallback["teamplay_sample_count"] == 0 and fallback["teamplay_degraded"] is True
    assert all(v is None for v in fallback["unscored"].values())


def test_control_the_plain_dump_would_invent_the_defaulted_keys():
    """Why exclude_unset is on the route: without it the profile recording
    grows a `requested_guid: null` it never had."""
    raw = json.loads((FIXTURES / "api_proximity_player_guid_profile.json").read_text(encoding="utf-8"))
    plain = ProxPlayerProfile.model_validate(raw).model_dump(mode="json")
    assert set(plain) - set(raw) == {"requested_guid"}
