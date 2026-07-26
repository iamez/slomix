"""Release-config contract (Codex REL-01).

A release config is the only thing standing between "deploy the new code"
and "deploy the new code against a schema that cannot serve it". These
tests make the three ways that goes wrong impossible to merge:

1. the config for the current version does not exist at all — which is
   exactly how v1.27.0 shipped 063 with no config;
2. the config names a migration file that is not in the repo;
3. a migration the code needs is missing from the config — the runner's
   `--only` preflight then refuses mid-deploy, after services have stopped.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

CONFIG_DIR = Path("scripts/release_configs")
MIGRATIONS_DIR = Path("migrations")
CLAUDE_MD = Path("CLAUDE.md")

# Migrations whose absence breaks the CURRENT code, not merely the schema.
# Keep this list in step with the code that reads the objects they create.
CODE_REQUIRES = {
    "063_kis_gaming_session_id.sql":
        "storytelling_kill_impact.gaming_session_id — read as a WHERE filter "
        "by useless-defense, PWC crossfire and enabler",
    "064_backfill_kis_gaming_session_id.sql":
        "without the backfill that column is ~87% NULL and those panels "
        "return empty for every historical session",
    "065_dedup_revive_weapon_accuracy.sql":
        "round identity + UNIQUE that the parser's ON CONFLICT targets name",
}


def _current_version() -> str:
    text = CLAUDE_MD.read_text(encoding="utf-8")
    m = re.search(r"\*\*Version\*\*:\s*([0-9]+\.[0-9]+\.[0-9]+)", text)
    assert m, "could not read the project version from CLAUDE.md"
    return m.group(1)


def _configs() -> list[Path]:
    return sorted(CONFIG_DIR.glob("v*.sh"))


def _newest_config() -> Path:
    """The config that will carry whatever is on main right now.

    Between releases, CLAUDE.md still names the LAST released version while
    main already holds the next release's code, so the current-version config
    is the wrong thing to check for code requirements — the newest one is.
    """
    def key(p: Path) -> tuple[int, ...]:
        return tuple(int(x) for x in p.stem.lstrip("v").split("."))

    configs = _configs()
    assert configs, "scripts/release_configs/ has no configs at all"
    return max(configs, key=key)


def _migrations_in(config: Path) -> list[str]:
    body = config.read_text(encoding="utf-8")
    block = re.search(r"MIGRATIONS=\((.*?)\)", body, re.S)
    if not block:
        return []
    return re.findall(r'"([^"]+\.sql)"', block.group(1))


def test_a_config_exists_for_the_current_version():
    """v1.27.0 shipped migration 063 with no config at all; the next deploy
    would then have run current code against a schema without it."""
    version = _current_version()
    path = CONFIG_DIR / f"v{version}.sh"
    assert path.exists(), (
        f"no release config for the current version v{version}. "
        f"Create {path} listing the migrations this release needs."
    )


@pytest.mark.parametrize("config", _configs(), ids=lambda p: p.name)
def test_every_named_migration_exists(config):
    for name in _migrations_in(config):
        assert (MIGRATIONS_DIR / name).exists(), (
            f"{config.name} names {name}, which is not in migrations/"
        )


def test_newest_config_carries_every_code_required_migration():
    """The runner refuses `--only` while anything outside the set is
    un-applied, so an incomplete list aborts the deploy AFTER services stop."""
    config = _newest_config()
    listed = set(_migrations_in(config))
    missing = {m: why for m, why in CODE_REQUIRES.items() if m not in listed}
    assert not missing, (
        f"{config.name} omits migrations the current code depends on:\n"
        + "\n".join(f"  {m}: {why}" for m, why in missing.items())
    )


def _version_of(config: Path) -> tuple[int, ...]:
    return tuple(int(x) for x in config.stem.lstrip("v").split("."))


# TRUSTED_HOSTS became a hard start-up requirement in v1.26.0 (host/path
# security). Older tags predate it and must not be judged against it.
_TRUSTED_HOSTS_SINCE = (1, 26, 0)


@pytest.mark.parametrize(
    "config",
    [c for c in _configs() if _version_of(c) >= _TRUSTED_HOSTS_SINCE],
    ids=lambda p: p.name,
)
def test_configs_since_1_26_declare_trusted_hosts(config):
    """main.py resolves TRUSTED_HOSTS at import under the production posture
    and raises without it — the web service simply will not start."""
    assert "TRUSTED_HOSTS=" in config.read_text(encoding="utf-8"), (
        f"{config.name} does not set TRUSTED_HOSTS; deploying this tag would "
        f"leave the web service unable to start"
    )


def test_no_migration_is_silently_absent_from_every_config():
    """A migration in the repo that no config ever names can only reach a
    target by hand. Numbers below the oldest config are exempt."""
    named: set[str] = set()
    for config in _configs():
        named.update(_migrations_in(config))
    numbered = {
        p.name for p in MIGRATIONS_DIR.glob("*.sql")
        if re.match(r"^0\d\d_", p.name)
    }
    oldest_named = min((n[:3] for n in named), default="999")
    orphans = sorted(
        n for n in numbered if n[:3] >= oldest_named and n not in named
    )
    assert not orphans, (
        "migrations no release config ever ships: " + ", ".join(orphans)
    )
