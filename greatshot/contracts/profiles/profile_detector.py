"""Profile detection and mapping facade for demo parsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from greatshot.contracts.profiles import etlegacy_main


@dataclass(frozen=True)
class DemoProfile:
    profile_id: str
    profile_name: str

    def canonical_weapon(self, raw_value: str | None) -> str:
        return etlegacy_main.canonical_weapon(raw_value)

    def canonical_team(self, raw_value: str | None) -> str:
        return etlegacy_main.canonical_team(raw_value)


def detect_profile(config_values: Dict[str, Any], match_stats: Dict[str, Any]) -> DemoProfile:
    """
    Detect parsing profile.

    For now we default to ET:Legacy if hints contain "legacy".
    The function is intentionally isolated so ETPro/other mods can be added later
    without touching scanner logic.
    """
    haystack_parts = [
        str(config_values.get("gamename", "")),
        str(config_values.get("fs_game", "")),
        str(match_stats.get("mod", "")),
        str(match_stats.get("gameplay", "")),
    ]
    haystack = " ".join(haystack_parts).lower()

    if "legacy" in haystack or "et" in haystack:
        return DemoProfile(
            profile_id=etlegacy_main.PROFILE_ID,
            profile_name=etlegacy_main.PROFILE_NAME,
        )

    return DemoProfile(
        profile_id=etlegacy_main.PROFILE_ID,
        profile_name=etlegacy_main.PROFILE_NAME,
    )
