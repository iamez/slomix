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


class TestTheTwoGuidLengthsAreTheSamePlayer:
    """⛔ MY FIX RETURNED NOTHING FOR EVERY VALID REQUEST.

    Measured on the live database: `player_comprehensive_stats.player_guid` is
    8 characters on 19,845 rows and 32 on 929, while `combat_engagement`
    participants are stored as the 32-character form. Of 32 distinct long GUIDs
    sampled, 28 have their 8-character prefix present in `pcs` and ZERO match a
    full 32-character `pcs` guid.

    So the site hands out the short form and this table holds the long one. A
    raw string comparison never matches, and the filter I added turned "the
    whole board" (the old bug) into "this player never played with anybody" — a
    different wrong answer, and a more convincing one. Codex on #860.

    ⭐ `_resolve_name_for_guid` had already solved this, eight lines away. The
    membership test had not: a helper that knows something its own caller does
    not is where this kind of bug lives.
    """

    LONG_A = "AAAA1111" + "0" * 24
    LONG_B = "BBBB2222" + "0" * 24

    def _rows(self):
        att = [{"guid": self.LONG_A, "name": "alpha"},
               {"guid": self.LONG_B, "name": "bravo"}]
        return [(json.dumps(att), json.dumps([self.LONG_A, self.LONG_B]), 100, "killed")]

    def test_the_short_form_the_site_hands_out_matches(self):
        duos = _compute_scoped_duos(self._rows(), 10, guid_name_map=NAMES,
                                    player_guid="AAAA1111")
        assert _pairs(duos) == {("alpha", "bravo")}

    def test_the_long_form_still_matches(self):
        # CONTROL: canonicalising must not break the form that already worked.
        duos = _compute_scoped_duos(self._rows(), 10, guid_name_map=NAMES,
                                    player_guid=self.LONG_A)
        assert _pairs(duos) == {("alpha", "bravo")}

    def test_case_does_not_decide_identity(self):
        duos = _compute_scoped_duos(self._rows(), 10, guid_name_map=NAMES,
                                    player_guid="aaaa1111")
        assert _pairs(duos) == {("alpha", "bravo")}

    def test_a_different_player_still_gets_nothing(self):
        # CONTROL: prefix matching must not become matching everything.
        duos = _compute_scoped_duos(self._rows(), 10, guid_name_map=NAMES,
                                    player_guid="DDDD4444")
        assert duos == []


class TestAThreePlayerEngagementIsWhereTwoFiltersDiffer:
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


class TestTheFilterReachesTheQueryNotOnlyThePythonAfterIt:
    """⛔ THE ROW CAP IS 5,000 AND THE TABLE HAS 17,424 CROSSFIRE ROWS.

    Measured on the live database. Filtering only in Python means a player whose
    engagements fall outside the newest 5,000 answers "no duos" on a busy scope —
    the same class as applying a LIMIT before a filter, one layer further out.
    With the narrowing in the query, that player's rows come back as 1,297.

    The narrowing is deliberately LOOSE — a substring match on the JSON text —
    because `_compute_scoped_duos` still decides exactly. A false positive costs
    one row that is then rejected; a false negative would be another silently
    empty answer. Measured: 0 false positives on that sample anyway.

    Codex on #860.
    """

    @staticmethod
    def _capture():
        seen = {}

        class _Db:
            async def fetch_all(self, query, params=None):
                seen.setdefault("queries", []).append((query, params))
                return []
            async def fetch_one(self, *a, **k): return None
            async def fetch_val(self, *a, **k): return 0

        return seen, _Db

    def _call(self, player_guid):
        import asyncio

        from website.backend.routers.proximity_combat import get_proximity_duos
        seen, Db = self._capture()
        payload = asyncio.run(get_proximity_duos(player_guid=player_guid, db=Db()))
        return seen, payload

    def test_the_guid_is_bound_into_the_engagement_query(self):
        seen, _ = self._call("AAAA1111")
        engagement = [q for q in seen["queries"] if "combat_engagement" in q[0]
                      and "crossfire_participants" in q[0]]
        assert engagement, "no engagement query was issued"
        query, params = engagement[-1]
        assert "LIKE" in query.upper(), (
            "the player filter never reached the query; the 5,000-row cap is "
            "applied before it")
        assert any("AAAA1111" in str(p) for p in (params or ())), params

    def test_without_a_guid_the_query_is_left_alone(self):
        # CONTROL: the narrowing must not appear when nobody asked for it.
        seen, _ = self._call(None)
        query = [q for q in seen["queries"] if "combat_engagement" in q[0]][-1][0]
        assert "crossfire_participants) LIKE" not in query.upper().replace(" ", "")

    def test_the_scope_echoes_the_filter_that_was_applied(self):
        """A scope that reports `player_guid: null` while filtering by one is a
        response describing a different request than the one it answered."""
        _, payload = self._call("aaaa1111")
        assert payload["scope"]["player_guid"] == "AAAA1111"

    def test_an_absent_guid_is_reported_absent(self):
        _, payload = self._call(None)
        assert payload["scope"]["player_guid"] is None


