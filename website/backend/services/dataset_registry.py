"""The dataset register — docs/design/19 §5, slice 1 (2026-09-06).

One entry per dataset the site can show: what collects it, which switch
turns collection off (where one exists), which pages show it by default,
what it depends on, and what it costs cold. The register is READ-ONLY in
this slice: `GET /api/datasets` publishes it, nothing stores a user's
choices yet (that is slice 2, with its own table and migration).

Three things already existed and this unifies them rather than adding a
fourth: the profile endpoint's section allowlist (`_PROFILE_SECTIONS`,
`_HEAVY_SECTIONS` with measured costs, `_parse_sections` that 400s on an
unknown key — players_profile_router.py), the formula registry's
"one entry per thing, a status, a surface" shape (formula_registry.py,
untyped), and `routes.data.json` as the page-key namespace. The profile
router now DERIVES its allowlist from here, so there is one list.

Rules the tests pin:
- keys are unique; `default_visible_on` ⊆ the SPA's route keys;
  `depends_on` ⊆ keys; `parity_key` is a `data-parity` the SPA renders;
- a collection toggle names something that really gates collection where
  telemetry originates (a Lua `isFeatureEnabled` section or a bot env
  switch), never a web-layer flag — a toggle that lives in the web layer
  lies about what the server sends (doc 19 §5);
- `cost_ms_cold` is a measurement, not an estimate: only the two profile
  sections that were timed carry one.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

REGISTRY_VERSION = "1.0"

CollectedBy = Literal["lua", "bot_parser", "importer", "derived"]


class DatasetDescriptor(BaseModel):
    """Every field is REQUIRED on the wire: the register is a closed list the
    SPA types by hand, and the manual-type drift guard reads the OpenAPI
    `required` list — a Python default would make the schema say "optional"
    for a key that is always sent. Defaults live in the constructors below."""
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    collected_by: CollectedBy
    #: The switch that turns COLLECTION off, at the origin: a Lua section
    #: name (`isFeatureEnabled("...")` in proximity_tracker.lua) or a bot
    #: env key. None = always collected (parser/importer output).
    collection_toggle: str | None
    #: Whether the designer default shows it (doc 19 §3: anonymous visitors
    #: always see the designer default).
    display_toggle_default: bool
    #: Whether a signed-in user may hide/show it (slice 3).
    user_overridable: bool
    #: Page keys from routes.data.json where it is shown by default.
    default_visible_on: list[str]
    #: Other dataset keys that must be collected for this one to mean
    #: anything (the informal "KIS needs proximity" rule, made checkable).
    depends_on: list[str]
    #: The endpoint that serves it, when one endpoint does.
    endpoint: str | None
    #: Measured cold cost of the section, in ms — only where it was timed.
    cost_ms_cold: int | None
    #: The `data-parity` attribute the SPA renders it under, when it does.
    parity_key: str | None


PROFILE_ENDPOINT = "/api/players/{identifier}/profile"
SESSION_ENDPOINT_BASICS = "/api/stats/session/{gaming_session_id}/basics"
SESSION_ENDPOINT_AWARDS = "/api/stats/session/{gaming_session_id}/awards"
SESSION_ENDPOINT_DETAIL = "/api/stats/session/{gaming_session_id}/detail"


def _profile(key: str, label: str, *, collected_by: CollectedBy = "bot_parser",
             parity: str | None = None, cost: int | None = None, shown: bool = True,
             toggle: str | None = None, depends: list[str] | None = None) -> DatasetDescriptor:
    return DatasetDescriptor(
        key=key, label=label, collected_by=collected_by, collection_toggle=toggle,
        display_toggle_default=shown, user_overridable=True,
        default_visible_on=["profile"] if shown else [],
        depends_on=depends or [], endpoint=PROFILE_ENDPOINT, cost_ms_cold=cost,
        parity_key=parity,
    )


def _session(key: str, label: str, *, endpoint: str, parity: str, collected_by: CollectedBy = "bot_parser",
             depends: list[str] | None = None, toggle: str | None = None) -> DatasetDescriptor:
    return DatasetDescriptor(
        key=key, label=label, collected_by=collected_by, collection_toggle=toggle,
        display_toggle_default=True, user_overridable=True,
        default_visible_on=["session-detail", "session-detail-date"], depends_on=depends or [],
        endpoint=endpoint, cost_ms_cold=None, parity_key=parity,
    )


def _lua(key: str, label: str, toggle: str, *, shown_on: list[str], parity: str | None = None,
         depends: list[str] | None = None) -> DatasetDescriptor:
    return DatasetDescriptor(
        key=key, label=label, collected_by="lua", collection_toggle=toggle,
        display_toggle_default=True, user_overridable=True,
        default_visible_on=shown_on, depends_on=depends or [], endpoint=None,
        cost_ms_cold=None, parity_key=parity,
    )


# ---------------------------------------------------------------------------
# Profile sections — the fourteen keys the profile endpoint accepts in
# `?sections=`. The two costs are the measurements in players_profile_router
# (dev, heaviest player, cold cache). Sections the SPA does not render are
# registered with display_toggle_default=False and no page.
PROFILE_SECTIONS: tuple[DatasetDescriptor, ...] = (
    _profile("identity", "identity and aliases", parity="profile.header"),
    _profile("skill", "rating and its components", collected_by="derived", parity="profile.rating-components"),
    _profile("streaks", "kill and death streaks", parity="profile.streaks"),
    _profile("weapons", "weapon breakdown", parity="profile.weapons"),
    _profile("hit_regions", "hit regions", collected_by="lua", toggle="hit_region_tracking",
             parity="profile.hit-regions", depends=["proximity_capture"]),
    _profile("movement", "movement", collected_by="lua", toggle="engagement_tracking",
             parity="profile.movement", depends=["proximity_capture"]),
    _profile("relationships", "rivals and duos", collected_by="derived", parity="profile.relationships"),
    _profile("maps", "per-map record", parity="profile.maps"),
    _profile("recent_matches", "recent rounds", parity="profile.recent"),
    _profile("aim", "aim summary", collected_by="lua", toggle="shot_fired", cost=16_887, shown=False,
             depends=["proximity_capture"]),
    _profile("advanced", "advanced timing", collected_by="lua", toggle="spawn_timing", cost=11_077,
             shown=False, depends=["proximity_capture"]),
    _profile("gather_summary", "gather summary", shown=False),
    _profile("nick_history", "nick history", shown=False),
    _profile("combat_timing", "combat timing", collected_by="lua", toggle="engagement_tracking",
             shown=False, depends=["proximity_capture"]),
)

# Session detail — the Stats 2.0 surfaces, each under its own parity key.
SESSION_SECTIONS: tuple[DatasetDescriptor, ...] = (
    _session("session_basics", "basics table", endpoint=SESSION_ENDPOINT_BASICS, parity="session.basics"),
    _session("session_awards", "session awards", endpoint=SESSION_ENDPOINT_AWARDS, parity="session.awards",
             collected_by="derived"),
    _session("session_scoreboard", "map-by-map scoreboard", endpoint=SESSION_ENDPOINT_DETAIL, parity="session.scoreboard"),
    _session("session_teams", "team attribution", endpoint=SESSION_ENDPOINT_DETAIL, parity="session.teams",
             collected_by="derived"),
    _session("session_story", "the session story", endpoint="/api/storytelling/session",
             parity="session.story", collected_by="derived", depends=["kill_impact"]),
    _session("session_players", "per-player drilldown", endpoint=SESSION_ENDPOINT_BASICS, parity="session.players"),
    _session("session_lives", "lives and spawns", endpoint=SESSION_ENDPOINT_DETAIL, parity="session.lives"),
    _session("session_mvp", "mvp and verdicts", endpoint=SESSION_ENDPOINT_DETAIL, parity="session.mvp",
             collected_by="derived"),
)

# Proximity capture — the Lua tracker's sections, each behind its own
# `isFeatureEnabled` switch on the game server. `proximity_capture` is the
# umbrella every derived metric depends on; PROXIMITY_ENABLED is the bot's
# import switch for the whole family.
PROXIMITY_DATASETS: tuple[DatasetDescriptor, ...] = (
    _lua("proximity_capture", "proximity capture (200 ms samples)", "PROXIMITY_ENABLED",
         shown_on=["proximity", "proximity-player", "proximity-replay", "proximity-teams", "spider-web"]),
    _lua("engagements", "combat engagements", "engagement_tracking",
         shown_on=["proximity", "proximity-player"], depends=["proximity_capture"]),
    _lua("kill_outcomes", "kill outcomes (gib / revive / tapout)", "kill_outcome_tracking",
         shown_on=["proximity", "proximity-player"], depends=["proximity_capture"]),
    _lua("hit_regions_capture", "hit regions", "hit_region_tracking",
         shown_on=["proximity-player"], depends=["proximity_capture"]),
    _lua("spawn_timing", "spawn timing", "spawn_timing",
         shown_on=["proximity"], depends=["proximity_capture"]),
    _lua("reactions", "reaction metrics", "reaction_tracking",
         shown_on=["proximity"], depends=["proximity_capture"]),
    _lua("crossfire", "crossfire opportunities", "crossfire_opportunities",
         shown_on=["proximity-teams"], depends=["proximity_capture", "engagements"]),
    _lua("shots_fired", "shots fired", "shot_fired",
         shown_on=["proximity-player"], depends=["proximity_capture"]),
    _lua("aim_lock", "aim lock windows", "aim_lock",
         shown_on=["proximity"], depends=["proximity_capture", "shots_fired"]),
    _lua("vehicle_progress", "vehicle progress and escorts", "objective_run_tracking",
         shown_on=["session-detail"], depends=["proximity_capture"]),
    DatasetDescriptor(
        key="kill_impact", label="kill impact (KIS)", collected_by="derived", collection_toggle=None,
        display_toggle_default=True, user_overridable=True,
        default_visible_on=["session-detail", "session-detail-date"],
        depends_on=["proximity_capture", "kill_outcomes"],
        endpoint="/api/storytelling/kill-impact", cost_ms_cold=None, parity_key="session.player.kis",
    ),
    DatasetDescriptor(
        key="spider_web", label="spider web (round reconstruction)", collected_by="derived", collection_toggle=None,
        display_toggle_default=True, user_overridable=True,
        default_visible_on=["spider-web"], depends_on=["proximity_capture"],
        endpoint="/api/replay/round/{round_id}/web", cost_ms_cold=None, parity_key=None,
    ),
)

DATASETS: tuple[DatasetDescriptor, ...] = PROFILE_SECTIONS + SESSION_SECTIONS + PROXIMITY_DATASETS


def get_registry() -> list[DatasetDescriptor]:
    return list(DATASETS)


def profile_section_keys() -> frozenset[str]:
    """The `?sections=` allowlist of the profile endpoint, derived here so
    the router and the register cannot disagree."""
    return frozenset(d.key for d in PROFILE_SECTIONS)


def heavy_profile_section_keys(threshold_ms: int = 5_000) -> frozenset[str]:
    """Sections a page should fetch on demand, from the measured cost."""
    return frozenset(d.key for d in PROFILE_SECTIONS if (d.cost_ms_cold or 0) >= threshold_ms)
