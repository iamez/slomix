"""Run the pre-push hook against real commits and see what it refuses.

A test that matches the hook's regexes against strings proves the regexes are
what they are. This builds a throwaway repository, commits a file, invokes the
hook the way git does — refs on stdin — and checks the exit code. That is the
thing the guard has to do.

⛔ WHY IT EXISTS. On 2026-08-22 a research script carrying the dev database
password as an `os.environ.get(..., default)` fallback was committed and pushed
to this public repository. The hook ran. Its pattern matched `NAME = value` and
the offending line was `os.environ.get("POSTGRES_PASSWORD", "…")`, where the
name and the value are separated by `", "` — so it saw nothing.

`git log -S` afterwards found the same literal in 66 commits reaching back to
2025-11-05. The fallback was a habit, and habits need a guard that fires rather
than a rule someone remembers.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / "scripts" / "git-hooks" / "pre-push"
ZERO = "0" * 40

#: ⭐ Assembled at run time, never written as one literal.
#:
#: The first version of this file spelled its fixtures out, and the hook blocked
#: its own push — which is the strongest evidence the guard works and also the
#: reason it cannot be written that way. Every fixture below interpolates these,
#: so no line in this file matches the patterns it is testing: the value lands
#: in the source as `"{_FAKE_SECRET}"`, and braces are not in the character
#: class the hook looks for.
#:
#: They are also not credentials. Nothing here has ever opened anything.
_FAKE_SECRET = "".join(("wjXK", "7", "pQ2", "mLd", "0", "vRt"))
_FAKE_TOKEN = "".join(("MTIz", "NDU2", "Nzg5", "MC5h", "YmNk", "ZWZn"))


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository with an `origin/main` for the hook to diff against."""
    path = tmp_path / "repo"
    path.mkdir()
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "t@example.invalid")
    _git(path, "config", "user.name", "test")
    (path / "seed.txt").write_text("seed\n")
    _git(path, "add", "seed.txt")
    _git(path, "commit", "-qm", "seed")
    # The hook falls back to `origin/main` when the remote sha is all zeros.
    _git(path, "update-ref", "refs/remotes/origin/main", _git(path, "rev-parse", "HEAD"))
    return path


def run_hook(repo: Path, filename: str, content: str) -> subprocess.CompletedProcess:
    (repo / filename).write_text(content)
    _git(repo, "add", filename)
    _git(repo, "commit", "-qm", f"add {filename}")
    head = _git(repo, "rev-parse", "HEAD")
    return subprocess.run(
        ["bash", str(HOOK), "origin", "https://example.invalid/repo.git"],
        input=f"refs/heads/main {head} refs/heads/main {ZERO}\n",
        capture_output=True, text=True, cwd=repo,
    )


# --- what must be refused ---------------------------------------------------

REFUSED = {
    "env_default": (
        "import os\n"
        "def connect():\n"
        '    return dict(password=os.environ.get("POSTGRES_PASSWORD", '
        f'"{_FAKE_SECRET}"))\n'
    ),
    "getenv_default": (
        "import os\n"
        f'TOKEN = os.getenv("DISCORD_BOT_TOKEN", "{_FAKE_TOKEN}")\n'
    ),
    "keyword_literal": (
        f'DB = dict(host="127.0.0.1", password="{_FAKE_SECRET}")\n'
    ),
}

#: `NAME=value` is check 4's territory and check 4 WARNS on purpose: its pattern
#: cannot tell `DISCORD_BOT_TOKEN=your_token_here` in install.sh's help text
#: from a real token, and it tripped on this hook's own first push. Making it
#: block would break `.env.example` and every doc that shows a connection
#: string. The new checks block instead because they are narrow enough to.
WARNED_NOT_BLOCKED = {
    "plain_assignment": f"POSTGRES_PASSWORD={_FAKE_SECRET}\n",
}


@pytest.mark.parametrize("name", sorted(REFUSED))
def test_hook_refuses_a_hardcoded_credential(repo: Path, name: str) -> None:
    result = run_hook(repo, f"{name}.py", REFUSED[name])
    assert result.returncode != 0, (
        f"{name}: the hook allowed a hardcoded credential\n{result.stderr}"
    )


@pytest.mark.parametrize("name", sorted(WARNED_NOT_BLOCKED))
def test_the_broad_pattern_warns_without_blocking(repo: Path, name: str) -> None:
    """The deliberate split: broad and noisy warns, narrow and certain blocks."""
    result = run_hook(repo, f"{name}.py", WARNED_NOT_BLOCKED[name])
    assert result.returncode == 0, "check 4 must not block; that is its design"
    assert "may contain a credential" in result.stderr


def test_the_refusal_says_what_to_do_instead(repo: Path) -> None:
    """A guard that only says no gets `--no-verify`d."""
    result = run_hook(repo, "bad.py", REFUSED["env_default"])
    assert "no fallback" in result.stderr.lower()
    assert "environment" in result.stderr.lower()


# --- what must still get through --------------------------------------------

ALLOWED = {
    # The idioms this repository already uses everywhere else.
    "empty_default": (
        'import os\n'
        'password = os.environ.get("POSTGRES_PASSWORD", "")\n'
    ),
    "chained_empty_default": (
        'import os\n'
        'password = (os.environ.get("POSTGRES_PASSWORD")\n'
        '            or os.environ.get("PGPASSWORD", ""))\n'
    ),
    "helper_call": 'password = _require_password()\n',
    "placeholder": 'POSTGRES_PASSWORD=your_secure_password_here\n',
    "redacted_doc": "PGPASSWORD='REDACTED_DB_PASSWORD' psql -h localhost\n",
    "ci_value": 'SESSION_SECRET = "ci-test-secret-not-for-production"\n',
    "shell_expansion": 'PGPASSWORD="${DB_PASS}" psql -h localhost\n',
}


@pytest.mark.parametrize("name", sorted(ALLOWED))
def test_hook_allows_the_safe_idioms(repo: Path, name: str) -> None:
    """⚠️ The half that matters most. A guard that blocks ordinary work is a
    guard someone switches off — which is why check 4 stayed a warning."""
    result = run_hook(repo, f"{name}.py", ALLOWED[name])
    assert result.returncode == 0, (
        f"{name}: the hook refused a safe idiom\n{result.stderr}"
    )
