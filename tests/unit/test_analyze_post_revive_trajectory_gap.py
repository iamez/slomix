from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from scripts.analyze_post_revive_trajectory_gap import (
    RawCapture,
    Revive,
    RevivedOutcome,
    RoundGate,
    RoundGateMatcher,
    RoundIdentity,
    Track,
    analyze_captures,
    parse_capture,
)

IDENTITY = RoundIdentity("supply", 1, 1_700_000_000, 1_700_000_010)


def _track(
    guid: str,
    spawn: int,
    death: int,
    death_type: str,
) -> Track:
    return Track(guid, spawn, death, death_type)


def _capture(
    tmp_path: Path,
    *,
    tracks: tuple[Track, ...],
    revives: tuple[Revive, ...] = (),
    outcomes: tuple[RevivedOutcome, ...] = (),
    identity: RoundIdentity = IDENTITY,
) -> RawCapture:
    path = tmp_path / f"{identity.round_start_unix}_engagements.txt"
    path.write_text("fixture\n", encoding="utf-8")
    return RawCapture(path, identity, 6, tracks, revives, outcomes)


def test_measures_gap_until_next_normal_spawn_and_cross_checks_subset(tmp_path):
    capture = _capture(
        tmp_path,
        tracks=(
            _track("HUMAN_A", 0, 2_000, "killed"),
            _track("HUMAN_A", 8_000, 10_000, "round_end"),
            _track("HUMAN_B", 0, 10_000, "round_end"),
        ),
        revives=(Revive(3_000, "HUMAN_A"),),
        outcomes=(RevivedOutcome(3_000, "HUMAN_A"),),
    )

    result = analyze_captures([capture], gate_matcher=None)

    assert result["trajectory_gap"]["unavailable_ms"] == 5_000
    assert result["trajectory_gap"]["eligible_player_round_ms"] == 20_000
    assert result["trajectory_gap"]["unavailable_fraction"] == pytest.approx(0.25)
    assert result["complete_roster_snapshot_unavailability"]["unavailable_fraction"] == pytest.approx(0.5)
    assert result["revive_cross_check"] == {
        "primary_revive_callbacks": 1,
        "enemy_kill_revived_outcomes": 1,
        "matched_enemy_kill_subset": 1,
        "enemy_kill_subset_without_callback": 0,
        "primary_callbacks_covered_by_enemy_kill_subset_fraction": 1.0,
    }


def test_multiple_revives_merge_instead_of_double_counting(tmp_path):
    capture = _capture(
        tmp_path,
        tracks=(
            _track("HUMAN_A", 0, 2_000, "killed"),
            _track("HUMAN_A", 9_000, 10_000, "round_end"),
        ),
        revives=(Revive(3_000, "HUMAN_A"), Revive(5_000, "HUMAN_A")),
    )

    result = analyze_captures([capture], gate_matcher=None)

    assert result["trajectory_gap"]["raw_revive_windows"] == 2
    assert result["trajectory_gap"]["merged_player_windows"] == 1
    assert result["trajectory_gap"]["unavailable_ms"] == 6_000


def test_gap_without_later_spawn_ends_at_exact_round_end(tmp_path):
    capture = _capture(
        tmp_path,
        tracks=(
            _track("HUMAN_A", 0, 2_000, "killed"),
            _track("HUMAN_B", 0, 10_000, "round_end"),
        ),
        revives=(Revive(4_000, "HUMAN_A"),),
    )

    result = analyze_captures([capture], gate_matcher=None)

    assert result["trajectory_gap"]["unavailable_ms"] == 6_000
    assert result["trajectory_gap"]["raw_window_endings"] == {"round_end": 1}


def test_warmup_crossing_track_is_clamped_to_round_start(tmp_path):
    capture = _capture(
        tmp_path,
        tracks=(
            _track("HUMAN_A", -500, 2_000, "killed"),
            _track("HUMAN_A", 8_000, 10_000, "round_end"),
        ),
        revives=(Revive(3_000, "HUMAN_A"),),
    )

    result = analyze_captures([capture], gate_matcher=None)

    assert result["population"]["eligible_human_player_rounds"] == 1
    assert result["exclusions"]["human_player_rounds"] == {}
    assert result["trajectory_gap"]["unavailable_ms"] == 5_000


