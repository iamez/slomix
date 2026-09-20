"""Keep the retained historical handoff distinct from current operating advice."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_historical_handoff_is_dated_and_its_companion_is_available():
    """The retained snapshot must not masquerade as the current plan."""
    handoff = (ROOT / "docs/HANDOFF-opus5-2026-09-07.md").read_text()
    assert "Historical snapshot, not current operating instructions" in handoff
    assert "#952, #955 and #958 landed after v1.45.0" in handoff
    assert (ROOT / "docs/HANDOFF-astra.md").is_file()


def test_historical_cleanup_advice_is_not_a_static_timer_enable_recipe():
    """A static unit is not diagnosed by an inapplicable enable command."""
    for name in ("HANDOFF-opus5-2026-09-07.md", "BACKLOG.md"):
        text = " ".join((ROOT / "docs" / name).read_text().split())
        assert "enable --now systemd-tmpfiles-clean.timer" not in text
    handoff = (ROOT / "docs/HANDOFF-opus5-2026-09-07.md").read_text()
    assert "--rotate --vacuum-size=200M" in handoff
    assert "explicit journald restart" in handoff
