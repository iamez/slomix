"""⛔ /proximity/duos DECLARED `player_guid` AND READ NOTHING.

The parameter appeared exactly once in the handler — in its own signature. A
caller asking about one player got the whole board back with a 200, which is
the same silence that showed 1,873 revives for a round that had 90 on
`/proximity/revives` (a 12x error, live, until somebody looked).

The class guard is `test_declared_parameters_are_used.py`. This file is the
behaviour: that the filter selects the right pairs, in GUID space, and that the
limit is applied after it rather than before.
"""

from __future__ import annotations

import json

from website.backend.routers.proximity_helpers import _compute_scoped_duos

A, B, C = "AAAA1111", "BBBB2222", "CCCC3333"
NAMES = {A: "alpha", B: "bravo", C: "charlie"}


def _row(guids, outcome="killed", delay=100):
    attackers = [{"guid": g, "name": NAMES[g]} for g in guids]
    return (json.dumps(attackers), json.dumps(list(guids)), delay, outcome)


def _pairs(duos):
    return {tuple(sorted((d["player1"], d["player2"])))for d in duos}


class TestTheFilterSelects:
    ROWS = [_row([A, B]), _row([A, B]), _row([B, C]), _row([A, C])]

    def test_unfiltered_shows_every_pair(self):
        # CONTROL: without this, a filter that returns nothing would look right.
        assert _pairs(_compute_scoped_duos(self.ROWS, 10, guid_name_map=NAMES)) == {
            ("alpha", "bravo"), ("bravo", "charlie"), ("alpha", "charlie")}

    def test_asking_about_one_player_returns_only_that_players_pairs(self):
        duos = _compute_scoped_duos(self.ROWS, 10, guid_name_map=NAMES, player_guid=A)
        assert _pairs(duos) == {("alpha", "bravo"), ("alpha", "charlie")}

    def test_a_player_who_never_appears_gets_nothing_not_everything(self):
        # ⛔ The failure being fixed: an unread parameter answers with the whole
        # board. An empty answer is the honest one here.
        duos = _compute_scoped_duos(self.ROWS, 10, guid_name_map=NAMES,
                                    player_guid="DDDD4444")
        assert duos == []

    def test_a_blank_guid_is_not_a_filter(self):
        assert _pairs(_compute_scoped_duos(self.ROWS, 10, guid_name_map=NAMES,
                                           player_guid="  ")) == _pairs(
            _compute_scoped_duos(self.ROWS, 10, guid_name_map=NAMES))

    def test_the_counts_are_the_filtered_ones(self):
        duos = _compute_scoped_duos(self.ROWS, 10, guid_name_map=NAMES, player_guid=A)
        by_pair = {tuple(sorted((d["player1"], d["player2"]))): d for d in duos}
        assert by_pair[("alpha", "bravo")]["crossfire_count"] == 2
        assert by_pair[("alpha", "charlie")]["crossfire_count"] == 1


class TestAThreePlayerEngagementIsWhereTwOFiltersDiffer:
    """⛔ FOUND BY MUTATION, NOT BY READING.

    Deleting the pair-level filter left the whole suite green, because every
    fixture above was a two-player engagement — there, dropping engagements the
    player is not in already answers the question. The filters only diverge when
    an engagement has three participants: it survives the engagement test
    because the player IS in it, and it then contributes the pair of the OTHER
    two, who were never asked about.

    A fixture that cannot reach a branch does not test it, and a mutation is how
    that gets noticed.
    """

    ROWS = [_row([A, B, C])]

    def test_the_pair_of_the_other_two_is_not_reported(self):
        duos = _compute_scoped_duos(self.ROWS, 10, guid_name_map=NAMES, player_guid=A)
        assert ("bravo", "charlie") not in _pairs(duos)
        assert _pairs(duos) == {("alpha", "bravo"), ("alpha", "charlie")}

    def test_unfiltered_it_still_reports_all_three(self):
        # CONTROL: the pair filter must not be a blanket suppression.
        assert _pairs(_compute_scoped_duos(self.ROWS, 10, guid_name_map=NAMES)) == {
            ("alpha", "bravo"), ("alpha", "charlie"), ("bravo", "charlie")}


class TestTheLimitIsAppliedAfterTheFilter:
    """⛔ Order matters, and getting it wrong is invisible in a green suite.

    Slice first and the answer is "the top N pairs of everyone, minus the ones
    that were not about you" — which is usually empty, and looks exactly like a
    player who never played with anybody.
    """

    def test_a_busy_board_still_answers_about_the_quiet_player(self):
        rows = [_row([B, C]) for _ in range(30)] + [_row([A, B])]
        duos = _compute_scoped_duos(rows, 1, guid_name_map=NAMES, player_guid=A)
        assert _pairs(duos) == {("alpha", "bravo")}
