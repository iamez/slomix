"""⛔ ELEVEN ENDPOINTS SAID `"status": "ok"` WHILE THE DATABASE WAS DOWN.

Not silence — a claim. `_table_column_exists()` returned `False` on any
exception, every caller read `False` as "the telemetry table is not deployed
yet", and each answered `{"status": "ok", ...empty}`. That is byte-identical to
a deployed-but-unpopulated table, and it is worse than an empty body:
`website/frontend/src/app/lib/responseStatus.ts` classifies `ok` as SUCCESS, so
the page renders "nothing happened tonight" over an outage with full confidence.

One helper, eleven handlers. The fix is three states where there were two, and
the tests below are three states as well — because a fix that answered
`unavailable` for a genuinely undeployed column would just be a different lie.

⚠️ The failing stub must RAISE. `tests/integration/test_api_response_contracts.py`
and `test_typed_endpoints_survive_short_shapes.py` both drive an EMPTY stub, and
an empty database is exactly what a swallowing handler imitates — which is why
neither of them ever saw this.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from website.backend.dependencies import get_db
from website.backend.routers import (
    proximity_objectives,
    proximity_positions,
    proximity_support,
    proximity_teamplay,
)

MODULES = (proximity_objectives, proximity_positions, proximity_support,
           proximity_teamplay)

# The eleven that stood behind the deployment probe.
GATED_PATHS = [
    "/api/proximity/carrier-events",
    "/api/proximity/carrier-kills",
    "/api/proximity/carrier-returns",
    "/api/proximity/vehicle-progress",
    "/api/proximity/escort-credits",
    "/api/proximity/construction-events",
    "/api/proximity/objective-runs",
    "/api/proximity/objective-focus",
    "/api/proximity/combat-position-stats",
    "/api/proximity/support-summary",
    "/api/proximity/focus-fire",
]


class _Broken:
    """Every call raises. This is an OUTAGE, not an empty database."""
    async def fetch_all(self, *a, **k): raise RuntimeError("database is down")
    async def fetch_one(self, *a, **k): raise RuntimeError("database is down")
    async def fetch_val(self, *a, **k): raise RuntimeError("database is down")
    async def execute(self, *a, **k): raise RuntimeError("database is down")


class _NotDeployed:
    """The database answers; the column genuinely is not there."""
    async def fetch_all(self, *a, **k): return []
    async def fetch_one(self, *a, **k): return None
    async def fetch_val(self, *a, **k): return False
    async def execute(self, *a, **k): return None


class _DeployedButEmpty:
    """The column is there and nothing has been recorded into it yet."""
    async def fetch_all(self, *a, **k): return []
    async def fetch_one(self, *a, **k): return None
    async def fetch_val(self, *a, **k): return True
    async def execute(self, *a, **k): return None


def _client(stub) -> TestClient:
    app = FastAPI()
    for module in MODULES:
        app.include_router(module.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: stub()
    return TestClient(app, raise_server_exceptions=False)


def _status(client: TestClient, path: str):
    r = client.get(path)
    try:
        return r.status_code, r.json().get("status")
    except Exception:
        return r.status_code, None


@pytest.mark.parametrize("path", GATED_PATHS)
def test_an_outage_is_never_reported_as_ok(path):
    code, status = _status(_client(_Broken), path)
    assert status != "ok", (
        f"{path} answered {code} with status 'ok' while every database call "
        f"raised. The page cannot tell that from a quiet night.")
    assert status == "unavailable", (
        f"{path} answered status={status!r}; the vocabulary for a failure the "
        f"frontend already renders is 'unavailable' "
        f"(responseStatus.ts FAILURE_STATUSES). A new spelling would need "
        f"classifying on both sides of the language boundary to say what this "
        f"one already says.")


@pytest.mark.parametrize("path", GATED_PATHS)
def test_an_outage_says_WHY(path):
    body = _client(_Broken).get(path).json()
    assert body.get("reason"), f"{path} says 'unavailable' without saying why"
    assert "deployed" in body["reason"]


@pytest.mark.parametrize("stub,label", [(_NotDeployed, "column absent"),
                                        (_DeployedButEmpty, "column present, no rows")])
@pytest.mark.parametrize("path", GATED_PATHS)
def test_a_working_database_with_nothing_in_it_still_answers_ok(path, stub, label):
    """⛔ THE CONTROL, AND IT IS HALF THE FIX.

    Without it, a change that answered 'unavailable' whenever the answer was
    empty would pass every assertion above while replacing one false claim with
    another — and this one would put a failure banner over every feature that
    simply has no data yet.
    """
    code, status = _status(_client(stub), path)
    assert status == "ok", (
        f"{path} answered {status!r} with a working database ({label}); an "
        f"empty answer is not a failure")


def test_the_probe_itself_reports_three_states_not_two():
    """The root cause, at the root. `False` and `None` must not be the same
    answer, because 'not deployed' and 'could not ask' are not the same fact."""
    import asyncio

    from website.backend.routers.proximity_helpers import _table_column_exists

    assert asyncio.run(_table_column_exists(_Broken(), "t", "c")) is None
    assert asyncio.run(_table_column_exists(_NotDeployed(), "t", "c")) is False
    assert asyncio.run(_table_column_exists(_DeployedButEmpty(), "t", "c")) is True


class TestTheSeasonEndpointsSayWhenTheyCouldNotMeasure:
    """⛔ TWO ENDPOINTS WITH NO FAILURE FIELD OF ANY KIND.

    `/api/seasons/current/summary` ran every query through a helper that
    swallowed its exception and returned 0, so a dead database produced a
    complete, plausible season of zeros. `/api/seasons/current/leaders` ran
    thirteen lookups that each returned None on failure — and a `null` leader is
    exactly what a category with no data looks like.

    ⚠️ The leaders endpoint also logged at DEBUG, so a production outage there
    left no trace at all: thirteen nulls in the response and nothing in the log.
    """

    PATHS = ("/api/seasons/current/summary", "/api/seasons/current/leaders")

    def _body(self, stub, path):
        from website.backend.routers import records_seasons
        app = FastAPI()
        app.include_router(records_seasons.router, prefix="/api")
        app.dependency_overrides[get_db] = lambda: stub()
        return TestClient(app, raise_server_exceptions=False).get(path).json()

    @pytest.mark.parametrize("path", PATHS)
    def test_an_outage_is_partial_and_names_what_it_lost(self, path):
        body = self._body(_Broken, path)
        assert body.get("status") == "partial", (
            f"{path} reported status={body.get('status')!r} with every query "
            f"raising")
        assert body.get("failed_metrics"), f"{path} did not name what failed"
        assert "not zero" in (body.get("note") or "") or \
               "not empty" in (body.get("note") or "")

    @pytest.mark.parametrize("path", PATHS)
    def test_a_quiet_season_is_still_ok(self, path):
        """CONTROL. Zeros are an ordinary season total; a working database that
        has nothing to report is not a failure, and marking it as one would put
        a banner over every new quarter."""
        body = self._body(_DeployedButEmpty, path)
        assert body.get("status") == "ok", (
            f"{path} reported {body.get('status')!r} on an empty-but-working "
            f"database")
        assert body.get("failed_metrics") == []

    def test_the_leaders_count_is_not_collapsed_by_a_shared_label(self):
        """⚠️ FOUND BY READING THE OUTPUT, NOT BY THE ASSERTION PASSING.

        The first version recorded the DATE COLUMN each lookup used. All
        thirteen use `round_date`, so a total outage deduplicated to one entry
        and the note said "1 leader queries failed" — an undercount that reads
        as a single missing category. The label has to name the thing the reader
        cares about, which is the category.
        """
        body = self._body(_Broken, "/api/seasons/current/leaders")
        assert len(body["failed_metrics"]) > 5, body["failed_metrics"]
        assert "round_date" not in body["failed_metrics"]


class _SqliteLike:
    """A healthy SQLite adapter: it has a `db_path`, and it raises on the
    PostgreSQL catalogue query the way `SQLiteAdapter.fetch_val` does."""
    db_path = "/tmp/dev.sqlite3"

    def __init__(self, columns=("attacker_guid",)):
        self._columns = columns

    async def fetch_all(self, query, params=None):
        if "PRAGMA table_info" in query:
            return [(0, c, "TEXT", 0, None, 0) for c in self._columns]
        return []

    async def fetch_one(self, *a, **k): return None

    async def fetch_val(self, query, params=None):
        if "information_schema" in query:
            raise RuntimeError('no such table: information_schema.columns')
        return 0


class TestAnUnsupportedCatalogueIsNotAnOutage:
    """⛔ THE DIALECT IS NOT THE SERVER.

    `information_schema` does not exist in SQLite, so the probe raised on EVERY
    call in the supported local development configuration. Once an exception
    started meaning "the database did not answer", all eleven handlers would
    have reported an outage against a perfectly healthy dev database — the fix
    for one false claim manufacturing another. Codex on #862.
    """

    def _probe(self, db, table="proximity_combat_position", column="attacker_guid"):
        import asyncio

        from website.backend.routers.proximity_helpers import _table_column_exists
        return asyncio.run(_table_column_exists(db, table, column))

    def test_sqlite_answers_the_question_instead_of_failing_it(self):
        assert self._probe(_SqliteLike()) is True

    def test_sqlite_can_still_say_the_column_is_absent(self):
        # CONTROL: a dialect-aware probe that always said True would be useless.
        assert self._probe(_SqliteLike(columns=("something_else",))) is False

    def test_a_real_sqlite_outage_is_still_an_outage(self):
        class _Down(_SqliteLike):
            async def fetch_all(self, *a, **k):
                raise RuntimeError("database is locked")
        assert self._probe(_Down()) is None

    def test_postgres_is_untouched(self):
        # CONTROL: the branch must not capture the adapter that has no db_path.
        assert self._probe(_Broken()) is None
        assert self._probe(_DeployedButEmpty()) is True

    def test_a_table_name_that_is_not_an_identifier_is_refused(self):
        """The PRAGMA path interpolates, because SQLite accepts no parameter
        there. Every caller passes a literal, and this is what keeps it so."""
        import pytest as _pytest
        with _pytest.raises(ValueError):
            self._probe(_SqliteLike(), table="rounds; DROP TABLE rounds")


class TestTheHelperCannotBeTalkedOutOfItsOwnStatus:
    def test_a_payload_key_cannot_overwrite_the_status(self):
        from website.backend.routers.proximity_helpers import _probe_unavailable
        out = _probe_unavailable("t", "c", status="ok", reason="nothing wrong", rows=[])
        assert out["status"] == "unavailable"
        assert "did not answer" in out["reason"]
        assert out["rows"] == []


class TestTheDashboardCountsAnUnavailableSectionAsFailed:
    """An outage across all six objective probes was still reported as
    `sections_ok: 6, sections_error: 0` — the aggregate being the last place
    still claiming the page was fine."""

    def test_the_classification_rule_itself(self):
        # The rule as the aggregator now spells it, pinned against drift.
        import inspect

        from website.backend.routers import proximity_dashboard as pd
        src = inspect.getsource(pd.get_proximity_dashboard)
        src = "\n".join(ln.split("#")[0] for ln in src.splitlines())
        assert '("error", "unavailable")' in src, (
            "the dashboard aggregator no longer counts `unavailable` as a "
            "failed section, so an outage reports sections_ok")
        # ⚠️ CONTROL FOR THE READER ITSELF. A source guard that greps a file is
        # one comment away from agreeing with the prose that explains the code,
        # so this proves the stripper removed comments and that the phrase is
        # being read from executable text.
        assert "#" not in src
        assert "Codex on #862" not in src


class TestAFailureMarkerMustNameTheThingAndDisappearWhenRecovered:
    """⛔ TWO WAYS `failed_metrics` LIED, BOTH IN MY OWN FIELD.

    It exists so a consumer can suppress exactly the values that are missing.
    That only works if the name is the CATEGORY and the list is what is still
    failing after every retry. Codex on #862.

    ⚠️ The fixtures below match on query text, and my first attempt matched on
    text that is NOT in the query — `rounds_played` where the session query says
    `round_count`. The test passed, on an empty `failed_metrics`, asserting
    nothing. So each fixture here first proves it reached the branch.
    """

    def _leaders(self, stub):
        from website.backend.routers import records_seasons
        app = FastAPI()
        app.include_router(records_seasons.router, prefix="/api")
        app.dependency_overrides[get_db] = lambda: stub()
        return TestClient(app, raise_server_exceptions=False).get(
            "/api/seasons/current/leaders").json()

    class _Base:
        async def fetch_all(self, *a, **k): return []
        async def fetch_val(self, *a, **k): return 0
        async def fetch_one(self, query, params=None):
            if "GROUP BY gaming_session_id" in query:
                return (7, 12, "2026-08-01")          # session row: id, count, date
            return ("AAAA1111", "alpha", 42)          # leader row: guid, name, value

    def test_a_longest_session_failure_is_named_not_called_unknown(self):
        class _SessionFails(self._Base):
            async def fetch_one(self, query, params=None):
                if "GROUP BY gaming_session_id" in query:
                    raise RuntimeError("column does not exist")
                return await super().fetch_one(query, params)
        body = self._leaders(_SessionFails)
        assert body["status"] == "partial", "fixture never reached the failure"
        assert "unknown" not in body["failed_metrics"], (
            "a failed leader was recorded as 'unknown', so the response says "
            "partial and refuses to say WHICH category is gone")
        assert "longest_session" in body["failed_metrics"], body["failed_metrics"]

    def test_a_recovered_fallback_leaves_no_marker_behind(self):
        """⛔ The response carried usable data AND told every consumer to
        suppress it. A recovered value is not a failure."""
        class _PrimaryFails(self._Base):
            async def fetch_one(self, query, params=None):
                if "LEAST(COALESCE(time_dead_minutes" in query and "time_alive_seconds" in query:
                    raise RuntimeError("column does not exist")
                return await super().fetch_one(query, params)
        body = self._leaders(_PrimaryFails)
        assert body["leaders"]["time_alive"] is not None, "fixture no longer recovers"
        assert "time_alive" not in body["failed_metrics"], (
            f"a recovered category is still listed as failed: "
            f"{body['failed_metrics']}")

    def test_recovering_one_category_does_not_forget_the_others(self):
        """⛔ FOUND BY A SURVIVING MUTATION: `leader_failures.clear()` passed
        every test above, because none of them had TWO failures at once.

        `time_alive` recovers through its fallback while `dpm` stays broken.
        Forgetting the whole list would then hide a category that really is
        missing — trading a false "unavailable" for a false "here it is", which
        is the worse direction."""
        class _OneRecoversOneDoesNot(self._Base):
            async def fetch_one(self, query, params=None):
                if "LEAST(COALESCE(time_dead_minutes" in query and "time_alive_seconds" in query:
                    raise RuntimeError("column does not exist")
                if "damage_given" in query and "time_played_seconds" in query:
                    raise RuntimeError("dpm is broken")
                return await super().fetch_one(query, params)
        body = self._leaders(_OneRecoversOneDoesNot)
        assert body["leaders"]["time_alive"] is not None, "fixture no longer recovers"
        assert "time_alive" not in body["failed_metrics"]
        assert body["failed_metrics"], (
            "recovering one category emptied the whole list, so a category that "
            "is genuinely missing is now reported as fine")

    def test_a_category_that_never_recovers_is_still_named(self):
        """CONTROL: forgetting too eagerly would empty the list and take the
        whole feature with it."""
        class _EverythingFails(self._Base):
            async def fetch_one(self, *a, **k):
                raise RuntimeError("database is down")
        body = self._leaders(_EverythingFails)
        assert body["status"] == "partial"
        assert "time_alive" in body["failed_metrics"], body["failed_metrics"]
