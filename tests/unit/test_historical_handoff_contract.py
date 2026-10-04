"""Keep the retained historical handoff distinct from current operating advice."""

import os
import re
import subprocess
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
        assert '(cd website/frontend && npm run build:app) && DEV_SRC_DIR="$PWD" scripts/dev_deploy.sh' in (
            ROOT / "docs" / name
        ).read_text()


def test_global_plan_date_includes_handoff_review_refresh():
    plan = (ROOT / "docs/PLAN.md").read_text()
    match = re.search(r"\*\*Zadnja posodobitev:\*\* (\d{4}-\d{2}-\d{2})", plan)
    assert match is not None
    assert match.group(1) >= "2026-10-04"


def test_current_backlog_and_historical_scope_are_unambiguous():
    backlog = (ROOT / "docs/BACKLOG.md").read_text()
    current = backlog.split("## Trenutna pozicija", 1)[1].split("\n- ", 2)[1]
    assert "2026-10-04" in current and "8e262684" in current
    plan = (ROOT / "docs/PLAN.md").read_text()
    assert "> Historical checkpoint below predates this actual-main synchronization:" not in plan


def test_documented_recipe_passes_built_worktree_to_deploy(tmp_path):
    root = tmp_path / "work tree"
    (root / "website/frontend").mkdir(parents=True)
    (root / "scripts").mkdir()
    commands = tmp_path / "commands"
    commands.mkdir()
    npm = commands / "npm"
    npm.write_text('#!/bin/sh\nprintf "build:%s\\n" "$PWD"\n')
    npm.chmod(0o755)
    deploy = root / "scripts/dev_deploy.sh"
    deploy.write_text('#!/bin/sh\nprintf "source:%s\\ntarget:%s\\n" "${DEV_SRC_DIR:-wrong-primary-checkout}" "$1"\n')
    deploy.chmod(0o755)
    git = commands / "git"
    git.write_text('#!/bin/sh\nprintf "approved-commit\\n"\n')
    git.chmod(0o755)
    for name in ("HANDOFF-opus5-2026-09-07.md", "BACKLOG.md"):
        text = (ROOT / "docs" / name).read_text()
        recipe = re.search(r'`(\(cd website/frontend && npm run build:app\)[^`]+)`', text).group(1)
        result = subprocess.run(['bash', '-c', recipe], cwd=root, text=True,
                                capture_output=True, check=True,
                                env={**os.environ, 'PATH': f'{commands}:{os.environ["PATH"]}'})
        assert result.stdout.splitlines() == [
            f'build:{root}/website/frontend', f'source:{root}', 'target:approved-commit',
        ]


def test_squash_lesson_follows_all_newer_lessons():
    text = (ROOT / "docs/AGENT_LOG.md").read_text()
    position = text.index('**2026-09-20 · Squash merge status')
    for match in re.finditer(r'\*\*(2026-\d\d-\d\d) ·', text):
        if match.group(1) > '2026-09-20':
            assert match.start() < position


def test_resume_explicitly_identifies_local_only_retrieval():
    plan = (ROOT / "docs/PLAN.md").read_text()
    current = plan.split('> Historical checkpoint below', 1)[0]
    assert 'LOCAL-ONLY runtime resume' in current
    assert '/home/samba/share/slomix-astra-runtime-integration-20260926' in current
    assert 'refactor/db-runtime-team-assignment-20260926' in current
    assert 'git -C' in current and '1986d671^{commit}' in current
    assert 'not fetchable from GitHub' in current
