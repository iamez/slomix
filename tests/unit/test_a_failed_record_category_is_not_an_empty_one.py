"""⛔ ON /api/stats/records, `[]` MEANS FAILED AND AN ABSENT KEY MEANS EMPTY.

Backwards from what any reader would guess, and it happened by accident: the
success path omits a category with no rows (`if rows:`), while the failure path
sets it to `[]`. It is nonetheless the ONLY signal this endpoint has that a
category could not be measured, so it is pinned here — an undocumented
distinction is one refactor away from being "tidied" into agreement, and the
tidy version cannot tell an outage from a quiet season.

⚠️ It is not fixed by adding a `status` field the way the rest of this family
was. `StatsRecords` is declared on the client as
`export type StatsRecords = Record<string, RecordEntry[]>` — a type ALIAS whose
values are all arrays — so a string field here breaks the SPA type. Moving the
wire needs both sides moved together.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from website.backend.dependencies import get_db
from website.backend.routers import records_awards

PATH = "/api/stats/records"


class _Broken:
    async def fetch_all(self, *a, **k): raise RuntimeError("database is down")
    async def fetch_one(self, *a, **k): raise RuntimeError("database is down")
    async def fetch_val(self, *a, **k): raise RuntimeError("database is down")


class _Empty:
    async def fetch_all(self, *a, **k): return []
    async def fetch_one(self, *a, **k): return None
    async def fetch_val(self, *a, **k): return 0


def _body(stub):
    app = FastAPI()
    app.include_router(records_awards.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: stub()
    return TestClient(app, raise_server_exceptions=False).get(PATH).json()


def test_a_failed_category_arrives_as_an_empty_list():
    body = _body(_Broken)
    assert body, "the endpoint answered nothing at all"
    assert all(v == [] for v in body.values()), (
        "with every query raising, each category must arrive as [] — that is "
        "this endpoint's only way of saying it could not measure one")


def test_a_genuinely_empty_category_is_ABSENT_not_empty():
    """⛔ THE OTHER HALF, AND THE ONE THAT MAKES THE FIRST MEAN ANYTHING.

    If a working-but-empty database also produced `[]`, the two states would be
    identical and the first test above would be pinning nothing.
    """
    body = _body(_Empty)
    assert body == {}, (
        f"a working database with no rows must OMIT the categories, not send "
        f"them empty; got keys {sorted(body)}")


@pytest.mark.parametrize("stub,expected", [(_Broken, 200), (_Empty, 200)])
def test_both_states_answer_200(stub, expected):
    app = FastAPI()
    app.include_router(records_awards.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: stub()
    assert TestClient(app, raise_server_exceptions=False).get(PATH).status_code == expected