def test_fully_pre_round_life_is_ignored(tmp_path):
    capture = _capture(
        tmp_path,
        tracks=(
            _track("HUMAN_A", -1_000, -100, "killed"),
            _track("HUMAN_A", 0, 2_000, "killed"),
            _track("HUMAN_A", 8_000, 10_000, "round_end"),
        ),
        revives=(Revive(3_000, "HUMAN_A"),),
    )

    result = analyze_captures([capture], gate_matcher=None)

    assert result["population"]["eligible_human_player_rounds"] == 1
    assert result["exclusions"]["human_player_rounds"] == {}
    assert result["trajectory_gap"]["unavailable_ms"] == 5_000


def test_bot_tracks_and_revives_are_excluded(tmp_path):
    capture = _capture(
        tmp_path,
        tracks=(
            _track("HUMAN_A", 0, 10_000, "round_end"),
            _track("OMNIBOT0100000000000000000000000", 0, 2_000, "killed"),
            _track("OMNIBOT0100000000000000000000000", 8_000, 10_000, "round_end"),
        ),
        revives=(Revive(3_000, "OMNIBOT0100000000000000000000000"),),
        outcomes=(RevivedOutcome(3_000, "OMNIBOT0100000000000000000000000"),),
    )

    result = analyze_captures([capture], gate_matcher=None)

    assert result["population"]["eligible_human_player_rounds"] == 1
    assert result["trajectory_gap"]["unavailable_ms"] == 0
    assert result["revive_cross_check"]["primary_revive_callbacks"] == 0


def test_bot_only_round_does_not_dilute_human_snapshot_denominator(tmp_path):
    bot_capture = _capture(
        tmp_path,
        tracks=(_track("OMNIBOT0100000000000000000000000", 0, 10_000, "round_end"),),
    )

    result = analyze_captures([bot_capture], gate_matcher=None)

    assert result["population"]["capture_rounds_included"] == 1
    assert result["population"]["eligible_human_rounds"] == 0
    assert result["complete_roster_snapshot_unavailability"]["eligible_round_ms"] == 0
    assert result["complete_roster_snapshot_unavailability"]["unavailable_fraction"] is None


def test_overlapping_lives_exclude_player_round_from_both_sides(tmp_path):
    capture = _capture(
        tmp_path,
        tracks=(
            _track("HUMAN_A", 0, 6_000, "killed"),
            _track("HUMAN_A", 5_000, 10_000, "round_end"),
            _track("HUMAN_B", 0, 10_000, "round_end"),
        ),
        revives=(Revive(7_000, "HUMAN_A"),),
    )

    result = analyze_captures([capture], gate_matcher=None)

    assert result["population"]["eligible_human_player_rounds"] == 1
    assert result["exclusions"]["human_player_rounds"] == {"overlapping_lives": 1}
    assert result["trajectory_gap"]["eligible_player_round_ms"] == 10_000


def test_capture_without_exact_round_end_is_excluded(tmp_path):
    capture = _capture(
        tmp_path,
        tracks=(_track("HUMAN_A", 0, 9_000, "killed"),),
    )

    result = analyze_captures([capture], gate_matcher=None)

    assert result["input"]["files_included"] == 0
    assert result["exclusions"]["captures"] == {"missing_or_inconsistent_exact_round_end": 1}


def test_round_gate_requires_one_exact_identity_and_quality_pass():
    valid = RoundGate(1, IDENTITY, True, False, "completed")
    matcher = RoundGateMatcher([valid])
    assert matcher.classify(IDENTITY) == ("matched_start_and_end", valid)

    rejected = RoundGate(
        2,
        RoundIdentity("supply", 2, 1_800_000_000, 1_800_000_010),
        False,
        False,
        "completed",
    )
    rejected_matcher = RoundGateMatcher([rejected])
    assert rejected_matcher.classify(rejected.identity) == (
        "rejected_by_round_quality_gate",
        rejected,
    )

    ambiguous_matcher = RoundGateMatcher(
        [
            valid,
            RoundGate(
                3,
                RoundIdentity("supply", 1, IDENTITY.round_start_unix, 1_900_000_010),
                True,
                False,
                "completed",
            ),
        ]
    )
    assert ambiguous_matcher.classify(IDENTITY) == (
        "ambiguous_exact_identity",
        None,
    )


def test_two_raw_identities_for_same_canonical_round_are_both_excluded(tmp_path):
    first = _capture(
        tmp_path,
        identity=IDENTITY,
        tracks=(_track("HUMAN_A", 0, 10_000, "round_end"),),
    )
    disagreeing_end = RoundIdentity(
        IDENTITY.map_name,
        IDENTITY.round_number,
        IDENTITY.round_start_unix,
        IDENTITY.round_end_unix + 1,
    )
    second = _capture(
        tmp_path,
        identity=disagreeing_end,
        tracks=(_track("HUMAN_A", 0, 10_000, "round_end"),),
    )
    gate = RoundGate(1, IDENTITY, True, False, "completed")

    result = analyze_captures(
        [first, second],
        gate_matcher=RoundGateMatcher([gate]),
    )

    assert result["input"]["files_included"] == 0
    assert result["exclusions"]["captures"] == {"duplicate_canonical_round": 2}


