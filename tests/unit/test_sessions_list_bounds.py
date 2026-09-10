"""Regression: `/api/sessions?limit=-5` and `?offset=-10` were live 500s.

Neither parameter carried bounds, the values went straight into the query,
Postgres refused the negative ones, and the failure came back as a server
fault — an input error reported as ours, which sends whoever reads it to the
database instead of to the request. Measured on dev before the fix:

    ?limit=-5      500        ?offset=-10     500
    ?limit=0       200        ?limit=1000000  200

Same shape as `/api/predictions/recent`, and this one is on the endpoint the
NEW SPA lists sessions from — `useSessions` in `queries.ts`, used by Landing,
Home, RoundsPage, SessionDetail, SmartStatsDiag and SessionsList.

⭐ The ceiling is generous rather than tight, and the reason is measured, not
guessed. `SessionsList.tsx` opens with `limit=200` and raises it by 200 per
"show older" click, so a ceiling near today's data would turn that button into
a 422. Cost is not the constraint either: limit=200, 500 and 1000 all return
the same 54,526 bytes in ~3 ms, because the query runs out of sessions (137)
long before it runs out of limit.
"""

import inspect
import warnings

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

warnings.filterwarnings("ignore")

from website.backend import dependencies as deps  # noqa: E402
from website.backend.routers import sessions_router  # noqa: E402

# What the new SPA actually sends, read off the call sites rather than assumed:
# Landing 6, Home 6, RoundsPage 30, SessionDetail 30, SmartStatsDiag 1, and
# SessionsList's PAGE of 200. Legacy `home.js` sends 1.
LIVE_CALLER_LIMITS = [1, 6, 30, 200]


class _RecordingDb:
    """A database that records whether it was consulted at all."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def fetch_all(self, query, params=None):
        self.calls.append((query, params))
        return []

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


@pytest.mark.parametrize("query", ["limit=-5", "limit=0", "limit=1000001", "offset=-1", "offset=-10"])
def test_a_value_the_query_cannot_use_is_refused_as_a_bad_request(client_and_db, query):
    client, db = client_and_db
    response = client.get(f"/api/sessions?{query}")
    assert response.status_code == 422, (
        f"?{query} answered {response.status_code}; a value the query cannot "
        "use must be a bad request, not a server fault"
    )
    assert db.calls == [], (
        f"?{query} reached the database — the bound is being checked inside "
        "the handler, where the next blanket `except` will hide it again"
    )


@pytest.mark.parametrize("limit", LIVE_CALLER_LIMITS)
def test_every_limit_a_caller_actually_sends_still_works(client_and_db, limit):
    client, db = client_and_db
    response = client.get(f"/api/sessions?limit={limit}")
    assert response.status_code == 200, response.text
    assert len(db.calls) >= 1, "the handler stopped querying"


def test_the_bounds_live_on_the_parameters_not_in_the_body():
    """⛔ THE PART A STATUS CODE CANNOT PROVE.

    A range check written inside the handler returns 422 too and would pass
    every assertion above — until someone widens an `except` above it.
    Reading the signature is the only way to tell the two apart, and the
    constraints are read off the OBJECT: FastAPI keeps them in `metadata` as
    `[Ge(...), Le(...)]`, not as attributes.
    """
    signature = inspect.signature(sessions_router.get_sessions_list)

    limit = signature.parameters["limit"].default
    limit_constraints = {type(c).__name__: c for c in getattr(limit, "metadata", [])}
    assert "Ge" in limit_constraints and limit_constraints["Ge"].ge == 1
    assert "Le" in limit_constraints, "limit has no ceiling at all"

    offset = signature.parameters["offset"].default
    offset_constraints = {type(c).__name__: c for c in getattr(offset, "metadata", [])}
    assert "Ge" in offset_constraints and offset_constraints["Ge"].ge == 0, (
        "offset can still go negative, which is the other half of the 500"
    )


def test_the_ceiling_clears_the_page_that_grows_its_limit():
    """⛔ The cross-language half, and the one a status code cannot reach.

    `SessionsList.tsx` does not paginate with `offset`; it raises `limit` by
    PAGE on every "show older" click. A ceiling below that first request would
    make the page 422 on load, and nothing in the Python tests would notice —
    the constant lives in TypeScript.
    """
    import re
    from pathlib import Path

    page_source = (
        Path(__file__).resolve().parents[2] / "website" / "frontend" / "src" / "app" / "pages" / "SessionsList.tsx"
    ).read_text()
    # Anchored on the declaration, not searched for anywhere in the file: the
    # comments in that file mention paging, and prose must not satisfy this.
    match = re.search(r"^const PAGE = (\d+);", page_source, re.M)
    assert match, "PAGE is no longer a top-level const in SessionsList.tsx"
    page = int(match.group(1))

    signature = inspect.signature(sessions_router.get_sessions_list)
    limit = signature.parameters["limit"].default
    ceiling = {type(c).__name__: c for c in limit.metadata}["Le"].le

    assert page <= ceiling, (
        f"SessionsList opens with limit={page} and the endpoint refuses "
        f"anything over {ceiling} — the page would 422 on first load"
    )
    assert ceiling >= page * 2, (
        f"the ceiling ({ceiling}) leaves no room for even one 'show older' "
        f"click at PAGE={page}; either raise it or page with offset instead "
        "of a growing limit"
    )
