"""⛔ A FAILURE LABEL THE PAGE NEVER LOOKS UP MARKS NOTHING, SILENTLY.

`/api/stats/overview` answers `status: "partial"` with `failed_metrics` naming
the queries that failed, and `Home.StandingFigures` renders `missing` for a cell
whose metric is in that list. The coupling is by STRING, across two languages,
with nothing checking it — and two of the four rendered cells were wrong from
the day the feature shipped: the backend emitted `rounds_count` and
`sessions_count` while the page asked about `rounds` and `sessions`.

So a failed rounds query produced `status: "partial"`, a fallback zero, and an
ordinary dash on the homepage — the outage-as-zero ambiguity the field exists to
remove, surviving inside the fix for it. The other two cells matched by
coincidence of naming, which is exactly why nothing looked wrong.

Codex on #848. This test is the joint the two sides were missing.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "website/backend/routers/records_overview.py"
HOME = ROOT / "website/frontend/src/app/pages/Home.tsx"


def _emitted_labels() -> set[str]:
    """Every `metric=` label this endpoint can put into `failed_metrics`.

    Parsed, not grepped: the calls span lines and the keyword is usually on a
    later one.
    """
    tree = ast.parse(BACKEND.read_text(encoding="utf-8"))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "metric" and isinstance(kw.value, ast.Constant):
                    out.add(kw.value.value)
    return out


def _keys_the_homepage_asks_about() -> set[str]:
    """The second argument of every `live(...)` call in StandingFigures.

    ⚠️ Comments are stripped first. A guard that greps a source file is one
    comment away from agreeing with the prose that explains the code — and the
    prose here names the very strings being checked.
    """
    text = HOME.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = "\n".join(ln.split("//")[0] for ln in text.splitlines())
    return set(re.findall(r"live\([^,]+,\s*'([^']+)'\)", text))


def test_the_reader_finds_both_sides():
    """CONTROL FIRST. Two empty sets agree perfectly, and an extractor that
    silently found nothing would make the real assertion below meaningless."""
    emitted, asked = _emitted_labels(), _keys_the_homepage_asks_about()
    assert len(emitted) >= 10, f"only {len(emitted)} metric labels found"
    assert len(asked) >= 4, f"only {len(asked)} live() keys found: {asked}"
    assert "total_kills" in emitted and "total_kills" in asked


def test_the_homepage_asks_about_labels_the_api_emits():
    asked = _keys_the_homepage_asks_about()
    emitted = _emitted_labels()
    unknown = sorted(asked - emitted)
    assert not unknown, (
        "the homepage marks these cells as missing by asking for labels the API "
        f"never emits, so they can never be marked: {unknown}\n"
        f"emitted: {sorted(emitted)}\n"
        "Either rename the backend `metric=` label to the response field it "
        "feeds, or translate in the page — but the two lists have to meet.")


def test_the_comment_stripper_is_doing_its_job():
    """CONTROL for the reader itself: a `live(` written inside a comment must
    not count as the page asking about it."""
    raw = HOME.read_text(encoding="utf-8")
    assert "//" in raw, "no comments in the file — this control proves nothing"
    stripped = _keys_the_homepage_asks_about()
    assert all("'" not in k and "//" not in k for k in stripped), stripped
