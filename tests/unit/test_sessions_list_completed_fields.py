"""`/api/sessions` gained the five fields its sibling had, and one shared bug.

Owner's decision, 2026-08-30: `/api/sessions` is the source for session
listings and `/api/stats/sessions` is not retired, so the two have to agree.
Measured across the 100 sessions both return, BEFORE this change: all 13
shared fields agreed exactly, neither was a superset — `/api/sessions` alone
had `draws` (not derivable: `rounds - axis_wins - allies_wins` disagreed on
94 of 100), and `/api/stats/sessions` alone had `duration_seconds`,
`start_time`, `end_time`, `player_names` and `total_deaths`.

⛔ THE BUG THAT ADDING A FIELD UNCOVERED. `/api/stats/sessions` built its
duration as `SUM(lua_round_teams.actual_duration_seconds)` over a LEFT JOIN.
The Lua webhook covers part of the history — 877 of 2030 valid R1/R2 rounds —
and an unmatched LEFT JOIN contributes nothing, so a **partial sum was
reported as a total**. Session 88 has 16 valid rounds of which 10 are
measured, and it answered 5209 s against an actual 7260 s; 46 of 100 sessions
answered **0 seconds**, which is not "unmeasured" on the wire, it is a
duration, and the legacy session card renders it as one.

Copying that into the new endpoint would have created a disagreement between
two endpoints on one field, so both now use `round_duration_sql()` — the
project's canonical expression (CLAUDE.md: take round duration from
`shared/round_time.py`), Lua where it exists and parsed `actual_time` where it
does not, covering 2030 of 2030. Measured after: 0 sessions at zero, 0
disagreements between the two endpoints.
"""

import warnings

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

warnings.filterwarnings("ignore")

from shared.round_time import round_duration_sql  # noqa: E402
from website.backend import dependencies as deps  # noqa: E402
from website.backend.routers import sessions_router  # noqa: E402

# One row in the shape the completed query returns: the original 15 columns
# (through `winning_team`), then the five appended ones.
ROW = (
    "2026-08-27",
    154,
    12,
    4,
    6,
    743,  # date, id, rounds, maps, players, kills
    "supply, te_escape2",
    3,
    3,
    0,  # maps_played, allies, axis, draws
    "Team A",
    "Team B",
    5,
    7,
    2,  # BOX team fields  -> row[10]..row[14]
    743,
    5226,
    # ⛔ A LIST from ARRAY_AGG — and the first name carries ', ' on purpose:
    # under the old STRING_AGG+split contract "kanii, jr" came back as two
    # phantom players. 0 comma names exist today; names are user-controlled,
    # so the contract follows what a name CAN be (Codex on #848).
    ["kanii, jr", "bronze"],  # names
    "20:15:00",
    "22:41:00",  # first_time, last_time
)
NEW_KEYS = {"total_deaths", "duration_seconds", "player_names", "start_time", "end_time"}
OLD_KEYS = {
    "date",
    "session_id",
    "rounds",
    "maps",
    "players",
    "total_kills",
    "maps_played",
    "allies_wins",
    "axis_wins",
    "draws",
    "team_1_name",
    "team_2_name",
    "team_1_score",
    "team_2_score",
    "winning_team",
    "formatted_date",
    "time_ago",
}


class _RecordingDb:
    def __init__(self, rows=(ROW,)) -> None:
        self.calls: list[tuple] = []
        self._rows = list(rows)

    async def fetch_all(self, query, params=None):
        self.calls.append((query, params))
        return list(self._rows)

    async def fetch_one(self, query, params=None):
        self.calls.append((query, params))
        return None


@pytest.fixture()
def client_and_db():
    db = _RecordingDb()
    app = FastAPI()
    app.include_router(sessions_router.router, prefix="/api")
    app.dependency_overrides[deps.get_db] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, db


