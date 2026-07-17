"""Central registry of every scoring formula in the platform (owner answer B6).

One place that answers: which formulas exist, what version is live, where the
code lives, and where the numbers surface. Services keep owning their own
FORMULA_VERSION constants — the registry IMPORTS live versions so it can never
drift from the source of truth; entries without a constant carry a static
version reviewed with the formula itself.

Statuses:
  live      — computed in production paths and user-visible
  shadow    — computed and stored/exposed for owner review, NOT user-visible;
              awaiting calibration/promotion gates
  research  — backtest scripts only; tables reviewed by the owner, no surface
  proposed  — designed/named but not implemented yet
"""
from __future__ import annotations

REGISTRY_VERSION = "1.0"


def _s_effort_version() -> str:
    """Live version straight from the owning module — deliberately NO
    fallback: a broken import fails loudly instead of reporting a stale
    hand-copied version (codex, PR #463). Static imports (no importlib)
    keep security scanners happy."""
    from website.backend.services.s_effort_service import FORMULA_VERSION
    return FORMULA_VERSION


def _ois_version() -> str:
    from website.backend.services.storytelling.ois import FORMULA_VERSION
    return FORMULA_VERSION


def _ssr_version() -> str:
    from website.backend.services.ssr_service import FORMULA_VERSION
    return FORMULA_VERSION


def _kis_version() -> str:
    from website.backend.services.storytelling.kis import FORMULA_VERSION
    return FORMULA_VERSION


def _prox_version() -> str:
    from website.backend.services.prox_scoring import FORMULA_VERSION
    return FORMULA_VERSION


def _prediction_published() -> bool:
    """Whether match predictions are actually posted to Discord (the promotion
    flag). The registry derives the prediction status/surface from this so it
    reports the real production state after PREDICTION_PUBLISH_ENABLED is
    flipped, instead of a hard-coded 'shadow' (Codex #511)."""
    import os
    return os.getenv("PREDICTION_PUBLISH_ENABLED", "false").lower() == "true"


