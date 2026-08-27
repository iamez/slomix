"""⛔ THE FILTERING HAPPENS IN FASTAPI, NOT IN PYDANTIC.

`tests/unit/test_response_models_drop_nothing.py` serialises a recorded
response through the model and compares. That proves the model CAN carry the
payload. It does not prove what the client receives, because the drop happens
in FastAPI's `serialize_response`, which runs its own validation against the
`response_model` and returns whatever survives — with a 200.

The two paths differ in ways that matter here:

  * `model_dump_json()` on an already-validated instance round-trips what the
    instance holds;
  * FastAPI re-validates the handler's RAW return value against the field
    definitions and silently discards anything the model does not declare.

So this file mounts each model on a real route that returns the recorded
fixture, calls it over ASGI, and compares the wire bytes against the fixture.
A field a model forgets fails HERE even when the unit test passes.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from website.backend.routers.records_awards import (
    AwardLeaderboard,
    AwardsPage,
    HallOfFame,
)
from website.backend.routers.records_seasons import CurrentSeason
from website.backend.routers.records_weapons import WeaponsByPlayer

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "api_responses"

CASES = [
    ("api_awards.json", AwardsPage),
    ("api_awards_leaderboard.json", AwardLeaderboard),
    ("api_hall-of-fame.json", HallOfFame),
    ("api_seasons_current.json", CurrentSeason),
    ("api_stats_weapons_by_player.json", WeaponsByPlayer),
]


def _differences(expected, actual, path: str = "") -> list[str]:
    """Every key AND every value that changed on the way to the client."""
    out: list[str] = []
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path or '<root>'}: dict -> {type(actual).__name__}"]
        for key, value in expected.items():
            here = f"{path}.{key}" if path else str(key)
            if key not in actual:
                out.append(f"{here}: DROPPED")
                continue
            out.extend(_differences(value, actual[key], here))
        out.extend(f"{path}.{key}: INVENTED"
                   for key in actual if key not in expected)
    elif isinstance(expected, list):
        if not isinstance(actual, list):
            return [f"{path}: list -> {type(actual).__name__}"]
        if len(expected) != len(actual):
            out.append(f"{path}: {len(expected)} -> {len(actual)} items")
        for i, (a, b) in enumerate(zip(expected, actual)):
            out.extend(_differences(a, b, f"{path}[{i}]"))
    elif expected != actual:
        out.append(f"{path}: {expected!r} -> {actual!r}")
    return out


async def _through_fastapi(payload, model):
    app = FastAPI()

    @app.get("/probe", response_model=model)
    async def probe():           # noqa: ANN202 - test route
        return payload

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/probe")
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
@pytest.mark.parametrize(("fixture", "model"), CASES, ids=[f for f, _ in CASES])
async def test_the_client_receives_every_field_the_handler_returned(fixture, model):
    payload = json.loads((FIXTURES / fixture).read_text())
    received = await _through_fastapi(payload, model)
    diffs = _differences(payload, received)
    assert not diffs, f"{fixture} via {model.__name__}: {diffs[:8]}"


@pytest.mark.asyncio
async def test_this_harness_can_actually_fail():
    """States its own premise.

    A test that only ever sees passing models cannot distinguish "nothing is
    dropped" from "the comparison is broken". This one hands FastAPI a model
    that is deliberately missing a field and requires the drop to be seen.
    """
    from pydantic import BaseModel

    class Incomplete(BaseModel):
        id: str  # `name`, `days_left` and five more are absent on purpose

    payload = json.loads((FIXTURES / "api_seasons_current.json").read_text())
    received = await _through_fastapi(payload, Incomplete)
    diffs = _differences(payload, received)
    assert any("DROPPED" in d for d in diffs), (
        "a model missing six fields lost nothing — the comparison is broken")
