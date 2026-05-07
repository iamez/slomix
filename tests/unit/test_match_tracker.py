"""Tests for bot/core/match_tracker.py.

MatchTracker is the canonical R1+R2 pairing logic — every code path
that needs "what's the match_id for this file?" or "which R1 goes with
this R2?" delegates here. A regression here would corrupt every match
correlation downstream (broken R2 differential, wrong KIS aggregation,
mis-paired team rosters).

Pin every static-method's contract.
"""
from __future__ import annotations

from pathlib import Path

from bot.core.match_tracker import MatchTracker, match_tracker


# ---------------------------------------------------------------------------
# extract_match_components
# ---------------------------------------------------------------------------


def test_extract_components_standard_filename():
    out = MatchTracker.extract_match_components(
        "2025-11-06-234153-etl_frostbite-round-2.txt",
    )
    assert out == {
        "date": "2025-11-06",
        "time": "234153",
        "map": "etl_frostbite",
        "round": "2",
        "base_match_id": "2025-11-06-etl_frostbite",
    }


def test_extract_components_round_1():
    out = MatchTracker.extract_match_components(
        "2025-11-06-234153-etl_supply-round-1.txt",
    )
    assert out["round"] == "1"
    assert out["base_match_id"] == "2025-11-06-etl_supply"


def test_extract_components_handles_underscores_in_map_name():
    out = MatchTracker.extract_match_components(
        "2025-11-06-180000-te_escape2_b3-round-2.txt",
    )
    assert out["map"] == "te_escape2_b3"
    assert out["base_match_id"] == "2025-11-06-te_escape2_b3"


def test_extract_components_handles_hyphens_in_map_name():
    """Map name can contain hyphens — regex is non-greedy so the
    'round-N' suffix wins the parse."""
    out = MatchTracker.extract_match_components(
        "2025-11-06-180000-some-hyphenated-map-round-1.txt",
    )
    # The regex is `(.+?)-round-(\d+)$` so the trailing `-round-N` is
    # the splitter — everything before it is the map.
    assert out["map"] == "some-hyphenated-map"
    assert out["round"] == "1"


def test_extract_components_strips_dot_txt_extension():
    out = MatchTracker.extract_match_components(
        "2025-11-06-180000-supply-round-1.txt",
    )
    assert ".txt" not in out["base_match_id"]


def test_extract_components_falls_back_for_unrecognised_format():
    out = MatchTracker.extract_match_components("totally-broken-filename.txt")
    assert out["date"] == "unknown"
    assert out["time"] == "unknown"
    assert out["map"] == "unknown"
    assert out["round"] == "1"
    # base_match_id falls back to the (extension-stripped) filename
    assert out["base_match_id"] == "totally-broken-filename"


def test_extract_components_round_3_or_higher_accepted_by_pattern():
    """The regex captures any digit run — round-9 parses cleanly even if
    we never produce it; pin so a future "round-3" feature doesn't crash."""
    out = MatchTracker.extract_match_components(
        "2025-11-06-180000-supply-round-9.txt",
    )
    assert out["round"] == "9"


# ---------------------------------------------------------------------------
# generate_match_id
# ---------------------------------------------------------------------------


def test_generate_match_id_strips_timestamp_so_r1_r2_match():
    """THE load-bearing contract: R1 and R2 of the same match produce
    IDENTICAL match_ids. Without this, every R1+R2 correlation breaks."""
    r1 = MatchTracker.generate_match_id("2025-11-06-180000-supply-round-1.txt")
    r2 = MatchTracker.generate_match_id("2025-11-06-181530-supply-round-2.txt")
    assert r1 == r2 == "2025-11-06-supply"


def test_generate_match_id_distinguishes_different_maps_same_day():
    a = MatchTracker.generate_match_id("2025-11-06-180000-supply-round-1.txt")
    b = MatchTracker.generate_match_id("2025-11-06-181530-frostbite-round-1.txt")
    assert a != b


def test_generate_match_id_distinguishes_different_days_same_map():
    a = MatchTracker.generate_match_id("2025-11-06-180000-supply-round-1.txt")
    b = MatchTracker.generate_match_id("2025-11-07-180000-supply-round-1.txt")
    assert a != b


def test_generate_match_id_format_is_date_dash_map():
    out = MatchTracker.generate_match_id("2025-11-06-180000-etl_frostbite-round-2.txt")
    assert out == "2025-11-06-etl_frostbite"


# ---------------------------------------------------------------------------
# find_round_pair
# ---------------------------------------------------------------------------


def test_find_pair_returns_r1_when_target_is_r2():
    files = [
        "2025-11-06-180000-supply-round-1.txt",
        "2025-11-06-181530-supply-round-2.txt",
        "2025-11-06-190000-frostbite-round-1.txt",
    ]
    out = MatchTracker.find_round_pair(
        "2025-11-06-181530-supply-round-2.txt", files,
    )
    assert out == "2025-11-06-180000-supply-round-1.txt"


def test_find_pair_returns_r2_when_target_is_r1():
    files = [
        "2025-11-06-180000-supply-round-1.txt",
        "2025-11-06-181530-supply-round-2.txt",
    ]
    out = MatchTracker.find_round_pair(
        "2025-11-06-180000-supply-round-1.txt", files,
    )
    assert out == "2025-11-06-181530-supply-round-2.txt"


def test_find_pair_returns_none_when_no_pair_exists():
    files = [
        "2025-11-06-180000-supply-round-1.txt",
    ]
    out = MatchTracker.find_round_pair(
        "2025-11-06-180000-supply-round-1.txt", files,
    )
    assert out is None


