from scripts.backfill_gametimes import _build_round_metadata_from_map


def test_build_round_metadata_normalizes_side_and_end_reason():
    metadata = {
        "map": "supply",
        "round": "1",
        "winner": "allies",
        "defender": "axis",
        "lua_endreason": "objective",
        "lua_roundstart": "1770901200",
        "lua_roundend": "1770901800",
    }

    round_metadata = _build_round_metadata_from_map(metadata)

    assert round_metadata["winner_team"] == 2
    assert round_metadata["defender_team"] == 1
    assert round_metadata["end_reason"] == "NORMAL"


def test_build_round_metadata_normalizes_invalid_values_to_unknown():
    metadata = {
        "map": "supply",
        "round": "2",
        "winner": "9",
        "defender": "n/a",
        "lua_endreason": "mapchange",
        "lua_roundstart": "1770901800",
        "lua_roundend": "1770902400",
    }

    round_metadata = _build_round_metadata_from_map(metadata)

    assert round_metadata["winner_team"] == 0
    assert round_metadata["defender_team"] == 0
    assert round_metadata["end_reason"] == "MAP_CHANGE"
