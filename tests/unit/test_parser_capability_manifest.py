"""The parser end of the manifest: reading a declaration, and proving one.

These run against files built here rather than fixtures on disk, because the
whole point is what the parser concludes from a file's SHAPE — which sections
carried rows — and that is easiest to state by constructing the shape.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from proximity.parser.capability_manifest import DISABLED, ENABLED, UNKNOWN
from proximity.parser.parser import ProximityParserV4

HEADER = (
    "# PROXIMITY_TRACKER_V6\n"
    "# map=supply\n"
    "# round=1\n"
    "# crossfire_window=1000\n"
    "# escape_time=5000\n"
    "# escape_distance=300\n"
    "# position_sample_interval=200\n"
    "# round_start_unix=1771618171\n"
    "# round_end_unix=1771618924\n"
)

TRACK_ROW = (
    "# PLAYER_TRACKS\n"
    "# guid;name;team;class;spawn_time;death_time;first_move_time;death_type;samples;path\n"
    "AAAA;p1;AXIS;0;0;1000;100;killed;2;0,1.0,2.0,3.0,100,0,1,0,0,start|"
    "1000,1.0,2.0,3.0,0,0,1,0,0,death\n"
)


def _write(tmp_path: Path, body: str) -> str:
    path = tmp_path / "2026-08-02-120000-supply-round-1_engagements.txt"
    path.write_text(body)
    return str(path)


def _manifest(tmp_path: Path, body: str) -> dict:
    parser = ProximityParserV4()
    parser.parse_file(_write(tmp_path, body))
    return parser.build_capability_manifest()


def test_sections_with_rows_are_recorded(tmp_path: Path) -> None:
    """A regression test with a story: the first version of this recording sat
    AFTER the section-detection chain, where every branch had already consumed
    its line with `continue`, so nothing was ever recorded. Every unit test
    still passed — only parsing a real file exposed it."""
    manifest = _manifest(tmp_path, HEADER + TRACK_ROW)
    assert "PLAYER_TRACKS" in manifest["sections_with_rows"]


def test_a_header_without_rows_proves_nothing(tmp_path: Path) -> None:
    """ENGAGEMENTS is written unconditionally, so an empty one is not evidence."""
    body = HEADER + "# ENGAGEMENTS\n# id;start_time\n" + TRACK_ROW
    manifest = _manifest(tmp_path, body)
    assert "ENGAGEMENTS" not in manifest["sections_with_rows"]
    assert manifest["capabilities"]["engagement_tracking"] == UNKNOWN


def test_missing_section_is_unknown_not_disabled(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, HEADER + TRACK_ROW)
    assert manifest["source"] == "sections_observed"
    assert manifest["capabilities"]["shot_fired"] == UNKNOWN
    assert DISABLED not in manifest["capabilities"].values()


def test_declaration_is_read_from_the_header(tmp_path: Path) -> None:
    body = (
        HEADER
        + "# tracker_version_full=6.11\n"
        + "# test_mode=0\n"
        + "# capabilities=shot_fired:0,aim_lock:1\n"
        + TRACK_ROW
    )
    manifest = _manifest(tmp_path, body)
    assert manifest["source"] == "declared"
    assert manifest["tracker_version_full"] == "6.11"
    assert manifest["test_mode"] is False
    assert manifest["capabilities"]["shot_fired"] == DISABLED
    assert manifest["capabilities"]["aim_lock"] == ENABLED


def test_test_mode_round_is_marked(tmp_path: Path) -> None:
    body = HEADER + "# test_mode=1\n# capabilities=shot_fired:0\n" + TRACK_ROW
    assert _manifest(tmp_path, body)["test_mode"] is True


def test_capture_interval_is_carried_from_the_header(tmp_path: Path) -> None:
    """Parsed since v4 and thrown away ever since; the web page had to invent it."""
    assert _manifest(tmp_path, HEADER + TRACK_ROW)["position_sample_interval_ms"] == 200


def test_parser_state_does_not_leak_between_files(tmp_path: Path) -> None:
    """One parser, two files: the second must not inherit the first's sections."""
    parser = ProximityParserV4()
    rich = tmp_path / "a_engagements.txt"
    rich.write_text(
        HEADER + TRACK_ROW + "# SHOT_FIRED\n# time;guid\n100;AAAA;1;0;0;0;0.0;0.0\n"
    )
    plain = tmp_path / "b_engagements.txt"
    plain.write_text(HEADER + TRACK_ROW)

    parser.parse_file(str(rich))
    assert parser.build_capability_manifest()["capabilities"]["shot_fired"] == ENABLED
    parser.parse_file(str(plain))
    assert parser.build_capability_manifest()["capabilities"]["shot_fired"] == UNKNOWN


@pytest.mark.parametrize("declared", ["", "shot_fired:1"])
def test_empty_declaration_still_counts_as_declared(tmp_path: Path, declared: str) -> None:
    """A tracker that declares nothing has still declared; `None` is reserved
    for files written before the contract existed."""
    body = HEADER + f"# capabilities={declared}\n" + TRACK_ROW
    assert _manifest(tmp_path, body)["source"] == "declared"


# --- the standalone scanner must not drift from the parser -----------------

REAL_FILES = sorted(
    Path("/home/samba/share/slomix_discord/local_proximity").glob("*_engagements.txt")
)


@pytest.mark.skipif(not REAL_FILES, reason="no raw proximity files on this host")
@pytest.mark.parametrize("index", [0, len(REAL_FILES) // 2, -1])
def test_scan_file_agrees_with_the_parser(index: int) -> None:
    """One answer, two code paths — this is what keeps them one answer.

    `scan_file` exists so the backfill need not run a full parse over 800
    rounds. That saving is only safe while the two agree, so the check runs on
    real files from three points in the corpus rather than on a fixture whose
    shape we chose.
    """
    from proximity.parser.capability_manifest import build_manifest, scan_file

    path = str(REAL_FILES[index])
    parser = ProximityParserV4()
    parser.parse_file(path)
    from_parser = parser.build_capability_manifest()

    scanned = scan_file(path)
    from_scan = build_manifest(
        sections_with_rows=scanned["sections_with_rows"],
        declared=scanned["declared"],
        test_mode=scanned["test_mode"],
        tracker_version_full=scanned["tracker_version_full"],
        position_sample_interval_ms=scanned["position_sample_interval_ms"],
    )
    assert from_scan == from_parser
