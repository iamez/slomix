"""Regression: `/api/predictions/recent?limit=-5` answered 500.

`limit: int = 5` carried no bounds, the value went straight into `LIMIT ?`,
Postgres rejected it, and the handler's blanket `except Exception` turned the
rejection into `{"detail": "Failed to fetch predictions"}` — a 500. So an
INPUT error was reported as a server fault, which sends whoever reads it
looking at the database instead of at the request. Measured live on dev
2026-08-30, before the fix:

    ?limit=-5   500        ?limit=5   200

⭐ The bound is declared on the parameter rather than checked in the body, and
that placement IS the fix: FastAPI validates before calling the handler, so a
bad value can never reach the `try` that would disguise it. Same shape as the
fix `/proximity/revives` needed — bound and parse ABOVE the exception
handler, never inside it.

The assertions below are about that placement, not only about the status
code: a check written inside the handler would also return 422 and would
still be wrong, because the next blanket `except` to appear would swallow it.
"""
import warnings

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

warnings.filterwarnings("ignore")

from website.backend import dependencies as deps  # noqa: E402
from website.backend.routers import predictions  # noqa: E402


class _RecordingDb:
    """A database that records whether it was consulted at all."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def fetch_all(self, query, params=None):
        self.calls.append((query, params))
        return []


@pytest.fixture()
def client_and_db():
    db = _RecordingDb()
    app = FastAPI()
    app.include_router(predictions.router, prefix="/api/predictions")
    app.dependency_overrides[deps.get_db] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, db


@pytest.mark.parametrize("limit", [-5, -1, 0, 201, 10_000])
def test_an_out_of_range_limit_is_refused_as_a_bad_request(client_and_db, limit):
    client, db = client_and_db
    response = client.get(f"/api/predictions/recent?limit={limit}")
    assert response.status_code == 422, (
        f"limit={limit} answered {response.status_code}; a value the query "
        f"cannot use must be a bad request, not a server fault")
    assert db.calls == [], (
        f"limit={limit} reached the database — the bound is being checked "
        f"inside the handler, so the next blanket `except` will hide it again")


@pytest.mark.parametrize("query", ["", "?limit=1", "?limit=3", "?limit=200"])
def test_every_value_a_caller_actually_sends_still_works(client_and_db, query):
    """Every caller in the tree asks for 3 — `app.js:483`, `probes.ts:35`,
    `diagnostics.js:26` — so the ceiling must not narrow live behaviour."""
    client, db = client_and_db
    response = client.get(f"/api/predictions/recent{query}")
    assert response.status_code == 200
    assert response.json() == []
    assert len(db.calls) == 1, "the handler stopped querying"


def test_the_bound_lives_on_the_parameter_not_in_the_body():
    """⛔ THE PART A STATUS CODE CANNOT PROVE.

    A range check written inside the handler returns 422 too, and would pass
    every assertion above — until someone widens the `except Exception` that
    already sits under it. Reading the signature is the only way to tell the
    two apart.
    """
    import inspect

    signature = inspect.signature(predictions.get_recent_predictions)
    limit = signature.parameters["limit"].default
    # ⚠️ Read off the OBJECT, not guessed: FastAPI's `Query` keeps the bounds
    # in `metadata` as annotated-types constraints (`[Ge(ge=1), Le(le=200)]`),
    # not as `.ge` / `.le` attributes. The first version of this assertion
    # looked for the attributes, found None on a correctly-bounded parameter,
    # and failed — a test that would have been "fixed" by loosening it.
    constraints = {type(c).__name__: c for c in getattr(limit, "metadata", [])}
    assert "Ge" in constraints, (
        "limit lost its lower bound; `LIMIT -5` is a 500 again")
    assert constraints["Ge"].ge == 1
    assert "Le" in constraints, "limit lost its upper bound"