class TestTheAttackerFallbackSurvivesTheSqlNarrowing:
    """⛔ THE PRE-FILTER LOOKED AT ONE COLUMN AND THE PYTHON LOOKS AT TWO.

    `_compute_scoped_duos` deliberately falls back to `attackers` when
    `crossfire_participants` is empty, and even searches `guid_to_name` — built
    from attackers — when applying the exact player filter. Narrowing the query
    on participants alone therefore discarded rows the UNFILTERED endpoint can
    still aggregate: a filtered request answering with LESS than the data
    supports, which is the failure the narrowing was added to prevent, inverted.

    ⚠️ Measured: 0 such rows in the live table today. The fallback exists
    because they are expected, so this is latent rather than hypothetical.
    Codex on #860.
    """

    @staticmethod
    def _capture():
        seen = {}

        class _Db:
            async def fetch_all(self, query, params=None):
                seen.setdefault("q", []).append((query, params))
                return []
            async def fetch_one(self, *a, **k): return None
            async def fetch_val(self, *a, **k): return 0

        return seen, _Db

    def test_the_narrowing_accepts_either_column(self):
        import asyncio

        from website.backend.routers.proximity_combat import get_proximity_duos
        seen, Db = self._capture()
        asyncio.run(get_proximity_duos(player_guid="AAAA1111", db=Db()))
        q = [x for x in seen["q"] if "crossfire_participants" in x[0]][-1][0].upper()
        # ⚠️ THE FILTER FRAGMENT, NOT THE WHOLE QUERY. `attackers` is in the
        # SELECT list too, so `"ATTACKERS" in q` was true whether the narrowing
        # mentioned it or not — a guard passing on a different occurrence of the
        # word it was looking for. Found by a mutation that removed the column
        # from the filter and changed nothing.
        i = q.index("AND (UPPER(CAST(CROSSFIRE_PARTICIPANTS")
        fragment = q[i:q.index("ORDER BY", i)]
        assert "ATTACKERS" in fragment, (
            f"the pre-filter reads only one of the two columns the Python "
            f"fallback reads: {fragment}")

    def test_a_row_with_only_attackers_still_produces_its_pair(self):
        """The behaviour the SQL must not cut off, proven in the helper."""
        att = [{"guid": "AAAA1111" + "0" * 24, "name": "alpha"},
               {"guid": "BBBB2222" + "0" * 24, "name": "bravo"}]
        rows = [(json.dumps(att), json.dumps([]), 100, "killed")]
        duos = _compute_scoped_duos(rows, 10, guid_name_map=NAMES,
                                    player_guid="AAAA1111")
        assert _pairs(duos) == {("alpha", "bravo")}
