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
`website/backend/routers/`, `status` takes 22 distinct values at the API
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
    # A subsystem HEALTH grade (diagnostics_router:707: healthy/degraded/
    # poor by percentage) — a verdict about the pipeline, not the request.
    # Surfaced only when the widened reader learned to see conditional
    # emissions; classified the day it was first seen.
    "healthy",
    "poor",
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
                if not (isinstance(key, ast.Constant) and key.value == "status"):
                    continue

                # ⛔ Not only bare literals: #830 ships
                # `"status": "ok" if not failures else "partial"`, and a
                # Constant-only reader was BLIND to the conditional — the
                # guard passed while an unclassified status shipped.
                # expression — but only along EMISSION shapes (a bare
                # constant, either branch of a conditional, operands of
                # `or`): a blind ast.walk also swept subscript keys like
                # row["status"] and reported the word 'status' itself as
                # an emitted value — a false positive measured on the
                # first run of the widened reader.
                def emitted_strings(node):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        yield node.value
                    elif isinstance(node, ast.IfExp):
                        yield from emitted_strings(node.body)
                        yield from emitted_strings(node.orelse)
                    elif isinstance(node, ast.BoolOp):
                        for v in node.values:
                            yield from emitted_strings(v)

                found.update(emitted_strings(value))
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
    # ⛔ Comments OUT before reading literals: an apostrophe inside an inline
    # comment ("#830's") poisoned the naive quote-pair reader and mangled
    # every entry after it — the guard silently unclassified values that WERE
    # classified. Prose must never reach a literal reader.
    body = re.sub(r"//[^\n]*", "", match.group(1))
    return set(re.findall(r"'([^']+)'", body))


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
    # ⛔ "partial" is emitted only through a CONDITIONAL ("ok" if ... else
    # "partial", records_overview) — it pins the reader's WIDTH: a reader
    # narrowed back to bare literals stops seeing it, the unclassified set
    # goes empty, and the classification test passes vacuously. That exact
    # mutation survived until this line existed.
    assert {"error", "unavailable", "ok", "partial"} <= emitted, (
        f"the AST reader missed statuses that are certainly emitted: {sorted({'error', 'unavailable', 'ok'} - emitted)}"
    )
    assert "definitely-not-a-real-status" not in emitted, "the reader invents values"


def test_the_numbers_this_files_prose_claims_are_still_true():
    """⛔ A COUNT WRITTEN IN A DOCSTRING GOES STALE IN SILENCE.

    Both numbers above were wrong when this was written — the module said 30 and
    the test said 17, and the measured vocabulary was 22. Nothing checked them,
    so they described a repository that no longer existed while reading like
    fact. Asserting the count is what makes the prose a claim instead of a
    decoration; when it fails, correct the sentence in the same commit that
    moved the number.
    """
    measured = len(_emitted_statuses())
    assert measured == 22, (
        f"the emitted status vocabulary is now {measured} values, not 22 — "
        f"update the count in this module's docstring and in the test above, "
        f"and check that every new spelling is classified on the TypeScript "
        f"side")
