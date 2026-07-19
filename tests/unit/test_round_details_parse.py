"""shared.round_details — canonical round_details parsing (IMP-002)."""
from __future__ import annotations

import json

from shared.round_details import (
    ROUND_DETAILS_VERSION,
    entry_map_name,
    entry_points,
    parse_round_details,
)


def test_v1_bare_list_str_and_native():
    entries = [{"map": "supply", "team1_points": 2, "team2_points": 0}]
    assert parse_round_details(json.dumps(entries)) == (1, entries)
    assert parse_round_details(entries) == (1, entries)


def test_v2_dict_wrapper():
    payload = {"round_details_version": 2, "maps": [{"map": "radar"}]}
    version, maps = parse_round_details(json.dumps(payload))
    assert version == 2 and maps == [{"map": "radar"}]
    assert ROUND_DETAILS_VERSION == 2


def test_unparseable_and_empty_inputs():
    for bad in (None, "", "   ", "not json", "42", json.dumps({"no_maps": 1}),
                json.dumps({"maps": "not-a-list"})):
        assert parse_round_details(bad) == (0, [])


def test_non_dict_entries_are_dropped():
    _, maps = parse_round_details(json.dumps([{"map": "a"}, "junk", 3]))
    assert maps == [{"map": "a"}]


def test_entry_points_both_key_sets_and_missing():
    assert entry_points({"team1_points": 2, "team2_points": 0}) == (2, 0)
    assert entry_points({"team_a_points": 0, "team_b_points": 2}) == (0, 2)
    assert entry_points({"map": "supply"}) is None       # neither key set
    assert entry_points({"team1_points": "x", "team2_points": 0}) is None


def test_entry_map_name_both_spellings():
    assert entry_map_name({"map": "supply"}) == "supply"
    assert entry_map_name({"map_name": "radar"}) == "radar"
    assert entry_map_name({}) is None
    assert entry_map_name({"map": ""}) is None
