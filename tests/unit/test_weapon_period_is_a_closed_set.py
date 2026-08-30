"""Regression: `period=nonsense` answered 200 with all-time numbers.

The three weapon handlers branch on `"7d"` / `"30d"` / `"season"` and let
everything else fall through to the no-date-filter branch. With `period: str`
that meant an unrecognised value was silently treated as `"all"` — and the
response echoed the value back under a `"period"` key, so the answer looked
like it had honoured the request. Measured live on dev 2026-08-30, before the
fix, on `/api/stats/weapons/by-player`:

    period=all       -> period='all'       players=25
    period=nonsense  -> period='nonsense'  players=25   <- same rows, all time
    period=session   -> period='session'   players=25
    period=week      -> period='week'      players=25

An ignored parameter is a wrong answer wearing the shape of a right one, and
it is the same class as the `/proximity/revives` finding, where an ignored
argument was a twelve-fold error in production.

The closed set is safe because it was measured, not guessed: both frontends
offer exactly these four values and default to `"all"` —
`PERIODS = ['all', 'season', '30d', '7d']` in `WeaponsPage.tsx:37`, the four
`data-weapon-period` buttons in the legacy pages, and
`let weaponPeriod = 'all'` in `matches.js:373`.

⚠️ The last test here is the one that matters over time: the whitelist and
the branch chain are the SAME fact written in two places, and a value added
to one but not the other reopens exactly this bug — a new `elif period ==
"90d"` would be dead code, a new Literal member would silently mean "all".
"""
import ast
import inspect
import typing
import warnings
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

warnings.filterwarnings("ignore")

from website.backend import dependencies as deps  # noqa: E402
from website.backend.routers import records_weapons  # noqa: E402

# The three handlers that take `period`, and the route each is reached by.
WEAPON_ROUTES = [
    "/api/stats/weapons",
    "/api/stats/weapons/hall-of-fame",
    "/api/stats/weapons/by-player",
    "/api/stats/weapons/by_player",
]
VALID_PERIODS = ["all", "season", "30d", "7d"]


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
    app.include_router(records_weapons.router, prefix="/api")
    app.dependency_overrides[deps.get_db] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, db


@pytest.mark.parametrize("route", WEAPON_ROUTES)
@pytest.mark.parametrize("period", ["nonsense", "session", "week", "all_time", "", "7D"])
def test_a_period_the_handler_cannot_honour_is_refused(client_and_db, route, period):
    client, db = client_and_db
    response = client.get(f"{route}?period={period}")
    assert response.status_code == 422, (
        f"{route}?period={period} answered {response.status_code}; a window "
        f"the handler cannot apply must be refused, not silently widened to "
        f"all time")
    assert db.calls == [], (
        f"{route}?period={period} reached the database — the value is being "
        f"checked inside the handler, below the blanket `except`")


@pytest.mark.parametrize("route", WEAPON_ROUTES)
@pytest.mark.parametrize("period", [*VALID_PERIODS, None])
def test_every_value_a_frontend_can_send_still_works(client_and_db, route, period):
    """The closed set must not narrow live behaviour: these four plus the
    default are everything `weaponPeriod` and `PERIODS` can hold."""
    client, db = client_and_db
    url = route if period is None else f"{route}?period={period}"
    response = client.get(url)
    assert response.status_code == 200, response.text
    assert db.calls, "the handler stopped querying"


def test_both_spellings_of_by_player_carry_the_same_contract():
    """⛔ Two paths, one handler — and until now two contracts.

    `/by-player` had no `response_model` while `/by_player` had one, so the
    guard covered the spelling legacy `matches.js` calls first and left the
    one `session-detail.js` and the old React client call unguarded. Read off
    the ROUTE OBJECTS, never off the source text: a decorator can be edited
    without changing what FastAPI registered.
    """
    models = {
        route.path: route.response_model
        for route in records_weapons.router.routes
        if getattr(route, "path", "").endswith(("by-player", "by_player"))
    }
    assert set(models) == {"/stats/weapons/by-player", "/stats/weapons/by_player"}, (
        f"expected both spellings to be registered, found {sorted(models)}")
    assert models["/stats/weapons/by-player"] is models["/stats/weapons/by_player"], (
        f"the two spellings of one handler carry different contracts: {models}")
    assert models["/stats/weapons/by-player"] is not None, (
        "both spellings are now untyped — the guard was removed, not shared")


def _literal_periods() -> set[str]:
    """The whitelist, read off the annotation object."""
    signature = inspect.signature(records_weapons.get_weapon_stats_by_player)
    annotation = signature.parameters["period"].annotation
    literal = typing.get_args(annotation)[0]  # unwrap Annotated
    return set(typing.get_args(literal))


def _branch_periods() -> set[str]:
    """The values the handlers actually branch on, read structurally.

    ⚠️ AST over the comparison nodes, not a regex over the file: a grep would
    match the same strings in this docstring, in a comment, or in an unrelated
    handler, and would report agreement that was never measured.
    """
    source = Path(inspect.getfile(records_weapons)).read_text()
    tree = ast.parse(source)
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare) or not isinstance(node.ops[0], ast.Eq):
            continue
        left, right = node.left, node.comparators[0]
        if isinstance(left, ast.Name) and left.id == "period" and isinstance(right, ast.Constant):
            found.add(right.value)
    return found


def test_the_whitelist_and_the_branch_chain_are_the_same_set():
    """⛔ THE PART A STATUS CODE CANNOT PROVE.

    Every test above passes if someone adds `"90d"` to the Literal and
    nowhere else — the request is accepted and quietly answered with
    all-time numbers, which is the bug this file exists for, reopened.
    """
    whitelist = _literal_periods()
    branches = _branch_periods()
    # "all" is the fall-through, so it is deliberately not a branch.
    assert whitelist - {"all"} == branches, (
        f"the accepted values and the branches disagree.\n"
        f"  accepted but never branched on (answered as all-time): "
        f"{sorted(whitelist - {'all'} - branches)}\n"
        f"  branched on but rejected at the door (dead code): "
        f"{sorted(branches - whitelist)}")
    assert "all" in whitelist, "the default stopped being an accepted value"


def test_the_checks_above_can_fail():
    """A control: the two readers must disagree when the sets differ."""
    whitelist = _literal_periods()
    assert whitelist - {"all"} != _branch_periods() | {"90d"}, (
        "the comparison cannot distinguish an extra member — it is not a guard")
    assert _branch_periods(), (
        "the AST reader found no branches at all; it would agree with any "
        "whitelist, including an empty one")
