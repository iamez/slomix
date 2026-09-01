"""⛔ A COVERAGE NUMBER NOBODY MEASURES IS A COVERAGE NUMBER THAT FALLS.

Three rounds of work (#806, #820, #830) put `response_model` on 43 of the 263
route decorators in `website/backend/routers/`. Nothing guarded the other 220,
and nothing stopped the 43 from becoming 42: every existing test in this area
checks that a model which EXISTS describes its payload correctly
(`test_response_models_drop_nothing.py`) or that a hard-coded list of typed
paths survives an empty database
(`test_typed_endpoints_survive_short_shapes.py`, whose `TYPED_PATHS` is a
literal, so a new untyped route never fails it).

Quality guards, not a coverage guard. This is the coverage guard, built like
`tests/data/endpoint_gap.txt`: the set is RECOMPUTED here and the file is only
the record, so the two cannot disagree quietly. It fails in BOTH directions —
a new untyped route is a regression, and a route that gained a model while
staying listed is a stale line somebody must delete. A ratchet that only tightens
when someone remembers to tighten it is an allowance, which is the failure mode
#823 named.

⚠️ The threshold is what `main` has (220), never what `main` plus the open
branches has.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTERS = ROOT / "website/backend/routers"
GAP_FILE = ROOT / "tests/data/response_model_gap.txt"

_HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}


def _routes() -> list[tuple[str, str, str, str, bool]]:
    """(module, handler, METHOD, path, has_response_model) for every route.

    Parsed, not grepped: a decorator spans several lines and `response_model=`
    is routinely on one of the later ones, so a line-oriented scan reports a
    coverage that has nothing to do with the code.
    """
    out = []
    for f in sorted(ROUTERS.glob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if not (isinstance(dec, ast.Call)
                        and isinstance(dec.func, ast.Attribute)
                        and dec.func.attr in _HTTP_METHODS):
                    continue
                path = (dec.args[0].value
                        if dec.args and isinstance(dec.args[0], ast.Constant)
                        else "?")
                out.append((f.name, node.name, dec.func.attr.upper(), path,
                            any(k.arg == "response_model" for k in dec.keywords)))
    return out


def _untyped_keys() -> set[str]:
    return {f"{mod}::{fn}" for mod, fn, _, _, typed in _routes() if not typed}


def _recorded() -> set[str]:
    return {ln.split("#")[0].strip() for ln in GAP_FILE.read_text().splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")}


def test_the_extractor_sees_both_kinds():
    """CONTROL, and it comes first.

    An extractor that returned everything, or nothing, would make every
    assertion below pass while measuring the empty set. `/api/stats/records`
    (records_awards.get_records) is typed and `/proximity/duos`
    (proximity_combat.get_proximity_duos) is not — both by inspection.
    """
    routes = _routes()
    assert len(routes) > 200, f"only {len(routes)} routes parsed"
    typed = {f"{m}::{h}" for m, h, _, _, t in routes if t}
    untyped = {f"{m}::{h}" for m, h, _, _, t in routes if not t}
    assert typed and untyped, "the extractor put every route in one bucket"
    assert "records_awards.py::get_records" in typed
    assert "proximity_combat.py::get_proximity_duos" in untyped
    assert not (typed & untyped)


def test_no_new_route_ships_without_a_response_model():
    regressed = sorted(_untyped_keys() - _recorded())
    assert not regressed, (
        "these routes have no `response_model`, and a route without one returns "
        "whatever the handler built — undeclared keys are not filtered, they are "
        "simply never checked against anything:\n  "
        + "\n  ".join(regressed)
        + "\n\nAdd a model (see website/backend/routers/records_overview.py for "
          "the shape), or, if it is genuinely not typeable yet, add the line to "
          "tests/data/response_model_gap.txt WITH a reason.")


def test_the_gap_file_does_not_keep_routes_that_were_fixed():
    stale = sorted(_recorded() - _untyped_keys())
    assert not stale, (
        "these routes now HAVE a response_model but are still listed as missing "
        "one — delete their lines from tests/data/response_model_gap.txt in the "
        "commit that typed them, so the file keeps meaning what it says:\n  "
        + "\n  ".join(stale))


def test_the_recorded_gap_is_the_measured_one():
    """Both directions in one number, so the file cannot drift by a line.

    ⚠️ When this fails because the gap SHRANK, the fix is to delete the lines,
    not to raise anything: there is no allowance here to spend.
    """
    assert _untyped_keys() == _recorded()
