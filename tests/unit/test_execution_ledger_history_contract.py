"""Keep the preserved execution ledger subordinate to current runtime work."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_old_resume_is_explicitly_historical():
    plan = (ROOT / "docs/PLAN.md").read_text()
    assert "**Historical resume instructions (2026-09-08, superseded):**" in plan
    assert "**Resume here:** review current checks/findings on #964" not in plan
    assert "runtime resume 1986d671" in plan[:1500]


def test_historical_label_does_not_cover_newer_backlog_entries():
    backlog = (ROOT / "docs/BACKLOG.md").read_text()
    assert "**Historical entries below are not current action instructions.**" not in backlog
    assert "Only the September 7/8 entries immediately above are historical" in backlog
    assert backlog.index("(Astra, 2026-09-20) R04j") < backlog.index(
        "**2026-09-08 (Astra, resume checkpoint):**"
    )


def test_preserved_september_seven_lessons_follow_later_runtime_lessons():
    log = (ROOT / "docs/AGENT_LOG.md").read_text()
    later = log.index("**2026-09-20 · Content reconciliation")
    for lesson in (
        "Commit, artifact, process and data are separate evidence.",
        "Canonical import is earlier than data finalization.",
        "Record the safety-policy snapshot when reviewing tooling.",
        "Configured Codex hooks are not necessarily active.",
    ):
        assert log.count(lesson) == 1
        assert later < log.index(lesson)