def get_registry() -> list[dict]:
    return [
        {
            "name": "et_rating",
            "version": "v2.0",
            "status": "live",
            "module": "website/backend/services/skill_rating_service.py",
            "surface": "/api/skill/leaderboard, /api/skill/player/*, SkillRating page",
            "summary": "15 percentile-normalized metrics (9 PCS + 6 proximity), "
                       "constant 0.15; population is bot-free and is_valid-gated. "
                       "Known bias: mixes telemetry epochs and median ≈0.57 (not "
                       "0.50) — corrected in the et_performance_v3 shadow.",
        },
        {
            "name": "et_performance_v3",
            "version": "et-perf-v3.0-shadow",
            "status": "shadow",
            "module": "website/backend/services/skill_rating_v3.py",
            "surface": "/api/skill/v3-shadow (owner review only)",
            "summary": "AUD-007 fix: same absolute weights, no constant, "
                       "directed midrank percentiles over a common 2026-03-24+ "
                       "telemetry epoch → population MEAN exactly 0.50 (median is "
                       "empirical, near but not forced to 0.50). Shadow until "
                       "promotion gates pass (remediation plan §6).",
        },
        {
            "name": "s_effort",
            "version": _s_effort_version(),
            "status": "live",
            "module": "website/backend/services/s_effort_service.py",
            "surface": "/api/skill/s-effort, player_skill_history scope='session'",
            "summary": "Session rating / pool strength (variant A, leave-one-out); "
                       "s.performance normalizes by lifetime vs POOL_NEUTRAL.",
        },
        {
            "name": "adjusted_lifetime",
            "version": _s_effort_version(),
            "status": "live",
            "module": "website/backend/services/s_effort_service.py",
            "surface": "/api/skill/adjusted-lifetime",
            "summary": "SRS-style iteration: AVG over sessions of "
                       "(session rating + pool delta), damped, 5 rounds.",
        },
        {
            "name": "kis",
            "version": _kis_version(),
            "status": "live",
            "module": "website/backend/services/storytelling/kis.py",
            "surface": "/api/storytelling/*, Smart Stats, Story, momentum",
            "summary": "Kill Impact Score: base x 11 context multipliers "
                       "(carrier/push/crossfire/spawn/outcome/class/distance/"
                       "health/alive/reinf), soft cap 5.0.",
        },
        {
            "name": "box_scoring",
            "version": "v1",
            "status": "live",
            "module": "website/backend/services/box_scoring_service.py",
            "surface": "BOX score panel, session scoring (canonical 2-pt scale)",
            "summary": "Oksii-style stopwatch map scoring; the session-score "
                       "canon every surface agrees on.",
        },
        {
            "name": "krogt",
            "version": "v1",
            "status": "live",
            "module": "website/backend/routers/proximity_scoring.py",
            "surface": "proximity leaderboards KROGT tab",
            "summary": "Composite proximity round-contribution score.",
        },
        {
            "name": "prox_score_web",
            "version": _prox_version(),
            "status": "live",
            "module": "website/backend/services/prox_scoring.py",
            "surface": "/api/proximity scoring endpoints",
            "summary": "combat 0.40 / team 0.35 / gamesense 0.25, "
                       "min 10 engagements.",
        },
        {
            "name": "prox_score_bot",
            "version": "v1",
            "status": "live",
            "module": "bot/services/proximity_session_score_service.py",
            "surface": "Discord session summaries",
            "summary": "7-weight session proximity score, min 3 engagements. "
                       "NOTE: intentionally different from prox_score_web; "
                       "registry exists to keep that visible.",
        },
        {
            "name": "good_night_index",
            "version": "phase-1",
            "status": "live",
            "module": "website/backend/services/good_night_service.py",
            "surface": "Good Night session summary",
            "summary": "Evening-as-product index (Good Night Engine plan).",
        },
        {
            "name": "form_index",
            "version": "v1",
            "status": "live",
            "module": "website/backend/routers/skill_router.py (composite)",
            "surface": "/api/skill/composite, Form page (legacy JS)",
            "summary": "One trackable form number per player (rank-vs-self + "
                       "proximity impact factor).",
        },
        {
            "name": "prediction_engine",
            "version": "heuristic-v1.1",
            "status": "live" if _prediction_published() else "shadow",
            "module": "bot/services/prediction_engine.py",
            "surface": ("Discord predictions (published; PREDICTION_PUBLISH_ENABLED=true)"
                        if _prediction_published() else
                        "shadow only — stored for calibration, not published "
                        "(PREDICTION_PUBLISH_ENABLED=false)"),
            "summary": "Experimental heuristic estimate: H2H 45% + form 30% + "
                       "map 25%, mapped to 30-70% band, valid/human rounds "
                       "before prediction time only. NOT a calibrated "
                       "probability — publishes only after >=100 resolved "
                       "shadow predictions pass Brier/reliability gates "
                       "(remediation plan §5).",
        },
        {
            "name": "clutch_value",
            "version": "clutch-v0",
            "status": "research",
            "module": "scripts/backtest_clutch_detector.py",
            "surface": "owner backtest tables only",
            "summary": "Sum of KIS chain x 1vN multiplier x objective stake x "
                       "outcome. v1 adds time-remaining stake, teammate "
                       "proximity and own-goal detection (owner answer A1).",
        },
        {
            "name": "target_acquisition",
            "version": "target-acq-v0.1",
            "status": "research",
            "module": "scripts/backtest_target_acquisition.py",
            "surface": "owner backtest tables; SSR candidate input",
            "summary": "aim-lock onset -> kill median, group-relative; "
                       "USABLE verdict (spread 275ms, split-half +0.81).",
        },
        {
            "name": "spawn_readiness",
            "version": "target-acq-v0.1",
            "status": "research",
            "module": "scripts/backtest_target_acquisition.py",
            "surface": "owner backtest tables; SSR candidate input",
            "summary": "time-to-first-move per life; USABLE verdict "
                       "(spread 326ms, split-half +0.85).",
        },
        {
            "name": "obj_deadtime",
            "version": "obj-deadtime-v0.1",
            "status": "research",
            "module": "scripts/backtest_obj_phase_deadtime.py",
            "surface": "owner backtest tables; xOV stake component candidate",
            "summary": "Defender-aliveness case-control: advance vs near-miss "
                       "diff +0.072 (informative).",
        },
        {
            "name": "opening_duels",
            "version": "duels-v0.1",
            "status": "research",
            "module": "scripts/backtest_opening_duels.py",
            "surface": "owner backtest tables; SSR candidate input",
            "summary": "Entry stat: rate of scoring vs being the round's "
                       "FIRST kill (net per rounds present). Owner B6 mandate "
                       "('izmisli še kake formule'); dev table shows a real "
                       "spread (bronzelow +13.8% .. KaNii -9.6%).",
        },
        {
            "name": "trade_discipline",
            "version": "duels-v0.1",
            "status": "research",
            "module": "scripts/backtest_opening_duels.py",
            "surface": "owner backtest tables; SSR candidate input",
            "summary": "Share of own deaths avenged within the trade window "
                       "(lua_trade_kill original_victim / kill_outcome deaths) "
                       "— the team-play view of dying.",
        },
        {
            "name": "ois",
            "version": _ois_version(),
            "status": "live",
            "module": "website/backend/services/storytelling/ois.py",
            "surface": "SSR input; Smart Stats Comp Skill board",
            "summary": "Objective Impact Score — KIS-scale credit for NON-KILL "
                       "objective acts (doc return 3.0 x speed, defuse 2.5, "
                       "construction 2.0 x contested). Kept OUTSIDE KIS so KIS "
                       "stays a pure kill score (owner answer A2).",
        },
        {
            "name": "situational_skill_rating",
            "version": _ssr_version(),
            "status": "live",
            "module": "website/backend/services/ssr_service.py",
            "surface": "/api/skill/ssr; proximity Comp Skill tab; profile "
                       "Reactions card; Smart Stats board",
            "summary": "Per-player aggregate of group-relative percentiles "
                       "(8 components): clutch KIS/session, situational KIS "
                       "share, OIS/session, kill permanence, target "
                       "acquisition, spawn readiness, opening net, trade "
                       "discipline (min 5 sessions / 3 components; partial "
                       "coverage averaged over what exists). Owner answer A4.",
        },
    ]


def get_formula(name: str) -> dict | None:
    for entry in get_registry():
        if entry["name"] == name:
            return entry
    return None
