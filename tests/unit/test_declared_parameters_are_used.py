"""⛔ A QUERY PARAMETER THE HANDLER NEVER READS IS A LIE WITH A 200 ON IT.

`/proximity/revives` accepted `session_date`, `round_number` and `player_guid`
and used none of them. The page asked for one round and was shown the last
thirty days: 1,873 revives where the round had 90 — a 12x error, live, for as
long as nobody looked. It was fixed one endpoint at a time, which is how the
next one gets missed.

This is the class guard. It parses every route handler and asks whether each
declared parameter appears ANYWHERE in the body — f-strings, helper calls,
nested closures included, because a parameter passed straight through to a
helper is used. Nothing is inferred about correctness; only about a parameter
that could not possibly have had an effect.

⚠️ Ignoring a parameter can be deliberate. `ACCEPTED_AND_IGNORED` is that door,
and it is deliberately narrow: each entry names the endpoint, the parameter and
the reason, and adding one is a decision somebody has to write down.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTERS = ROOT / "website/backend/routers"

_HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}

# Not parameters the handler is expected to read in its body.
_INFRASTRUCTURE = {"request", "response", "db", "self", "cls",
                   "background_tasks", "credentials"}
_INFRA_ANNOTATIONS = {"Request", "Response", "BackgroundTasks", "DatabaseAdapter"}

ACCEPTED_AND_IGNORED = {
    # players_router.get_leaderboard — documented in place at its signature.
    # The HAVING clause it fed was removed; the parameter is kept so that
    # `?min_games=abc` still answers 422 rather than silently succeeding.
    # Dropping it would change the contract; using it would change the numbers.
    "players_router.py::get_leaderboard::min_games",
}


def _is_dependency(default: ast.expr | None) -> bool:
    return (isinstance(default, ast.Call) and isinstance(default.func, ast.Name)
            and default.func.id in {"Depends", "Security"})


def _annotation_name(node: ast.expr | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Subscript):
        return _annotation_name(node.value)
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _names_used(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Every identifier mentioned in the body, including inside f-strings."""
    used: set[str] = set()
    for stmt in fn.body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name):
                used.add(node.id)
            elif isinstance(node, ast.arg):          # nested defs / lambdas
                used.add(node.arg)
            elif isinstance(node, ast.keyword) and node.arg:
                used.add(node.arg)
    return used


def _unused_parameters() -> list[str]:
    out = []
    for f in sorted(ROUTERS.glob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                       and d.func.attr in _HTTP_METHODS for d in fn.decorator_list):
                continue
            args = fn.args
            params = list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
            defaults = ([None] * (len(args.posonlyargs) + len(args.args)
                                  - len(args.defaults)) + list(args.defaults))
            defaults += list(args.kw_defaults)
            used = _names_used(fn)
            for i, a in enumerate(params):
                if a.arg in _INFRASTRUCTURE:
                    continue
                if _annotation_name(a.annotation) in _INFRA_ANNOTATIONS:
                    continue
                if i < len(defaults) and _is_dependency(defaults[i]):
                    continue
                if a.arg not in used:
                    out.append(f"{f.name}::{fn.name}::{a.arg}")
    return sorted(out)


def test_the_scanner_can_actually_find_one():
    """CONTROL, first. A scanner that returns the empty set for the wrong
    reason — a parse failure, an over-broad exclusion — makes the real
    assertion below pass while measuring nothing. So it is pointed at a
    synthetic handler whose unused parameter is not in doubt."""
    src = (
        "@router.get('/x')\n"
        "async def h(used: int = 1, ignored: str | None = None,\n"
        "            db: DatabaseAdapter = Depends(get_db)):\n"
        "    return {'v': used}\n"
    )
    tree = ast.parse(src)
    fn = tree.body[0]
    used = _names_used(fn)
    assert "used" in used and "ignored" not in used, (
        "the body scan cannot tell a read parameter from an unread one")


def test_the_scanner_reaches_the_real_routers():
    """CONTROL. If the glob or the parse silently found nothing, every
    endpoint would look clean."""
    found = _unused_parameters()
    assert (ROUTERS / "proximity_combat.py").exists()
    assert len(list(ROUTERS.glob("*.py"))) > 30
    # min_games is the known deliberate case: the scanner must still SEE it,
    # it is only excused below. If this stops holding the scanner went blind.
    assert "players_router.py::get_leaderboard::min_games" in found


def test_every_declared_parameter_reaches_the_query():
    unused = [k for k in _unused_parameters() if k not in ACCEPTED_AND_IGNORED]
    assert not unused, (
        "these endpoints declare a query parameter and never read it, so a "
        "caller that sets it gets the UNFILTERED answer with a 200 — the shape "
        "of the /proximity/revives 12x error:\n  "
        + "\n  ".join(unused)
        + "\n\nUse it, remove it, or add it to ACCEPTED_AND_IGNORED with the "
          "reason it is accepted and ignored.")
