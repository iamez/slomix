"""Reconciliation rules: report real disagreements, never invent them.

The tolerances here are the ones measured against supa's sheet on 2026-08-14
(kills and durations exact, DPM within a few points), and the "not compared"
path matters as much as the "mismatch" path — a dev tool that cries wolf gets
switched off.
"""
import pytest

from bot.services.supastats_image_reader import ParsedSheet, PlayerRow
from bot.services.supastats_reconcile_service import reconcile


def _sheet(kills, winners, totals=None, dpm=None, r1=None, r2=None, teams=("RED", "BLUE")):
    totals = totals or [sum(v) for v in kills]
    rows = [
        PlayerRow(name=None, team=teams[0] if i < len(kills) // 2 else teams[1],
                  values=v, total=t)
        for i, (v, t) in enumerate(zip(kills, totals))
    ]
    dpm_rows = [
        PlayerRow(name=None, team=r.team, values=d, total=None)
        for r, d in zip(rows, dpm)
    ] if dpm else []
    return ParsedSheet(
        session_date="2026-08-11", map_count=len(kills[0]), winners=winners,
        dpm=dpm_rows, kills=rows, round1_seconds=r1 or [], round2_seconds=r2 or [],
    )


def _call(sheet, **overrides):
    base = dict(
        session_date="2026-08-11",
        gaming_session_id=144,
        our_kills={"alice": [5, 7], "bob": [3, 9]},
        our_dpm={"alice": [300, 310], "bob": [250, 260]},
        our_durations=([340, 388], [229, 145]),
        our_map_winners=["Reds", "Blues"],
        our_teams={"Reds": ["alice"], "Blues": ["bob"]},
    )
    base.update(overrides)
    return reconcile(sheet, **base)


def test_identical_data_reports_nothing():
    sheet = _sheet([[5, 7], [3, 9]], ["RED", "BLUE"], r1=[340, 388], r2=[229, 145])
    report = _call(sheet)
    assert report.ok
    assert report.mismatches == []


def test_kills_difference_is_reported_exactly():
    sheet = _sheet([[5, 7], [3, 8]], ["RED", "BLUE"])   # bob's map 2: 8 vs our 9
    report = _call(sheet)
    assert not report.ok
    assert any("kills" in m and "map 2" in m for m in report.mismatches)


def test_dpm_within_tolerance_is_not_reported():
    """Ours ran a few points under the sheet's on every map — a time-base
    difference, not a data error. Reporting it would bury the real findings."""
    sheet = _sheet([[5, 7], [3, 9]], ["RED", "BLUE"], dpm=[[303, 313], [253, 262]])
    assert _call(sheet).ok


def test_dpm_beyond_tolerance_is_reported():
    sheet = _sheet([[5, 7], [3, 9]], ["RED", "BLUE"], dpm=[[300, 400], [250, 260]])
    report = _call(sheet)
    assert any("DPM" in m for m in report.mismatches)


def test_duration_difference_is_reported():
    sheet = _sheet([[5, 7], [3, 9]], ["RED", "BLUE"], r1=[340, 999], r2=[229, 145])
    report = _call(sheet)
    assert any("R1 duration" in m and "999" in m for m in report.mismatches)


def test_map_winner_difference_is_reported():
    sheet = _sheet([[5, 7], [3, 9]], ["BLUE", "BLUE"])
    report = _call(sheet)
    assert any("map 1 winner" in m for m in report.mismatches)


def test_map_count_difference_stops_the_comparison():
    """Comparing map 3 of one sheet against map 3 of a different night would
    produce nonsense, so a count mismatch is the only finding reported."""
    sheet = _sheet([[5, 7, 1], [3, 9, 2]], ["RED", "BLUE", "RED"])
    report = _call(sheet)
    assert report.mismatches == ["map count: supastats 3, we have 2"]


def test_failed_checksum_blocks_all_comparison():
    """A misread screenshot must never become a discrepancy report."""
    sheet = _sheet([[5, 7], [3, 9]], ["RED", "BLUE"], totals=[99, 99])
    report = _call(sheet)
    assert report.mismatches == []
    assert any("checksum" in u for u in report.unmatched)


def test_unlinkable_player_is_flagged_not_compared():
    sheet = _sheet([[5, 7], [40, 40]], ["RED", "BLUE"])
    report = _call(sheet)
    assert any("could not be linked" in u for u in report.unmatched)


@pytest.mark.parametrize("winners", [["RED", "BLUE"], ["BLUE", "RED"]])
def test_colour_binding_follows_the_linked_players(winners):
    """RED/BLUE carry no meaning on their own — they are bound to our teams
    through the players whose rows we linked, in whichever order the sheet
    happens to use."""
    kills = [[5, 7], [3, 9]]
    sheet = _sheet(kills, winners)
    our_winners = ["Reds" if w == "RED" else "Blues" for w in winners]
    assert _call(sheet, our_map_winners=our_winners).ok


@pytest.mark.asyncio
async def test_load_our_session_survives_mid_session_rename():
    """A player renaming between maps must stay ONE vector (GROUP BY guid
    rule — coderabbit, PR #771). Before the fix the per-(map,guid)
    MAX(player_name) split them into two partial vectors."""
    from bot.services.supastats_reconcile_service import load_our_session

    class _Db:
        async def fetch_all(self, query, params=()):
            if "player_comprehensive_stats" in query:
                # (map_no, guid, name, kills, deaths, damage, seconds)
                return [
                    (1, "AAAA1111", "oldname", 10, 5, 3000, 600),
                    (2, "AAAA1111", "newname-longer", 7, 8, 2100, 600),
                    (1, "BBBB2222", "stable", 4, 6, 1200, 600),
                    (2, "BBBB2222", "stable", 6, 2, 1800, 600),
                ]
            # duration rows — shape follows the query: the base branch
            # selects (map_no, rn, actual_time); after PR #770 lands the
            # query also selects actual_duration_seconds.
            rows = [(1, 1, "5:00", 300), (1, 2, "4:00", 240),
                    (2, 1, "6:00", 360), (2, 2, "3:00", 180)]
            if "actual_duration_seconds" in query:
                return rows
            return [r[:3] for r in rows]

    ours = await load_our_session(_Db(), 42)
    assert ours["kills"] == {"newname-longer": [10, 7], "stable": [4, 6]}
    assert ours["deaths"] == {"newname-longer": [5, 8], "stable": [6, 2]}
