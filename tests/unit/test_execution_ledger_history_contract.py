"""Keep the preserved execution ledger subordinate to current runtime work."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_backlog_current_position_uses_latest_local_plan():
    text = (ROOT / "docs/BACKLOG.md").read_text()
    current = text.split("## Trenutna pozicija", 1)[1].split("\n## ", 1)[0]
    assert "latest PLAN" in current
    assert "latest checkpoint at the top" in current
    assert "/home/samba/share/slomix-astra-runtime-integration-20260926" in current
    assert not re.search(r"#\d+", current), "Current position must route to PLAN, not duplicate a stale PR queue"
    assert "1986d671" not in current and "8e262684" not in current


def test_old_resume_is_explicitly_historical():
    plan = (ROOT / "docs/PLAN.md").read_text()
    assert "**Historical resume instructions (2026-09-08, superseded):**" in plan
    assert "**Resume here:** review current checks/findings on #964" not in plan
    current = plan.split("## Historical checkpoints", 1)[0]
    assert "integration checkpoint8e262684" in current
    introduction = plan.split('## Astra execution ledger — historical authority', 1)[1].split(
        '**2026-09-08 evidence refresh:**', 1
    )[0]
    assert 'and runtime commit 1986d671' not in introduction
    assert 'only from the latest checkpoint at the top' in ' '.join(introduction.split())


@pytest.mark.parametrize('name', [
    'KNOWN_ISSUES.md', 'HANDOFF-astra.md', 'HANDOFF-astra-inventory.md', 'HANDOFF-next.md',
])
def test_every_ledger_entry_point_routes_to_current_plan(name):
    text = (ROOT / 'docs' / name).read_text()
    header = text.split('> **Current routing — 2026-10-04.**', 1)
    assert len(header) == 2
    route = header[1].split('\n\n', 1)[0]
    assert 'latest checkpoint in `docs/PLAN.md`' in ' '.join(route.replace('>', '').split())
    assert 'historical' in route


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


def test_continuation_prompt_has_separate_first_session_scope():
    text = (ROOT / 'docs/prompts/astra_kickoff.md').read_text()
    introduction = text.split('## First session only', 1)[0]
    assert 'For continuation, read `docs/PLAN.md` latest checkpoint first' in introduction
    assert 'is historical evidence, not current queue authority' in introduction
    assert '## First session only (historical onboarding block)' in text
    short = text.split('## Short form (later sessions)', 1)[1]
    assert 'docs/PLAN.md' in short
    assert 'HANDOFF §2' not in short
    assert 'Do not repeat hour-one discovery' in short


def test_handoff_preserves_narrow_review_exception_without_authorizing_execution():
    text = (ROOT / 'docs/HANDOFF-next.md').read_text().split('## ', 1)[0]
    assert '**Current routing — 2026-10-04.** Read the latest checkpoint' in text
    assert '**Historical consolidation checkpoint — 2026-09-20.**' in text
    assert 'it uses forbidden push options' not in text
    assert 'AGENTS.md' in text and 'narrow written exception' in text
    assert 'Astra did not execute' in text


def test_resume_explicitly_identifies_local_only_retrieval():
    plan = (ROOT / 'docs/PLAN.md').read_text()
    boundary = '## Historical checkpoints — superseded, retain evidence as of each date'
    assert boundary in plan
    current = plan.split(boundary, 1)[0]
    assert 'LOCAL-ONLY runtime resume' in current
    assert '/home/samba/share/slomix-astra-runtime-integration-20260926' in current
    assert 'refactor/db-runtime-team-assignment-20260926' in current
    assert 'git -C' in current and '8e262684^{commit}' in current
    assert 'not fetchable from GitHub' in current
