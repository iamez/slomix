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
    """Every identifier the handler's OWN scope reads, f-strings included.

    ⛔ Reads only, and scope-aware. Three things are NOT reads of a handler
    parameter, and the first version counted all three:

      * a nested function's or lambda's own parameter list (`ast.arg`)
      * the NAME of a keyword argument at a call site (`ast.keyword`)
      * a name read INSIDE a nested scope that rebinds it as its own parameter

    The third is the subtle one and only a scope walk finds it:
    `def inner(session_date): return session_date` reads a name spelled the
    same as the handler's parameter while nothing ever looks at the handler's.
    Passing a parameter through to a helper is still an `ast.Name` load in the
    handler's own scope, so that case remains covered. Codex on #860.
    """
    used: set[str] = set()

    def walk(node: ast.AST, shadowed: frozenset[str]) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            a = node.args
            own = {x.arg for x in
                   list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs)}
            if a.vararg:
                own.add(a.vararg.arg)
            if a.kwarg:
                own.add(a.kwarg.arg)
            # ⚠️ Defaults are evaluated in the ENCLOSING scope, so they still
            # count as reads: `def inner(x=session_date)` does read it.
            for d in list(a.defaults) + [d for d in a.kw_defaults if d]:
                walk(d, shadowed)
            body = node.body if isinstance(node.body, list) else [node.body]
            for stmt in body:
                walk(stmt, shadowed | own)
            return
        if isinstance(node, ast.Name):
            # ⛔ A STORE IS NOT A READ. `player_guid = None` at the top of a
            # handler is an `ast.Name` too, and counting it marked the parameter
            # used while the caller's value could never reach the response —
            # precisely the shape this scanner exists to find, excused by the
            # scanner. Codex on #860.
            if isinstance(node.ctx, ast.Load) and node.id not in shadowed:
                used.add(node.id)
            return
        for child in ast.iter_child_nodes(node):
            walk(child, shadowed)

    for stmt in fn.body:
        walk(stmt, frozenset())
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
        "            shadowed: str | None = None, kw: int = 0,\n"
        "            overwritten: str | None = None,\n"
        "            db: DatabaseAdapter = Depends(get_db)):\n"
        "    def inner(shadowed):\n"
        "        return shadowed\n"
        "    helper(kw=1)\n"
        "    overwritten = None\n"
        "    return {'v': used}\n"
    )
    tree = ast.parse(src)
    fn = tree.body[0]
    used = _names_used(fn)
    assert "used" in used, "a plainly read parameter was not seen as read"
    assert "ignored" not in used, "an unread parameter was counted as read"
    # ⛔ The two that the first version got wrong, and neither is a read:
    assert "shadowed" not in used, (
        "a NESTED function's own parameter list was counted as a read of the "
        "outer parameter of the same name")
    assert "kw" not in used, (
        "the NAME of a keyword argument at a call site was counted as a read")
    assert "overwritten" not in used, (
        "a parameter that is only ASSIGNED TO was counted as read, so a value "
        "the caller supplies and the handler discards looks used")


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