def test_find_pair_does_not_match_different_map():
    """Pair must share base_match_id (date + map). Different map → no pair."""
    files = [
        "2025-11-06-180000-supply-round-1.txt",
        "2025-11-06-181530-frostbite-round-2.txt",
    ]
    out = MatchTracker.find_round_pair(
        "2025-11-06-180000-supply-round-1.txt", files,
    )
    assert out is None


def test_find_pair_does_not_match_different_day():
    files = [
        "2025-11-06-180000-supply-round-1.txt",
        "2025-11-07-181530-supply-round-2.txt",
    ]
    out = MatchTracker.find_round_pair(
        "2025-11-06-180000-supply-round-1.txt", files,
    )
    assert out is None


def test_find_pair_picks_first_matching_pair():
    """When multiple R2s exist for the same map+day (rare but possible
    with replays), the first one in the list wins. Pin current behaviour."""
    files = [
        "2025-11-06-180000-supply-round-1.txt",
        "2025-11-06-181530-supply-round-2.txt",
        "2025-11-06-185000-supply-round-2.txt",
    ]
    out = MatchTracker.find_round_pair(
        "2025-11-06-180000-supply-round-1.txt", files,
    )
    # find_round_pair returns the FIRST match in iteration order
    assert out == "2025-11-06-181530-supply-round-2.txt"


# ---------------------------------------------------------------------------
# find_round_1_for_round_2 (filesystem glob — uses tmp_path fixture)
# ---------------------------------------------------------------------------


def _touch(directory: Path, name: str) -> Path:
    p = directory / name
    p.write_text("")
    return p


def test_find_r1_for_r2_basic(tmp_path):
    _touch(tmp_path, "2025-11-06-180000-supply-round-1.txt")
    _touch(tmp_path, "2025-11-06-181530-supply-round-2.txt")
    out = MatchTracker.find_round_1_for_round_2(
        "2025-11-06-181530-supply-round-2.txt", tmp_path,
    )
    assert out is not None
    assert out.name == "2025-11-06-180000-supply-round-1.txt"


def test_find_r1_for_r2_returns_none_when_target_is_r1(tmp_path):
    """Caller passed an R1 file — function declines to look up itself."""
    _touch(tmp_path, "2025-11-06-180000-supply-round-1.txt")
    out = MatchTracker.find_round_1_for_round_2(
        "2025-11-06-180000-supply-round-1.txt", tmp_path,
    )
    assert out is None


def test_find_r1_for_r2_returns_none_when_no_r1(tmp_path):
    _touch(tmp_path, "2025-11-06-181530-supply-round-2.txt")
    out = MatchTracker.find_round_1_for_round_2(
        "2025-11-06-181530-supply-round-2.txt", tmp_path,
    )
    assert out is None


def test_find_r1_for_r2_picks_closest_when_multiple_r1(tmp_path):
    """Two R1s on the same day for the same map — pick the one closest
    in time to the R2 (handles back-to-back replay sessions cleanly)."""
    _touch(tmp_path, "2025-11-06-100000-supply-round-1.txt")  # 8h before R2
    _touch(tmp_path, "2025-11-06-175800-supply-round-1.txt")  # 17m before R2
    out = MatchTracker.find_round_1_for_round_2(
        "2025-11-06-181530-supply-round-2.txt", tmp_path,
    )
    assert out is not None
    assert out.name == "2025-11-06-175800-supply-round-1.txt"


def test_find_r1_for_r2_does_not_match_different_map(tmp_path):
    _touch(tmp_path, "2025-11-06-180000-frostbite-round-1.txt")
    out = MatchTracker.find_round_1_for_round_2(
        "2025-11-06-181530-supply-round-2.txt", tmp_path,
    )
    assert out is None


# ---------------------------------------------------------------------------
# validate_match_id
# ---------------------------------------------------------------------------


def test_validate_match_id_accepts_canonical_format():
    assert MatchTracker.validate_match_id("2025-11-06-supply") is True
    assert MatchTracker.validate_match_id("2025-11-06-etl_frostbite") is True
    assert MatchTracker.validate_match_id("2026-04-21-te_escape2") is True


def test_validate_match_id_rejects_timestamp_in_middle():
    """A 6-digit run between dashes → looks like a stray timestamp; reject."""
    assert MatchTracker.validate_match_id(
        "2025-11-06-234153-supply-round-1",
    ) is False


def test_validate_match_id_rejects_trailing_timestamp():
    assert MatchTracker.validate_match_id("2025-11-06-supply-234153") is False


def test_validate_match_id_rejects_round_keyword():
    """`round` token in the ID indicates a leftover round suffix."""
    assert MatchTracker.validate_match_id("2025-11-06-supply-round-1") is False
    assert MatchTracker.validate_match_id("2025-11-06-RoundOnSupply") is False


def test_validate_match_id_rejects_non_iso_date_prefix():
    """Pattern requires YYYY-MM-DD prefix."""
    assert MatchTracker.validate_match_id("supply-2025") is False
    assert MatchTracker.validate_match_id("06-11-2025-supply") is False


# ---------------------------------------------------------------------------
# Singleton sanity
# ---------------------------------------------------------------------------


def test_module_level_singleton_exposes_same_class():
    """The module-level `match_tracker` singleton is the canonical entry
    point for legacy callers — must be an instance of MatchTracker."""
    assert isinstance(match_tracker, MatchTracker)
