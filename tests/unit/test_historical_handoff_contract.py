"""Keep the retained historical handoff distinct from current operating advice."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def assert_no_timer_enable_recipe(text):
    """Reject enable recipes regardless of their activation/dry-run flags."""
    normalized = " ".join(text.split())
    assert not re.search(
        r"\bsystemctl\b[^`;]*\benable\b[^`;]*\bsystemd-tmpfiles-clean\.timer\b",
        normalized,
    ), "Historical cleanup must not prescribe enabling the static timer"


@pytest.mark.parametrize("flags", ["", "--now ", "--dry-run ", "--user --now "])
def test_timer_enable_guard_rejects_flag_variants(flags):
    with pytest.raises(AssertionError, match="static timer"):
        assert_no_timer_enable_recipe(
            f"`sudo systemctl enable {flags}systemd-tmpfiles-clean.timer`"
        )


def test_historical_handoff_is_dated_and_its_companion_is_available():
    """The retained snapshot must not masquerade as the current plan."""
    handoff = (ROOT / "docs/HANDOFF-opus5-2026-09-07.md").read_text()
    assert "Historical snapshot, not current operating instructions" in handoff
    assert "#952, #955 and #958 landed after v1.45.0" in handoff
    assert (ROOT / "docs/HANDOFF-astra.md").is_file()


def test_historical_cleanup_advice_is_not_a_static_timer_enable_recipe():
    """A static unit is not diagnosed by an inapplicable enable command."""
    for name in ("HANDOFF-opus5-2026-09-07.md", "BACKLOG.md"):
        assert_no_timer_enable_recipe((ROOT / "docs" / name).read_text())
    handoff = (ROOT / "docs/HANDOFF-opus5-2026-09-07.md").read_text()
    assert "--rotate --vacuum-size=200M" in handoff
    assert "explicit journald restart" in handoff


def test_historical_backlog_follows_newer_checkpoints_and_recipe_has_root_paths():
    backlog = (ROOT / "docs/BACKLOG.md").read_text()
    assert backlog.index("(Astra, 2026-09-20)") < backlog.index("(Opus 5, 2026-09-07")
    assert "historical snapshot, not current instructions" in backlog
    for name in ("BACKLOG.md", "HANDOFF-opus5-2026-09-07.md"):
        assert "(cd website/frontend && npm run build:app) && scripts/dev_deploy.sh" in (
            ROOT / "docs" / name
        ).read_text()


def test_global_plan_date_includes_handoff_review_refresh():
    plan = (ROOT / "docs/PLAN.md").read_text()
    match = re.search(r"\*\*Zadnja posodobitev:\*\* (\d{4}-\d{2}-\d{2})", plan)
    assert match is not None
    assert match.group(1) >= "2026-09-28"