def test_v4_capture_is_excluded_as_revive_capability_unproven(tmp_path):
    capture = _capture(
        tmp_path,
        tracks=(_track("HUMAN_A", 0, 10_000, "round_end"),),
    )
    capture = RawCapture(
        capture.path,
        capture.identity,
        4,
        capture.tracks,
        capture.revives,
        capture.revived_outcomes,
    )

    result = analyze_captures([capture], gate_matcher=None)

    assert result["input"]["files_included"] == 0
    assert result["exclusions"]["captures"] == {"revive_capability_not_proven": 1}


def test_parser_reads_only_measurement_sections(tmp_path):
    path = tmp_path / "round_engagements.txt"
    path.write_text(
        "\n".join(
            [
                "# PROXIMITY_TRACKER_V6",
                "# map=Supply",
                "# round=1",
                "# round_start_unix=1700000000",
                "# round_end_unix=1700000010",
                "# PLAYER_TRACKS",
                "# guid;name;team;class;spawn_time;death_time;first_move_time;death_type;samples;path",
                "HUMAN_A;name;AXIS;MEDIC;0;2000;100;killed;1;0,0,0,0,100,0,1,0,0,spawn",
                "HUMAN_A;name;AXIS;MEDIC;8000;10000;8100;round_end;1;8000,0,0,0,100,0,1,0,0,spawn",
                "# REVIVES",
                "# time;medic_guid;medic_name;revived_guid;revived_name;x;y;z;distance;enemy;under_fire",
                "3000;MEDIC;medic;HUMAN_A;name;1;2;3;4;;0",
                "# KILL_OUTCOME",
                "# fields",
                "2000;HUMAN_A;name;KILLER;killer;1;revived;3000;1000;1000;;;;",
                "",
            ]
        ),
        encoding="utf-8",
    )

    capture = parse_capture(path)

    assert capture.identity == IDENTITY
    assert capture.tracker_version == 6
    assert len(capture.tracks) == 2
    assert capture.revives == (Revive(3_000, "HUMAN_A"),)
    assert capture.revived_outcomes == (RevivedOutcome(3_000, "HUMAN_A"),)


def test_parser_keeps_death_type_when_nine_field_row_omits_path(tmp_path):
    path = tmp_path / "round_engagements.txt"
    path.write_text(
        "\n".join(
            [
                "# PROXIMITY_TRACKER_V6",
                "# map=supply",
                "# round=1",
                "# round_start_unix=1700000000",
                "# round_end_unix=1700000010",
                "# PLAYER_TRACKS",
                "HUMAN_A;name;AXIS;MEDIC;0;10000;100;round_end;50",
                "",
            ]
        ),
        encoding="utf-8",
    )

    capture = parse_capture(path)

    assert capture.tracks[0].death_type == "round_end"
    assert capture.exact_round_end_ms == 10_000


def test_revive_subset_cross_check_is_round_scoped(tmp_path):
    first = _capture(
        tmp_path,
        identity=IDENTITY,
        tracks=(
            _track("HUMAN_A", 0, 2_000, "killed"),
            _track("HUMAN_A", 8_000, 10_000, "round_end"),
        ),
        revives=(Revive(3_000, "HUMAN_A"),),
    )
    second_identity = RoundIdentity("supply", 2, 1_700_000_020, 1_700_000_030)
    second = _capture(
        tmp_path,
        identity=second_identity,
        tracks=(
            _track("HUMAN_A", 0, 2_000, "killed"),
            _track("HUMAN_A", 8_000, 10_000, "round_end"),
        ),
        outcomes=(RevivedOutcome(3_000, "HUMAN_A"),),
    )

    result = analyze_captures([first, second], gate_matcher=None)

    assert result["revive_cross_check"]["matched_enemy_kill_subset"] == 0
    assert result["revive_cross_check"]["enemy_kill_subset_without_callback"] == 1


def test_parse_exclusions_are_reflected_in_file_totals():
    result = analyze_captures(
        [],
        gate_matcher=None,
        files_seen=2,
        parse_exclusions=Counter({"parse_or_identity_error": 2}),
    )

    assert result["input"]["files_seen"] == 2
    assert result["input"]["files_parsed"] == 0
    assert result["input"]["files_excluded"] == 2
