from pathlib import Path

from proximity.parser.parser import ProximityParserV4


def _write_minimal_engagement_file(path: Path, map_name: str, header_round: int, round_end_unix: int) -> None:
    path.write_text(
        "\n".join(
            [
                "# PROXIMITY_TRACKER_V4",
                f"# map={map_name}",
                f"# round={header_round}",
                "# crossfire_window=1000",
                "# escape_time=5000",
                "# escape_distance=300",
                "# position_sample_interval=500",
                "# round_start_unix=1770000000",
                f"# round_end_unix={round_end_unix}",
                "# ENGAGEMENTS",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_round_normalization_prefers_matching_gametime_round(tmp_path):
    proximity_file = tmp_path / "2026-02-11-220202-supply-round-1_engagements.txt"
    _write_minimal_engagement_file(proximity_file, map_name="supply", header_round=1, round_end_unix=1770843722)

    gametimes_dir = tmp_path / "local_gametimes"
    gametimes_dir.mkdir()
    (gametimes_dir / "gametime-supply-R2-1770843722.json").write_text("{}", encoding="utf-8")

    parser = ProximityParserV4(output_dir=str(tmp_path), gametimes_dir=str(gametimes_dir))
    assert parser.parse_file(str(proximity_file)) is True
    assert parser.metadata["round_num"] == 2
    assert parser.metadata["round_num_source"] == "gametime"


def test_round_normalization_falls_back_to_filename_when_gametime_missing(tmp_path):
    proximity_file = tmp_path / "2026-02-11-220202-supply-round-2_engagements.txt"
    _write_minimal_engagement_file(proximity_file, map_name="supply", header_round=1, round_end_unix=1770843722)

    parser = ProximityParserV4(output_dir=str(tmp_path), gametimes_dir=str(tmp_path / "missing_gametimes"))
    assert parser.parse_file(str(proximity_file)) is True
    assert parser.metadata["round_num"] == 2
    assert parser.metadata["round_num_source"] == "filename"

