"""Two paths, one handler, and — until 2026-08-30 — one operationId.

`/api/stats/weapons/by-player` and `/api/stats/weapons/by_player` are the same
function under two spellings. FastAPI derives an operationId from the function
name plus the path and normalises `-` to `_`, so both produced
`get_weapon_stats_by_player_api_stats_weapons_by_player_get`.

⛔ WHY THAT WAS NOT COSMETIC. OpenAPI requires operationId to be unique, and
the generator turns each one into a member of the `operations` interface — so
the generated `openapi.d.ts` declared the same member twice. While the two
routes carried DIFFERENT contracts (the hyphen route had no `response_model`
and rendered as `unknown`, the underscore route had `WeaponsByPlayer`), the
compiler silently kept one of the two declarations. A caller of one path could
be typed by the other, and nothing anywhere said so: `tsc` passed, the snapshot
test passed, and the duplicate was invisible in both languages.

This guard is over the rendered document rather than the source, because the
collision is produced by FastAPI's derivation and not written down anywhere a
reader could grep for.
"""

import collections

from website.backend.main import app


def _operation_ids() -> list[str]:
    schema = app.openapi()
    return [
        operation["operationId"]
        for operations in schema["paths"].values()
        for operation in operations.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]


def test_no_two_routes_share_an_operation_id():
    counts = collections.Counter(_operation_ids())
    duplicates = {name: n for name, n in counts.items() if n > 1}
    assert not duplicates, (
        f"operationId is not unique: {duplicates}.\n"
        "Two routes on one handler collide once FastAPI normalises the path. "
        "Give the alias an explicit `operation_id=` in its decorator — "
        "otherwise the generated TypeScript declares one interface member "
        "twice and the compiler keeps whichever it saw last."
    )


def test_the_reader_is_actually_reading():
    """A control: an empty list has no duplicates either."""
    ids = _operation_ids()
    assert len(ids) > 200, f"only {len(ids)} operations found; the reader is broken"
    assert "get_weapon_stats_by_player_hyphen_alias" in ids, (
        "the alias that motivated this guard is no longer declared explicitly, "
        "so the collision it prevents is probably back"
    )