def test_the_five_fields_are_there_and_the_old_ones_survived(client_and_db):
    client, _ = client_and_db
    body = client.get("/api/sessions?limit=1").json()
    assert body, "no session came back"
    keys = set(body[0])
    assert keys >= NEW_KEYS, f"missing: {sorted(NEW_KEYS - keys)}"
    assert keys >= OLD_KEYS, (
        f"a pre-existing field disappeared: {sorted(OLD_KEYS - keys)} — the "
        "new columns were inserted into the middle of the SELECT and the row "
        "is unpacked BY POSITION"
    )


def test_the_python_side_reads_the_fixture_positions_it_claims(client_and_db):
    """The unpacking half: `row[10]`..`row[14]` are the BOX team fields and
    the five new ones are `row[15]`..`row[19]`.

    ⚠️ THIS TEST ALONE PROVES NOTHING ABOUT THE SQL. It runs against a fixed
    tuple, so it answers the same way whatever order the SELECT lists its
    columns in — a fixture cannot fail on a fact it does not contain, and this
    one passed unchanged against a mutation that moved all five columns back
    into the middle. The column order is checked against the query itself in
    `test_the_new_columns_are_appended_not_inserted`; both halves are needed.
    """
    client, _ = client_and_db
    row = client.get("/api/sessions?limit=1").json()[0]
    assert (row["team_1_name"], row["team_2_name"]) == ("Team A", "Team B")
    assert (row["team_1_score"], row["team_2_score"], row["winning_team"]) == (5, 7, 2)
    assert row["total_deaths"] == 743
    assert row["duration_seconds"] == 5226
    assert row["player_names"] == ["kanii, jr", "bronze"], (
        "a comma inside a name split it into phantom players — the wire must "
        "carry the array through, never a joined string"
    )
    assert (row["start_time"], row["end_time"]) == ("20:15", "22:41")


def test_the_new_columns_are_appended_not_inserted(client_and_db):
    """⛔ THE SPECIFIC WAY THIS CHANGE COULD BREAK EVERYTHING QUIETLY.

    The row is unpacked by position. A column added in the MIDDLE of the
    SELECT renames five existing fields with no error anywhere — the types
    line up, the response still carries every key, and every fixture-based
    test above still passes. Only the query's own column order can say.
    """
    client, db = client_and_db
    client.get("/api/sessions?limit=1")
    query = db.calls[0][0]
    start = query.index("sr.session_date")
    select_body = query[start : query.index("FROM session_rounds sr", start)]

    anchor_at = select_body.index("sb.winning_team")
    for column in (
        "total_deaths",
        "duration_seconds",
        "player_names",
        "sr.first_time",
        "sr.last_time",
    ):
        assert column in select_body, f"{column} left the projection"
        assert select_body.index(column) > anchor_at, (
            f"{column} is listed BEFORE sb.winning_team — the BOX team fields "
            "have shifted and row[10]..row[14] now read something else"
        )


@pytest.mark.parametrize("route", ["/api/sessions", "/api/stats/sessions"])
def test_both_endpoints_take_duration_from_the_canonical_expression(client_and_db, route):
    """⛔ THE ASSERTION THAT KEEPS THE TWO FROM DIVERGING AGAIN.

    ⚠️ Compared against the helper's OWN OUTPUT, not a regex written here: if
    `round_duration_sql` changes, this follows it instead of pinning a stale
    copy. And it is read off the query the handler actually built, not off the
    file — a comment mentioning the helper would satisfy a source scan.
    """
    client, db = client_and_db
    client.get(f"{route}?limit=1")
    assert db.calls, "the handler never queried"
    query = db.calls[0][0]
    assert round_duration_sql("r") in query, f"{route} does not derive duration from shared/round_time.py"
    assert "SUM(lrt.actual_duration_seconds)" not in query, (
        f"{route} is back to summing the Lua table alone, which reports a "
        "partial sum as a total — 46 of 100 sessions answered 0 seconds"
    )


