"""Every `status` the API emits has to belong to a class the frontend knows.

These endpoints answer **HTTP 200 whether they succeeded or not** (see
`test_ok_with_status_error_is_a_deliberate_convention.py`), so the in-band
`status` field is the only thing separating "no data" from "the query fell
over". The new SPA reads it in `src/app/lib/responseStatus.ts` — but that file
is TypeScript and this vocabulary is defined in Python, and **a fact written
in two languages drifts in silence**: nothing in either build fails when a
router starts emitting a spelling the frontend has never heard of. It just
renders the outage as an empty section.

So the check lives here, in the language that can read both sides.

⚠️ The classification matters as much as the list. Measured across
`website/backend/routers/`, `status` takes 17 distinct values at the API
boundary, and most are not verdicts about whether the request worked:
`queued`/`uploaded` are an upload lifecycle, `LOOKING`/`AVAILABLE`/`MAYBE` are
RSVP answers, `prototype`/`retired…` are a formula's maturity. A blanket
failure test over those would black out pages that are working — which is why
the frontend module is deliberately narrow and why this test asks for a class
rather than a yes/no.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTERS = ROOT / "website" / "backend" / "routers"
FRONTEND_MODULE = ROOT / "website" / "frontend" / "src" / "app" / "lib" / "responseStatus.ts"

# Values that are not verdicts about whether the request worked, and so are
# none of the frontend's business. Each is here because somebody looked.
NOT_A_RESULT_VERDICT = {
    "ok",
    "success",  # it worked
    "online",  # a game server's state, not the request's
    "LOOKING",
    "AVAILABLE",
    "MAYBE",
    "scheduled",  # RSVP answers
    "queued",
    "uploaded",  # upload lifecycle
    "prototype",
    "read_only",  # a surface's maturity
    "retired in kis-v5 (2026-07-25)",  # a formula's obituary
    "unsupported",  # SQLite dev fallback, never production
    "unknown",  # "not assessed", carried with available=False
}


def _emitted_statuses() -> set[str]:
    """⚠️ Structural: dict literals only.

    A grep would match this module's own prose — it names most of these
    values — and would report agreement it never measured.
    """
    found: set[str] = set()
    for path in sorted(ROUTERS.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "status"
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                ):
                    found.add(value.value)
    return found


def _frontend_list(name: str) -> set[str]:
    """Read one exported array out of the TypeScript module.

    ⚠️ Anchored on `export const <name> = [` and closed at the first `]`, so
    the module's long docstrings — which mention every one of these values in
    prose — cannot satisfy it.
    """
    source = FRONTEND_MODULE.read_text()
    match = re.search(rf"export const {name} = \[(.*?)\]", source, re.S)
    assert match, f"{name} is no longer an array literal in {FRONTEND_MODULE.name}"
    return set(re.findall(r"'([^']+)'", match.group(1)))


def test_the_frontend_lists_parse():
    """A control: a reader that returns nothing agrees with everything."""
    failures = _frontend_list("FAILURE_STATUSES")
    not_failures = _frontend_list("NOT_FAILURE_STATUSES")
    assert failures == {"error", "unavailable"}, (
        f"the failure vocabulary changed: {sorted(failures)}. If that is "
        "deliberate, this assertion is the place to record it."
    )
    assert len(not_failures) >= 4, (
        f"only {len(not_failures)} look-alikes are documented; the reader is probably matching the wrong block"
    )
    assert not failures & not_failures, "a status cannot be in both classes"


def test_every_emitted_status_belongs_to_a_class():
    emitted = _emitted_statuses()
    classified = _frontend_list("FAILURE_STATUSES") | _frontend_list("NOT_FAILURE_STATUSES") | NOT_A_RESULT_VERDICT
    unclassified = emitted - classified
    assert not unclassified, (
        f"a router emits status values nothing has classified: "
        f"{sorted(unclassified)}.\n"
        "Decide which one each is and say so in the same commit:\n"
        "  - it means the answer is unusable -> add it to FAILURE_STATUSES in "
        "website/frontend/src/app/lib/responseStatus.ts\n"
        "  - it looks like a failure but is a real answer -> add it to "
        "NOT_FAILURE_STATUSES there, with the reason\n"
        "  - it is not a verdict about the request at all (a lifecycle, an "
        "RSVP, a maturity level) -> add it to NOT_A_RESULT_VERDICT here.\n"
        "Leaving it unclassified means the new SPA renders that failure as an "
        "empty section, with a 200 and no error anywhere."
    )


def test_the_reader_sees_the_values_this_file_is_about():
    """A control on the AST side, for the same reason as the one above."""
    emitted = _emitted_statuses()
    assert {"error", "unavailable", "ok"} <= emitted, (
        f"the AST reader missed statuses that are certainly emitted: {sorted({'error', 'unavailable', 'ok'} - emitted)}"
    )
    assert "definitely-not-a-real-status" not in emitted, "the reader invents values"