def test_the_search_term_is_bound_and_never_interpolated(client_and_db):
    """The term reaches the database as a parameter, not as SQL text."""
    client, db = client_and_db
    term = "O'Brien%_x"
    client.get(f"/api/sessions?limit=5&search={term}")
    query, params = db.calls[0]
    escaped = term.replace("%", "\\%").replace("_", "\\_")
    # ⚠️ Check BOTH spellings. The raw term never appears in an interpolated
    # query either, because the code escapes BEFORE interpolating — asserting
    # only on the raw form is a guard that cannot fail, which is exactly how
    # the first version of this test passed against the mutation.
    assert term not in query and escaped not in query, "the search term was interpolated into the SQL instead of bound"
    assert "O'Brien" not in query, "part of the term reached the SQL text"
    assert any(escaped in str(p) for p in params), f"the escaped term never reached the parameters: {params}"
    # ⚠️ Escaping both wildcards is the point, and it is measurable: on dev,
    # `search=s_pply` returns 0 sessions and `search=supply` returns 123. An
    # unescaped `_` would make the first match the second.
    assert "\\_" in str(params[-1]) and "\\%" in str(params[-1])


def test_the_search_subqueries_gate_bots_too(client_and_db):
    """:485 (Codex on #848): the CTE gates alone were not enough — a map or
    player found ONLY in a valid bot round still matched the search
    subqueries and returned the session. Counted over the built query: the
    two search subqueries add two more bot gates on top of the CTE gates."""
    client, db = client_and_db
    client.get("/api/sessions?limit=5&search=supply")
    query, _ = db.calls[0]
    assert query.count("is_bot_round IS DISTINCT FROM TRUE") == 4, (
        f"expected 2 CTE + 2 search bot gates, found {query.count('is_bot_round IS DISTINCT FROM TRUE')}"
    )


def test_no_search_means_no_filter(client_and_db):
    client, db = client_and_db
    client.get("/api/sessions?limit=5")
    query, params = db.calls[0]
    assert "$3" not in query, "an empty search still built a filter"
    assert len(params) == 2, f"an empty search still bound a parameter: {params}"


def test_the_checks_above_can_fail(client_and_db):
    """Controls: the fixture must exercise what the assertions claim."""
    assert len(ROW) == 20, "the fixture row no longer matches the SELECT width"
    assert round_duration_sql("r") != "", "the helper returns nothing to look for"
    assert "SUM(lrt.actual_duration_seconds)" not in round_duration_sql("r"), (
        "the two expressions this test distinguishes are the same string"
    )


@pytest.mark.parametrize(
    ("route", "gates"),
    [
        # /api/sessions has TWO rounds-reading CTEs (session_box reads
        # session_results, no rounds join to gate); the sibling has four.
        # Exact counts: a gate added where none is possible is as
        # suspicious as one lost.
        ("/api/sessions", 2),
        ("/api/stats/sessions", 4),
    ],
)
def test_the_time_concat_is_padded_and_the_ctes_gate_bots(client_and_db, route, gates):
    """Two latent-shape guards, both counted over the QUERY THE HANDLER BUILT
    (a fixture cannot fail on a value it does not contain, and today's data
    contains neither an unpadded round_time nor a bot round that passes the
    other gates):

    - LPAD (:535, Codex on #848): round_time is TEXT and MIN/MAX order the
      concatenation lexically, so an unpadded pre-10:00 value like '4918'
      would sort after '063000'. Measured: every round_time is 6 chars today.
    - is_bot_round (:549): the flags answer different questions — measured
      today 0 bot rounds pass the is_valid+status gates, but everywhere else
      (round_set, pcs_where) the two stand together, and these CTEs must not
      be the exception.
    """
    client, db = client_and_db
    client.get(f"{route}?limit=1")
    assert db.calls, "the handler never queried"
    query = db.calls[0][0]
    assert query.count("LPAD(r.round_time, 6, '0')") == 2, (
        f"{route}: expected both time bounds padded, found {query.count(chr(76))} LPADs"
    )
    assert query.count("is_bot_round IS DISTINCT FROM TRUE") == gates, (
        f"{route}: expected {gates} bot gates, found {query.count('is_bot_round IS DISTINCT FROM TRUE')}"
    )
