"""
Player-related endpoints: search, link, profile, compare, leaderboard, matches, form, rounds.

Extracted from api.py to reduce file size and improve maintainability.
"""

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from shared.round_time import round_duration_sql
from shared.season_manager import SeasonManager
from shared.utils import escape_like_pattern
from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.middleware.auth_helpers import require_ajax_csrf_header as _require_ajax_csrf_header
from website.backend.rate_limit import limiter
from website.backend.routers.api_helpers import (
    batch_resolve_display_names,
    calculate_player_achievements,
    fetch_identity_links,
    resolve_display_name,
    resolve_player_guid,
)

router = APIRouter()
logger = get_app_logger("api.players")


class LinkPlayerRequest(BaseModel):
    player_name: str


#: ⛔ `list[str]`, not a wrapper object. The handler returns a bare list and
#: the SPA reads it as one; declaring an envelope here would silently reshape
#: the payload. The names may include `[BOT]` entries — a deliberate decision
#: recorded in the ordering comment below, not an oversight: `[BOT]` is a
#: naming convention, and filtering on it would be treating it as identity.
@router.get("/player/search", response_model=list[str])
@limiter.limit("30/minute")
async def search_player(request: Request, query: str, db: DatabaseAdapter = Depends(get_db)):
    """Search for player aliases. Rate-limited to deter enumeration."""
    if len(query) < 2:
        return []

    # Escape LIKE wildcards (%, _) in user input to prevent SQL injection
    safe_query = escape_like_pattern(query)

    # Case-insensitive search (ILIKE is Postgres specific).
    #
    # Ordered by RELEVANCE, not alphabetically. Alphabetical put anything whose
    # name starts with a bracket or digit first, which in practice meant bots:
    # searching "vid" returned three `[BOT]vid` entries — 6, 60 and 19 rounds,
    # none played since March — ahead of the actual player `vid`, who has 2,477
    # rounds and played yesterday. Whoever typed the name got the wrong profile
    # offered first (master review P1-4).
    #
    # Exact name wins, then a prefix match, then whoever actually plays. The
    # round count is the tiebreak that sinks stale bot aliases without hard-
    # coding a `[BOT]` rule, which would be a naming convention masquerading as
    # a filter.
    #
    # Two CTEs rather than one GROUP BY, because a guid carries many aliases
    # (Codex on #606):
    #   matched   one row per (guid, alias) that matched, with its own rank.
    #   best      the alias to rank and SHOW: the best-ranked one, then the
    #             most-used. Ranking or displaying MAX(player_name) picks the
    #             lexicographically largest alias, which need not be the one
    #             the user typed — an exact match could land in the "no match"
    #             bucket, and searching "vid" listed a guid as `[BOT]wajs`
    #             because that was its largest alias. The name here is only a
    #             FALLBACK: batch_resolve_display_names() below prefers a
    #             canonical display name where one exists.
    #   activity  counts ALL rounds for those guids, not only the rows the
    #             ILIKE kept. Counting matched rows alone under-ranks anyone
    #             who has since changed name.
    sql = """
        WITH matched AS (
            SELECT player_guid,
                   player_name,
                   CASE
                       WHEN LOWER(player_name) = LOWER(?) THEN 0
                       WHEN LOWER(player_name) LIKE LOWER(?) THEN 1
                       ELSE 2
                   END AS match_rank,
                   COUNT(*) AS alias_rounds
            FROM player_comprehensive_stats
            WHERE player_name ILIKE ?
            GROUP BY player_guid, player_name
        ),
        best AS (
            SELECT DISTINCT ON (player_guid)
                   player_guid, player_name, match_rank
            FROM matched
            ORDER BY player_guid, match_rank, alias_rounds DESC, player_name
        ),
        activity AS (
            SELECT player_guid, COUNT(*) AS total_rounds
            FROM player_comprehensive_stats
            WHERE player_guid IN (SELECT player_guid FROM best)
            GROUP BY player_guid
        )
        SELECT b.player_guid, b.player_name
        FROM best b
        JOIN activity a ON a.player_guid = b.player_guid
        ORDER BY b.match_rank, a.total_rounds DESC, b.player_name
        LIMIT 10
    """
    rows = await db.fetch_all(
        sql, (query, f"{safe_query}%", f"%{safe_query}%")
    )
    name_map = await batch_resolve_display_names(
        db, [(guid, player_name or "Unknown") for guid, player_name in rows]
    )
    return [name_map.get(guid, player_name or "Unknown") for guid, player_name in rows]


@router.post("/player/link")
async def link_player(
    request: Request, payload: LinkPlayerRequest, db: DatabaseAdapter = Depends(get_db)
):
    """Link Discord account to player alias"""
    _require_ajax_csrf_header(request)
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    discord_id = int(user["id"])

    # Check if already linked
    existing = await db.fetch_one(
        "SELECT player_name FROM player_links WHERE discord_id = ?", (discord_id,)
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"Already linked to {existing[0]}")

    # Verify player exists in stats
    stats = await db.fetch_one(
        "SELECT 1 FROM player_comprehensive_stats WHERE player_name = ? LIMIT 1",
        (payload.player_name,),
    )
    if not stats:
        raise HTTPException(status_code=404, detail="Player alias not found in stats")

    # Insert link
    await db.execute(
        "INSERT INTO player_links (discord_id, player_name, linked_at) VALUES (?, ?, NOW())",
        (discord_id, payload.player_name),
    )

    # Update session
    user["linked_player"] = payload.player_name
    request.session["user"] = user

    return {"status": "success", "linked_player": payload.player_name}


@router.get("/stats/live-session")
async def get_live_session(db: DatabaseAdapter = Depends(get_db)):
    """
    Get current live session status.
    """
    # Check if session is active (last activity within 30 minutes).
    #
    # ⛔ Codex on #855, confirmed live: pcs.round_date is a DATE-ONLY text
    # ('YYYY-MM-DD'), so the old `round_date::timestamp >= NOW() - 30 min`
    # compared against MIDNIGHT — after 00:30 the endpoint answered
    # {active: false} for the rest of the day (measured at 22:26 during an
    # evening with 12 rounds imported in the prior two hours), and
    # COUNT(DISTINCT round_date) collapsed every same-day round to 1.
    # rounds.created_at is the import timestamp — about a minute behind
    # play, which is exactly the claim the UI makes ("imported in the last
    # half hour"). A historical backfill would read as live for its half
    # hour; that is the honest trade for having a working clock at all.
    query = """
        SELECT
            MAX(r.created_at) as last_round,
            COUNT(DISTINCT r.id) as rounds,
            COUNT(DISTINCT p.player_guid) as players
        FROM rounds r
        JOIN player_comprehensive_stats p ON p.round_id = r.id
        WHERE r.round_number IN (1, 2)
            AND r.created_at >= NOW() - INTERVAL '30 minutes'
    """
    try:
        result = await db.fetch_one(query)
    except Exception as e:
        logger.error("Database error in get_live_session: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred.")

    if not result or not result[0]:
        return {"active": False}

    # Get latest round details (actual_duration_seconds lives on rounds table)
    latest_query = """
        SELECT
            r.map_name,
            r.created_at,
            r.actual_duration_seconds
        FROM rounds r
        WHERE r.round_number IN (1, 2)
        ORDER BY r.created_at DESC
        LIMIT 1
    """
    try:
        latest = await db.fetch_one(latest_query)
    except Exception as e:
        logger.error("Failed to fetch latest round details: %s", e)
        latest = None

    def format_stopwatch_time(seconds: int) -> str:
        if not seconds:
            return "0:00"
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"

    return {
        "active": True,
        "rounds_completed": result[1],
        "current_players": result[2],
        "current_map": latest[0] if latest else "Unknown",
        "last_round_time": format_stopwatch_time(latest[2]) if latest else None,
        "last_update": str(result[0]),
    }


# ── Tonight live hub (VISION_2026 S7 LIVE) ─────────────────────────────────────
_TONIGHT_ACTIVE_SECONDS = 40 * 60  # session is "live" if a round landed in 40 min


async def _hold_prob_curve(db, map_name: str) -> list[dict]:
    """Historical attack-completion curve for a map: P(attack done by time t),
    from MEASURED round durations across valid rounds (actual_time alone is
    the stopwatch target and is inflated on surrenders — RCA 2026-08-18)."""
    dur = round_duration_sql("rounds")
    rows = await db.fetch_all(
        f"""
        SELECT {dur} AS secs
        FROM rounds
        WHERE map_name = ?
          AND round_number IN (1, 2)
          AND is_valid IS DISTINCT FROM FALSE
          AND {dur} > 0
          -- Completed attacks only: with measured durations a surrendered or
          -- full-held round has a short/real duration too, and counting it
          -- would report the attack as "done by t" when it never finished
          -- (coderabbit, PR #770). Attackers completed <=> winner is not the
          -- defender.
          AND winner_team IN (1, 2)
          AND defender_team IN (1, 2)
          AND winner_team <> defender_team
        """,
        (map_name,),
    )
    secs = sorted(int(r[0]) for r in (rows or []))
    if len(secs) < 3:
        return []
    cap = secs[-1]
    total = len(secs)
    points = []
    idx = 0  # single pointer over the sorted list → O(n + buckets)
    t = 0
    while t <= cap:
        while idx < total and secs[idx] <= t:
            idx += 1
        points.append({"t": t, "p": round(idx / total * 100, 1)})
        t += 30
    return points


@router.get("/stats/hold-probability")
async def get_hold_probability(map_name: str = Query(alias="map"),
                               db: DatabaseAdapter = Depends(get_db)):
    """Historical attack-completion-time curve for a single map."""
    curve = await _hold_prob_curve(db, map_name)
    return {"status": "ok", "map": map_name, "curve": curve}


def _is_bot_player(p: dict) -> bool:
    """Identity-level bot check for lua payload players (guid OMNIBOT* or
    name [BOT]*) — mirror of ssr_service._BOTS."""
    guid = str(p.get("guid") or "")
    name = str(p.get("name") or "")
    return guid.upper().startswith("OMNIBOT") or name.startswith("[BOT]")


def _lua_players(val) -> list[dict]:
    """Normalise the axis_players/allies_players jsonb (list of {guid, name})
    whether asyncpg hands it back as a parsed list or a JSON string."""
    if isinstance(val, str):
        try:
            val = json.loads(val)
        except (ValueError, TypeError):
            return []
    return [p for p in (val or []) if isinstance(p, dict)]


async def _tonight_team_names(db, gaming_session_id, anchor_a: set, anchor_b: set):
    """Best-effort logical-team display names. In stopwatch mode the Axis/Allies
    labels swap every round, so the only stable identity is the roster. If the
    bot has already written session_teams for this session, map those names onto
    the alpha/beta anchors by GUID overlap; otherwise fall back to Team A/Team B.

    Defensive on purpose: names are cosmetic (the rosters are the real identity),
    so any schema/data surprise falls back to the generic labels rather than
    breaking the live payload. Note session_teams stores SHORT 8-char GUIDs while
    the lua feed has full 32-char GUIDs — compare on the 8-char prefix.
    """
    default = ("Team A", "Team B")
    if not gaming_session_id:
        return default
    short_a = {g[:8] for g in anchor_a if g}
    short_b = {g[:8] for g in anchor_b if g}
    try:
        rows = await db.fetch_all(
            "SELECT team_name, player_guids FROM session_teams WHERE gaming_session_id = ?",
            (gaming_session_id,),
        )
        by_team: dict[str, set] = {}
        for name, guids in (rows or []):
            if not name:
                continue
            by_team.setdefault(name, set()).update(
                g[:8] for g in _lua_guid_list(guids) if g
            )
        teams = sorted((kv for kv in by_team.items() if kv[1]), key=lambda kv: -len(kv[1]))[:2]
        if len(teams) < 2:
            return default
        (n1, g1), (n2, g2) = teams
        a_for_1 = len(g1 & short_a) - len(g1 & short_b)
        a_for_2 = len(g2 & short_a) - len(g2 & short_b)
        return (n1, n2) if a_for_1 >= a_for_2 else (n2, n1)
    except Exception:
        return default


def _lua_guid_list(val) -> list[str]:
    """Normalise a jsonb GUID array (session_teams.player_guids) to a list."""
    if isinstance(val, str):
        try:
            val = json.loads(val)
        except (ValueError, TypeError):
            return []
    return [g for g in (val or []) if isinstance(g, str)]


def _fmt_mmss(seconds) -> str:
    """Whole-second duration as m:ss (e.g. 252 -> '4:12'). '' for None, negative,
    or non-numeric input."""
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return ""
    if s < 0:
        return ""
    return f"{s // 60}:{s % 60:02d}"


def _tonight_director_line(score: dict, momentum: list, current: dict,
                           name_a: str, name_b: str) -> str | None:
    """One live 'director' sentence for the Tonight hub (Good Night plan rank 8,
    §A idea 1). A pure read of the already-computed tonight payload — never a new
    metric, just a plain-language summary of the night so far plus the live chase.

    Returns None before there is anything to say (no completed map and no round
    decided yet), so the caller can simply omit the line.
    """
    a_maps, b_maps = int(score.get("a_maps", 0)), int(score.get("b_maps", 0))
    a_rounds, b_rounds = int(score.get("a_rounds", 0)), int(score.get("b_rounds", 0))
    maps_completed = int(score.get("maps_completed", 0))
    if maps_completed == 0 and a_rounds == 0 and b_rounds == 0:
        return None

    # Momentum: last swing value (100 = Team A dominating, 0 = Team B).
    last_m = float(momentum[-1].get("a", 50.0)) if momentum else 50.0
    mom_a = last_m >= 55.0
    mom_b = last_m <= 45.0

    # Lead clause — maps first (the night is scored in maps), rounds as the
    # tiebreaker when maps are level.
    if a_maps > b_maps:
        leader, hi, lo, leader_is_a = name_a, a_maps, b_maps, True
        lead = f"{leader} lead the night {hi}–{lo} on maps"
    elif b_maps > a_maps:
        leader, hi, lo, leader_is_a = name_b, b_maps, a_maps, False
        lead = f"{leader} lead the night {hi}–{lo} on maps"
    elif maps_completed > 0:
        leader, leader_is_a = None, None
        lead = f"All square at {a_maps}–{b_maps} on maps"
    else:
        # First map still on the clock — lean on the round tally.
        leader, leader_is_a = None, None
        if a_rounds != b_rounds:
            rl, rh, rlo = (name_a, a_rounds, b_rounds) if a_rounds > b_rounds else (name_b, b_rounds, a_rounds)
            lead = f"Opening map on the clock — {rl} up {rh}–{rlo} on rounds"
        else:
            lead = f"Opening map on the clock — even {a_rounds}–{b_rounds} on rounds"

    # Momentum clause — only when it adds something.
    tail = ""
    if leader is not None:
        if (leader_is_a and mom_a) or (not leader_is_a and mom_b):
            tail = ", and they hold the momentum"
        elif (leader_is_a and mom_b) or (not leader_is_a and mom_a):
            other = name_b if leader_is_a else name_a
            tail = f", but {other} have swung the last few rounds"
    elif maps_completed > 0 and (mom_a or mom_b):
        # Level on maps — momentum names who's pushing now.
        pusher = name_a if mom_a else name_b
        tail = f", but {pusher} are pushing"

    # Live chase clause — an R1 just landed and R2 is on the clock.
    chase = ""
    if current and current.get("r2_pending"):
        beat = _fmt_mmss(current.get("beat_seconds"))
        cmap = (current.get("map") or "").replace("_", " ")
        if beat and cmap:
            chase = f" · {cmap}: R2 chasing {beat}"
        elif cmap:
            chase = f" · {cmap}: R2 to play"

    return f"{lead}{tail}{chase}."


class TonightRound(BaseModel):
    round: int
    #: None when the Lua winner value is outside 1/2 — a live or
    #: unlinked round, not an error (Codex on #830).
    winner: str | None
    axis_score: int
    allies_score: int
    #: None when neither `actual_duration_seconds` nor a usable timestamp
    #: pair exists (Codex on #830).
    duration: int | None
    a_on_axis: bool
    is_fullhold: bool


class TonightMap(BaseModel):
    #: `lua_round_teams.map_name` is nullable and preserved as null by
    #: `_store_lua_round_teams` — Codex on #830.
    map: str | None
    map_number: int
    rounds: list[TonightRound]
    winner: str
    a_points: int
    b_points: int


class TonightTeam(BaseModel):
    name: str
    #: Player display names, sorted case-insensitively.
    roster: list[str]


class TonightTeams(BaseModel):
    a: TonightTeam
    b: TonightTeam


class TonightScore(BaseModel):
    a_maps: int
    b_maps: int
    a_rounds: int
    b_rounds: int
    maps_completed: int


class TonightMomentum(BaseModel):
    a: float
    b: float


class TonightCurrent(BaseModel):
    """The map being played right now.

    `beat_seconds` is the R1 duration R2's attack has to beat, and it is
    populated ONLY while `r2_pending` is true. All four sampled nights had
    already finished their R2, so every sample showed null — the int branch is
    typed from `cur_by_round.get(1, {}).get("duration")`, not from a reading.
    """

    map: str | None
    round: int
    status: str
    r2_pending: bool
    beat_seconds: int | None


class TonightHoldPoint(BaseModel):
    t: int
    p: float


class TonightHoldProbability(BaseModel):
    """⭐ `map` IS NON-NULL HERE WHILE `TonightMap.map` AND `current_map` ARE
    NOT, and the asymmetry is structural rather than an oversight. The handler
    computes the curve as `_hold_prob_curve(db, current_map) if current_map
    else []`, and then emits this object only `if hold` — so a null map name
    yields an empty curve, an empty curve yields `hold_probability: None`, and
    this object never exists with a null map. Same kind of guarantee as
    `head_pct` under its `HAVING` floor: a fact about the code, not about
    today's rows."""

    map: str
    curve: list[TonightHoldPoint]


class TonightLive(BaseModel):
    """A night with rounds in it — the TWELVE-key shape."""

    status: str
    active: bool
    #: Nullable for the same reason as `TonightMap.map`.
    current_map: str | None
    last_update_unix: int
    age_seconds: int
    teams: TonightTeams
    score: TonightScore
    maps: list[TonightMap]
    momentum: list[TonightMomentum]
    current: TonightCurrent
    #: `_tonight_director_line` is annotated `str | None` and returns None
    #: before there is anything to say. All four samples had a sentence.
    director: str | None
    #: `{"map": …, "curve": […]} if hold else None` — null when the curve is
    #: empty, which no sampled night was.
    hold_probability: TonightHoldProbability | None


class TonightIdle(BaseModel):
    """No live session — the NINE-key shape, with `{}` and `[]` where the live
    shape carries structure.

    ⛔ SAMPLING THIS ENDPOINT TODAY RETURNS THIS SHAPE AND ONLY THIS SHAPE, and
    that is the reverse of the trap on `/stats/last-session`. The query is
    `WHERE captured_at::date = CURRENT_DATE`, the last capture was two days
    ago, so the live response is the EMPTY one and the twelve-key shape is the
    unreachable branch. Measured by rewriting CURRENT_DATE to five days that do
    have captures: 2026-08-27/26/23/20 answer twelve keys, and 2026-08-21
    answers nine — that is the SECOND idle return, where rows exist but every
    one was a bot round the identity filter dropped.

    ⚠️ `teams` and `score` are `{}` here and structured objects there, so the
    two shapes are a union, not one model with optional fields. `current`,
    `director` and `hold_probability` are literally None on this branch.
    """

    status: str
    active: bool
    teams: dict[str, Any]
    maps: list[Any]
    momentum: list[Any]
    score: dict[str, Any]
    current: None
    director: None
    hold_probability: None


@router.get("/stats/tonight",
            response_model=TonightLive | TonightIdle)
async def get_tonight(db: DatabaseAdapter = Depends(get_db)):
    """Consolidated live payload for the Tonight hub. Reads the real-time
    lua_round_teams feed and resolves it into LOGICAL TEAMS (not Axis/Allies —
    those swap every round in stopwatch mode). Returns per-map stopwatch results,
    team round/map tallies, rosters, a team-momentum swing, the current map's
    live status (incl. the R2 time-to-beat chase) and its hold-probability curve.
    One poll (~8s)."""
    rows = await db.fetch_all(
        """
        SELECT l.map_name, l.round_number, l.winner_team, l.defender_team,
               l.axis_score, l.allies_score, l.axis_players, l.allies_players,
               l.round_start_unix, l.round_end_unix,
               EXTRACT(EPOCH FROM l.captured_at)::bigint AS cap_unix,
               r.gaming_session_id, r.round_outcome, r.actual_duration_seconds
        FROM lua_round_teams l
        LEFT JOIN rounds r ON r.id = l.round_id
        WHERE l.captured_at::date = CURRENT_DATE
          AND (r.id IS NULL OR r.is_valid IS DISTINCT FROM FALSE)
        ORDER BY l.captured_at ASC
        """,
    )
    rows = rows or []
    if not rows:
        return {"status": "ok", "active": False, "teams": {}, "maps": [],
                "momentum": [], "score": {}, "current": None, "director": None,
                "hold_probability": None}

    # --- Resolve logical teams with the stopwatch side-alternation model that
    #     the rest of the site uses (see BOXScoringService): on odd maps Team A
    #     starts on Axis (R1) and swaps to Allies (R2); on even maps it's
    #     mirrored. This is deterministic (no fragile roster-overlap guessing)
    #     and consistent with session-detail scoring. "Team A" = whoever opened
    #     the night on Axis.
    def _alpha_side(map_no: int, rnd: int) -> int:
        # 1 = Axis, 2 = Allies. Odd map: R1 alpha=Axis, R2 alpha=Allies.
        if map_no % 2 == 1:
            return 1 if rnd == 1 else 2
        return 2 if rnd == 1 else 1

    # Players sub in/out across a night, so attribute each guid to the team it
    # played MOST rounds for (computed after the loop) — a clean, non-overlapping
    # roster even when someone fills in for the other team for a map.
    count_a: Counter = Counter()
    count_b: Counter = Counter()
    name_by_guid: dict[str, str] = {}

    maps: dict[int, dict] = {}
    momentum = []
    m = 50.0  # 100 = Team A dominating, 0 = Team B
    a_rounds = b_rounds = 0
    map_number = 0
    last_gsid = None

    for r in rows:
        map_name, rnum, winner = r[0], int(r[1] or 0), r[2]
        axis_sc, allies_sc = int(r[4] or 0), int(r[5] or 0)
        axis_p, allies_p = _lua_players(r[6]), _lua_players(r[7])
        # Bot rounds must never shape the public Tonight surface. The
        # is_valid join above only covers LINKED rows (r.id IS NULL passes
        # unlinked ones through, legitimately — a live round is unlinked for
        # a few minutes), so filter by identity too, same patterns as
        # ssr_service._BOTS. A fully-bot row is skipped BEFORE the
        # map_number increment so bot rounds don't advance the logical
        # side alternation of the real session either.
        axis_p = [p for p in axis_p if not _is_bot_player(p)]
        allies_p = [p for p in allies_p if not _is_bot_player(p)]
        if not axis_p and not allies_p:
            continue
        start_u, end_u = r[8], r[9]
        if r[11]:
            last_gsid = r[11]

        if rnum == 1:
            map_number += 1
        a_on_axis = _alpha_side(map_number, rnum) == 1

        # Tally each player's rounds per logical team for majority assignment.
        for p in (axis_p if a_on_axis else allies_p):
            if p.get("guid"):
                count_a[p["guid"]] += 1
                name_by_guid[p["guid"]] = p.get("name", name_by_guid.get(p["guid"], "?"))
        for p in (allies_p if a_on_axis else axis_p):
            if p.get("guid"):
                count_b[p["guid"]] += 1
                name_by_guid[p["guid"]] = p.get("name", name_by_guid.get(p["guid"], "?"))

        # Round winner → logical team.
        if winner == 1:
            rteam = "a" if a_on_axis else "b"
        elif winner == 2:
            rteam = "b" if a_on_axis else "a"
        else:
            rteam = None
        if rteam == "a":
            a_rounds += 1
        elif rteam == "b":
            b_rounds += 1

        target = 100.0 if rteam == "a" else (0.0 if rteam == "b" else 50.0)
        m = m * 0.7 + target * 0.3
        momentum.append({"a": round(m, 1), "b": round(100 - m, 1)})

        mp = maps.setdefault(map_number, {"map_number": map_number, "map": map_name, "rounds": []})
        # Prefer actual_duration_seconds (excludes pauses, what the stopwatch
        # time-to-beat is measured in) over wall-clock end-start; fall back to
        # wall-clock for a live/unlinked round whose rounds row isn't there yet.
        actual_dur = r[13] if len(r) > 13 else None
        duration = (
            int(actual_dur) if actual_dur
            else (int(end_u - start_u) if (start_u and end_u and end_u > start_u) else None)
        )
        round_outcome = r[12] if len(r) > 12 else None
        # Fullhold = the defending side won the round. Derive it from the lua
        # feed's own winner/defender (authoritative, already selected) — the
        # rounds.round_outcome text is the parser's ±30s time heuristic that
        # mislabels last-30s completions as holds, which scored real map wins
        # as 1-1 draws here (same bug fixed in BOXScoringService #727). Text
        # stays as fallback for rows whose sides are unknown.
        defender = r[3]
        if winner in (1, 2) and defender in (1, 2):
            is_fullhold = winner == defender
        else:
            is_fullhold = bool(round_outcome) and round_outcome.lower() == "fullhold"
        mp["rounds"].append({
            "round": rnum, "winner": rteam,
            "axis_score": axis_sc, "allies_score": allies_sc,
            "a_on_axis": a_on_axis, "duration": duration,
            "is_fullhold": is_fullhold,
        })

    # --- Per-map stopwatch result in team terms. R2 is the decider; if only R1
    #     has landed the map is still pending.
    map_list = []
    a_maps = b_maps = maps_completed = 0
    for mn in sorted(maps):
        mp = maps[mn]
        by_round = {rr["round"]: rr for rr in mp["rounds"]}
        r1 = by_round.get(1)
        r2 = by_round.get(2)
        winner = "pending"
        a_pts = b_pts = 0
        if r2:
            if r1 and r1.get("is_fullhold") and r2.get("is_fullhold"):
                # Double fullhold — both defenders held the full time; 1 pt each
                # (draw, no map win to either side). Mirrors
                # BOXScoringService.score_map so Tonight matches session-detail.
                winner = "draw"
                a_pts = b_pts = 1
                maps_completed += 1
            elif r2["winner"]:
                winner = r2["winner"]  # R2 decider takes the map — 2 points
                if winner == "a":
                    a_pts, a_maps = 2, a_maps + 1
                else:
                    b_pts, b_maps = 2, b_maps + 1
                maps_completed += 1
            else:
                winner = "draw"
                maps_completed += 1
        mp.update({"winner": winner, "a_points": a_pts, "b_points": b_pts})
        map_list.append(mp)

    # Every today-row can be a bot round that the identity filter above
    # dropped (map_number never advanced, maps stays empty) while `rows`
    # itself is non-empty — that must read as "no live session", not a 500.
    if not maps or map_number not in maps:
        return {"status": "ok", "active": False, "teams": {}, "maps": [],
                "momentum": [], "score": {}, "current": None, "director": None,
                "hold_probability": None}

    last_unix = int(rows[-1][10] or 0)
    now_unix = int(datetime.now(timezone.utc).timestamp())
    age = max(0, now_unix - last_unix)
    current_map = rows[-1][0]
    current_rnum = int(rows[-1][1] or 0)

    # --- Current-map live status + R2 time-to-beat chase. lua rows land at round
    #     END, so "live" means a fresh round just completed; if R1 just finished
    #     we surface the time R2's attack must beat.
    cur = maps[map_number]
    cur_by_round = {rr["round"]: rr for rr in cur["rounds"]}
    r2_pending = (1 in cur_by_round) and (2 not in cur_by_round)
    beat = cur_by_round.get(1, {}).get("duration") if r2_pending else None
    if r2_pending:
        status = "R1 in the books — R2 to play"
    elif current_rnum == 2:
        status = "map complete"
    else:
        status = "in progress"
    current = {
        "map": current_map, "round": current_rnum, "status": status,
        "r2_pending": r2_pending, "beat_seconds": beat,
    }

    # Majority assignment: each guid lands on the team it played most for (ties → A).
    roster_a: dict[str, str] = {}
    roster_b: dict[str, str] = {}
    for guid in set(count_a) | set(count_b):
        if count_a[guid] >= count_b[guid]:
            roster_a[guid] = name_by_guid.get(guid, "?")
        else:
            roster_b[guid] = name_by_guid.get(guid, "?")

    name_a, name_b = await _tonight_team_names(db, last_gsid, set(roster_a), set(roster_b))
    hold = await _hold_prob_curve(db, current_map) if current_map else []

    def _roster(d):
        return sorted(d.values(), key=str.lower)

    score = {
        "a_maps": a_maps, "b_maps": b_maps,
        "a_rounds": a_rounds, "b_rounds": b_rounds,
        "maps_completed": maps_completed,
    }
    return {
        "status": "ok",
        "active": age <= _TONIGHT_ACTIVE_SECONDS,
        "current_map": current_map,
        "last_update_unix": last_unix,
        "age_seconds": age,
        "teams": {
            "a": {"name": name_a, "roster": _roster(roster_a)},
            "b": {"name": name_b, "roster": _roster(roster_b)},
        },
        "score": score,
        "maps": map_list,
        "momentum": momentum,
        "current": current,
        "director": _tonight_director_line(score, momentum, current, name_a, name_b),
        "hold_probability": {"map": current_map, "curve": hold} if hold else None,
    }


@router.get("/stats/player/{player_name}")
async def get_player_stats(player_name: str, db: DatabaseAdapter = Depends(get_db)):
    """
    Get aggregated statistics for a specific player.
    """
    player_guid = await resolve_player_guid(db, player_name)
    use_guid = player_guid is not None
    identifier = player_guid if use_guid else player_name
    display_name = (
        await resolve_display_name(db, player_guid, player_name) if use_guid else player_name
    )

    # Postgres query
    # We join with rounds to get win/loss data
    # We assume round_id exists in player_comprehensive_stats as per bot code
    query = """
        SELECT
            SUM(p.kills) as total_kills,
            SUM(p.deaths) as total_deaths,
            SUM(p.damage_given) as total_damage,
            SUM(p.time_played_seconds) as total_time,
            COUNT(p.round_id) as total_games,
            SUM(p.xp) as total_xp,
            SUM(CASE WHEN p.team = r.winner_team THEN 1 ELSE 0 END) as total_wins,
            MAX(p.round_date) as last_seen
        FROM player_comprehensive_stats p
        LEFT JOIN rounds r ON r.id = p.round_id
        WHERE p.player_guid = $1
          AND p.round_number IN (1, 2)
          -- Codex on #855: the profile's lifetime numbers carry this gate
          -- (players_profile_router), so the milestones computed here must
          -- count the same rounds — measured 490 vs 454 kills for one guid
          -- without it. IS DISTINCT FROM keeps LEFT-JOIN NULLs, the same
          -- reading as everywhere else.
          AND r.is_valid IS DISTINCT FROM FALSE
    """
    if not use_guid:
        query = query.replace("p.player_guid = $1", "p.player_name ILIKE $1")

    try:
        row = await db.fetch_one(query, (identifier,))
    except Exception as e:
        logger.error(f"Error fetching player stats: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not row or not row[0]:  # No kills usually means no stats found
        raise HTTPException(status_code=404, detail="Player not found")

    (kills, deaths, damage, time, games, xp, wins, last_seen) = row

    # Handle None values
    kills = kills or 0
    deaths = deaths or 0
    damage = damage or 0
    time = time or 0
    games = games or 0
    xp = xp or 0
    wins = wins or 0

    kd = kills / deaths if deaths > 0 else kills
    dpm = (damage / (time / 60)) if time > 0 else 0
    win_rate = (wins / games * 100) if games > 0 else 0

    # Calculate achievements based on stats
    achievements = calculate_player_achievements(int(kills), int(games), kd)

    # Get favorite weapon (most kills) from weapon_comprehensive_stats
    weapon_query = """
        SELECT weapon_name, SUM(kills) as total_kills
        FROM weapon_comprehensive_stats
        WHERE player_guid = $1
        GROUP BY weapon_name
        ORDER BY total_kills DESC
        LIMIT 1
    """
    if not use_guid:
        weapon_query = weapon_query.replace("player_guid = $1", "player_name ILIKE $1")
    try:
        weapon_row = await db.fetch_one(weapon_query, (identifier,))
        if weapon_row and weapon_row[0]:
            clean_name = weapon_row[0]
            if clean_name.lower().startswith("ws ") or clean_name.lower().startswith(
                "ws_"
            ):
                clean_name = clean_name[3:]
            favorite_weapon = clean_name.replace("_", " ").title()
        else:
            favorite_weapon = None
    except Exception as e:
        logger.error(f"Error fetching favorite weapon for {player_name}: {e}")
        favorite_weapon = None

    # Get favorite map (most played)
    map_query = """
        SELECT map_name, COUNT(*) as play_count
        FROM player_comprehensive_stats
        WHERE player_guid = $1
        GROUP BY map_name
        ORDER BY play_count DESC
        LIMIT 1
    """
    if not use_guid:
        map_query = map_query.replace("player_guid = $1", "player_name ILIKE $1")
    try:
        map_row = await db.fetch_one(map_query, (identifier,))
        favorite_map = map_row[0] if map_row else None
    except Exception as e:
        logger.error(f"Error fetching favorite map for {player_name}: {e}")
        favorite_map = None

    # Get highest and lowest DPM (single round)
    # ⛔ R0 rows carry CUMULATIVE damage over NON-cumulative playtime
    # (CLAUDE.md), so without the round filter the "highest dpm" is the R0
    # artifact almost by construction — measured 790 vs a real 403 for one
    # guid. Same validity gate as the aggregate above.
    dpm_query = """
        SELECT
            MAX(CASE WHEN p.time_played_seconds > 60 THEN p.damage_given * 60.0 / p.time_played_seconds END) as max_dpm,
            MIN(CASE WHEN p.time_played_seconds > 60 THEN p.damage_given * 60.0 / p.time_played_seconds END) as min_dpm
        FROM player_comprehensive_stats p
        LEFT JOIN rounds r ON r.id = p.round_id
        WHERE p.player_guid = $1 AND p.time_played_seconds > 60
          AND p.round_number IN (1, 2)
          AND r.is_valid IS DISTINCT FROM FALSE
    """
    if not use_guid:
        dpm_query = dpm_query.replace("p.player_guid = $1", "p.player_name ILIKE $1")
    try:
        dpm_row = await db.fetch_one(dpm_query, (identifier,))
        highest_dpm = int(dpm_row[0]) if dpm_row and dpm_row[0] else None
        lowest_dpm = int(dpm_row[1]) if dpm_row and dpm_row[1] else None
    except Exception as e:
        logger.error(f"Error fetching DPM records for {player_name}: {e}")
        highest_dpm = None
        lowest_dpm = None

    # Get player aliases (other names used by same GUID)
    alias_query = """
        SELECT DISTINCT player_name
        FROM player_comprehensive_stats
        WHERE player_guid = $1
        AND player_name NOT ILIKE $2
        ORDER BY player_name
        LIMIT 5
    """
    try:
        if use_guid:
            alias_rows = await db.fetch_all(alias_query, (player_guid, display_name))
        else:
            alias_rows = []
        aliases = [row[0] for row in alias_rows] if alias_rows else []
    except Exception as e:
        logger.error(f"Error fetching aliases for {player_name}: {e}")
        aliases = []

    # Check Discord link status
    discord_query = """
        SELECT discord_id FROM player_links WHERE player_guid = $1 LIMIT 1
    """
    if not use_guid:
        discord_query = discord_query.replace("player_guid = $1", "player_name ILIKE $1")
    try:
        discord_row = await db.fetch_one(discord_query, (identifier,))
        discord_linked = discord_row is not None
    except Exception as e:
        logger.error(f"Error checking Discord link for {player_name}: {e}")
        discord_linked = False

    # Sick-leave (bolniška) attribution for the identity card — see migration 073.
    identity_link = (
        (await fetch_identity_links(db, [player_guid])).get(player_guid)
        if player_guid else None
    )

    return {
        "name": display_name,
        "guid": player_guid,
        "stats": {
            "kills": int(kills),
            "deaths": int(deaths),
            "damage": int(damage),
            "games": int(games),
            "wins": int(wins),
            "losses": int(games - wins),
            "win_rate": round(win_rate, 1),
            "kd": round(kd, 2),
            "dpm": int(dpm),
            "total_xp": int(xp),
            "playtime_hours": round(time / 3600, 1),
            "last_seen": last_seen,
            "favorite_weapon": favorite_weapon,
            "favorite_map": favorite_map,
            "highest_dpm": highest_dpm,
            "lowest_dpm": lowest_dpm,
        },
        "aliases": aliases,
        "discord_linked": discord_linked,
        "identity_link": identity_link,  # sick-leave attribution or None
        "achievements": achievements,
    }


@router.get("/stats/compare")
async def compare_players(
    player1: str, player2: str, db: DatabaseAdapter = Depends(get_db)
):
    """
    Compare two players side-by-side with radar chart data.
    Returns normalized stats (0-100 scale) for fair comparison.
    """
    guid1 = await resolve_player_guid(db, player1)
    guid2 = await resolve_player_guid(db, player2)

    if guid1 and guid2 and guid1 == guid2:
        raise HTTPException(status_code=400, detail="Both identifiers resolve to the same player")

    params = []
    clauses = []
    if guid1:
        clauses.append(f"player_guid = ${len(params) + 1}")
        params.append(guid1)
    else:
        clauses.append(f"player_name ILIKE ${len(params) + 1}")
        params.append(player1)

    if guid2:
        clauses.append(f"player_guid = ${len(params) + 1}")
        params.append(guid2)
    else:
        clauses.append(f"player_name ILIKE ${len(params) + 1}")
        params.append(player2)

    where_clause = " OR ".join(clauses)

    query = f"""
        SELECT
            player_guid,
            MAX(player_name) as player_name,
            SUM(kills) as total_kills,
            SUM(deaths) as total_deaths,
            SUM(damage_given) as total_damage,
            SUM(time_played_seconds) as total_time,
            COUNT(*) as total_games,
            SUM(revives_given) as total_revives,
            SUM(headshots) as total_headshots,
            AVG(accuracy) as avg_accuracy,
            SUM(gibs) as total_gibs,
            SUM(xp) as total_xp
        FROM player_comprehensive_stats
        WHERE ({where_clause})
          AND round_number IN (1, 2)
        GROUP BY player_guid
    """

    try:
        rows = await db.fetch_all(query, tuple(params))
    except Exception as e:
        logger.error(f"Error comparing players: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if len(rows) < 2:
        raise HTTPException(status_code=404, detail="One or both players not found")

    # Process both players
    players = []
    row_map = {row[0]: row for row in rows}
    ordered_guids = []
    if guid1:
        ordered_guids.append(guid1)
    if guid2 and guid2 not in ordered_guids:
        ordered_guids.append(guid2)

    if ordered_guids:
        ordered_rows = [row_map.get(g) for g in ordered_guids if row_map.get(g)]
        ordered_rows += [r for r in rows if r not in ordered_rows]
    else:
        ordered_rows = rows

    # Batch resolve display names once instead of N+1 per-row.
    quick_name_map = await batch_resolve_display_names(
        db, [(r[0], r[1] or "Unknown") for r in ordered_rows if r and r[0]]
    )

    for row in ordered_rows:
        guid = row[0]
        name = (
            quick_name_map.get(guid, row[1] or "Unknown")
            if guid
            else (row[1] or "Unknown")
        )
        kills = row[2] or 0
        deaths = row[3] or 0
        damage = row[4] or 0
        time_played = row[5] or 0
        games = row[6] or 0
        revives = row[7] or 0
        headshots = row[8] or 0
        accuracy = row[9] or 0
        gibs = row[10] or 0
        xp = row[11] or 0

        time_minutes = time_played / 60 if time_played > 0 else 1
        kd = kills / deaths if deaths > 0 else kills
        dpm = damage / time_minutes

        players.append(
            {
                "name": name,
                "guid": guid,
                "raw": {
                    "kills": int(kills),
                    "deaths": int(deaths),
                    "damage": int(damage),
                    "games": int(games),
                    "kd": round(kd, 2),
                    "dpm": round(dpm, 1),
                    "revives": int(revives),
                    "headshots": int(headshots),
                    "accuracy": round(accuracy, 1),
                    "gibs": int(gibs),
                    "xp": int(xp),
                },
            }
        )

    # Calculate normalized stats for radar chart (0-100 scale)
    # Compare each stat relative to the max between the two players
    radar_labels = ["K/D", "DPM", "Accuracy", "Revives", "Headshots", "Gibs"]
    p1, p2 = players[0], players[1]

    def normalize(val1, val2):
        """Normalize two values to 0-100 scale based on max."""
        max_val = max(val1, val2)
        if max_val == 0:
            return 50, 50
        return round(val1 / max_val * 100, 1), round(val2 / max_val * 100, 1)

    p1_kd, p2_kd = normalize(p1["raw"]["kd"], p2["raw"]["kd"])
    p1_dpm, p2_dpm = normalize(p1["raw"]["dpm"], p2["raw"]["dpm"])
    p1_acc, p2_acc = normalize(p1["raw"]["accuracy"], p2["raw"]["accuracy"])
    p1_rev, p2_rev = normalize(p1["raw"]["revives"], p2["raw"]["revives"])
    p1_hs, p2_hs = normalize(p1["raw"]["headshots"], p2["raw"]["headshots"])
    p1_gibs, p2_gibs = normalize(p1["raw"]["gibs"], p2["raw"]["gibs"])

    return {
        "player1": {**p1, "radar": [p1_kd, p1_dpm, p1_acc, p1_rev, p1_hs, p1_gibs]},
        "player2": {**p2, "radar": [p2_kd, p2_dpm, p2_acc, p2_rev, p2_hs, p2_gibs]},
        "radar_labels": radar_labels,
    }


class LeaderboardRow(BaseModel):
    """One row of the generic stat leaderboard, as this endpoint returns it.

    ⚠️ MEASURED, NOT DESIGNED: 635 rows over all 9 valid `stat` values × all 4
    distinct `period` branches (`7d`, `30d`, `season`, and the else-branch
    all-time). Zero nulls in every field.

    ⚠️ `kills` and `deaths` are `int | None`, AND THIS IS A CORRECTION. They
    were typed `int` on the argument that `SUM(x)` is null only for an
    all-null group, that there is no null `kills` row in the table, and that
    widening "buys nothing but a null check on every consumer". Comparing this
    file against the frontend's hand-written types showed the flaw: exactly
    the same evidence — column nullable, zero nulls observed — had produced
    `RecentRound.map_name: str | None` two endpoints away. The rule cannot be
    "it depends on how I felt".

    ⛔ The tiebreak is which mistake is recoverable. A `| None` the data never
    exercises costs one `?? 0` on the consumer. An `int` the data eventually
    contradicts is a 500 on a page that was rendering, and no test can catch
    it — only the table can. A response_model is a promise about what the
    server MAY send, and with a nullable column passed through raw (unlike
    `value` and `kd` three lines away, which the handler coalesces) the server
    may send null.

    `value` is `float` and not `int | float`: the handler's `else 0` branch
    (an int) needs a NULL `SUM`, unreachable for the same reason.
    """

    rank: int
    guid: str
    name: str
    value: float
    #: Rounds, NOT sessions — the field was renamed, the participation unit
    #: changed with it, and the handler still carries the old comment.
    rounds: int
    kills: int | None
    deaths: int | None
    kd: float


@router.get("/stats/leaderboard", response_model=list[LeaderboardRow])
async def get_leaderboard(
    stat: str = "dpm",
    period: str = "30d",
    #: ⛔ ACCEPTED AND IGNORED. `having` below is the empty string, so this
    #: value never reaches the query: `min_games=1` and `min_games=999` return
    #: identical rows (measured). It is NOT removed, because removing it would
    #: change an observable response — `min_games=abc` answers 422 today and
    #: would answer 200 once FastAPI stops knowing the parameter — and no
    #: caller sends it, so that change would buy nothing. Left declared and
    #: labelled instead: a parameter that VALIDATES a value and then discards
    #: it is the worst of the three states, because rejecting bad input is
    #: exactly what makes it look like it works.
    min_games: int = Query(
        default=3,
        description="Accepted and ignored — the handler applies no HAVING "
                    "clause. Kept only so that existing callers do not change "
                    "behaviour; do not build on it."),
    limit: int = 50,
    db: DatabaseAdapter = Depends(get_db),
):
    # Calculate start date
    if period == "7d":
        start_date_str = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")  # noqa: DTZ005 naive datetime for date-string arithmetic / SQL date filter / log timestamp display
    elif period == "30d":
        start_date_str = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")  # noqa: DTZ005 naive datetime for date-string arithmetic / SQL date filter / log timestamp display
    elif period == "season":
        sm = SeasonManager()
        start_date_str = sm.get_season_dates()[0].strftime("%Y-%m-%d")
    else:
        start_date_str = datetime(2020, 1, 1, tzinfo=timezone.utc).strftime("%Y-%m-%d")

    # Base query parts
    # nosec B608 - These clauses are static strings, not user-controlled input
    # Exclude bots (OMNIBOT* guids / [BOT] names): test artifacts must not
    # appear on all-time leaderboards (audit 2026-08-13). Shared by every metric
    # branch below via {where_clause}, so one gate covers them all.
    where_clause = "WHERE round_number IN (1, 2) AND time_played_seconds > 0 AND UPPER(player_guid) NOT LIKE 'OMNIBOT%' AND player_name NOT LIKE '%[BOT]%' AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)"
    name_select = "MAX(player_name) as player_name"
    # Phase 3 identity merge: fold a player's 'merged' alt guids into their main
    # identity so a post-guid-change history counts as one row. canonical_guid()
    # is the identity for everyone else, so nothing else moves (migration 075).
    guid_select = "canonical_guid(player_guid)"
    group_by = "GROUP BY canonical_guid(player_guid)"
    # Removed session count filter - table doesn't track sessions, only rounds/dates
    having = ""  # No HAVING clause needed for basic leaderboard

    if stat == "dpm":
        # nosec B608 - where_clause, group_by, having are static strings
        query = f"""
            WITH player_stats AS (
                SELECT
                    {guid_select} as player_guid,
                    {name_select},
                    COUNT(*) as rounds_played,
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    SUM(damage_given) as total_damage,
                    SUM(time_played_seconds) as total_time,
                    ROUND((SUM(damage_given)::numeric / NULLIF(SUM(time_played_seconds), 0) * 60), 2) as value,
                    CASE WHEN SUM(deaths) > 0 THEN ROUND(SUM(kills)::numeric / SUM(deaths), 2) ELSE SUM(kills)::numeric END as kd_ratio
                FROM player_comprehensive_stats
                {where_clause}
                {group_by}
                {having}
            )
            SELECT
                player_guid,
                player_name,
                value,
                rounds_played,
                total_kills,
                total_deaths,
                kd_ratio
            FROM player_stats
            ORDER BY value DESC
            LIMIT $2
        """
    elif stat == "kills":
        query = f"""
            SELECT
                {guid_select} as player_guid,
                {name_select},
                SUM(kills) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                CASE WHEN SUM(deaths) > 0 THEN ROUND(SUM(kills)::numeric / SUM(deaths), 2) ELSE SUM(kills)::numeric END as kd_ratio
            FROM player_comprehensive_stats
            {where_clause}
            {group_by}
            {having}
            ORDER BY value DESC
            LIMIT $2
        """
    elif stat == "kd":
        query = f"""
            SELECT
                {guid_select} as player_guid,
                {name_select},
                ROUND((SUM(kills)::numeric / NULLIF(SUM(deaths), 0)), 2) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                CASE WHEN SUM(deaths) > 0 THEN ROUND(SUM(kills)::numeric / SUM(deaths), 2) ELSE SUM(kills)::numeric END as kd_ratio
            FROM player_comprehensive_stats
            {where_clause}
            {group_by}
            {having}
            ORDER BY value DESC
            LIMIT $2
        """
    elif stat == "headshots":
        query = f"""
            SELECT
                {guid_select} as player_guid,
                {name_select},
                SUM(headshots) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                CASE WHEN SUM(deaths) > 0 THEN ROUND(SUM(kills)::numeric / SUM(deaths), 2) ELSE SUM(kills)::numeric END as kd_ratio
            FROM player_comprehensive_stats
            {where_clause}
            {group_by}
            {having}
            ORDER BY value DESC
            LIMIT $2
        """
    elif stat == "revives":
        query = f"""
            SELECT
                {guid_select} as player_guid,
                {name_select},
                SUM(revives_given) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                CASE WHEN SUM(deaths) > 0 THEN ROUND(SUM(kills)::numeric / SUM(deaths), 2) ELSE SUM(kills)::numeric END as kd_ratio
            FROM player_comprehensive_stats
            {where_clause}
            {group_by}
            {having}
            ORDER BY value DESC
            LIMIT $2
        """
    elif stat == "accuracy":
        # Accuracy requires minimum bullets fired to be meaningful
        query = f"""
            SELECT
                {guid_select} as player_guid,
                {name_select},
                ROUND(AVG(accuracy)::numeric, 1) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                CASE WHEN SUM(deaths) > 0 THEN ROUND(SUM(kills)::numeric / SUM(deaths), 2) ELSE SUM(kills)::numeric END as kd_ratio
            FROM player_comprehensive_stats
            {where_clause} AND bullets_fired > 100
            {group_by}
            HAVING COUNT(*) >= 3
            ORDER BY value DESC
            LIMIT $2
        """
    elif stat == "gibs":
        query = f"""
            SELECT
                {guid_select} as player_guid,
                {name_select},
                SUM(gibs) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                CASE WHEN SUM(deaths) > 0 THEN ROUND(SUM(kills)::numeric / SUM(deaths), 2) ELSE SUM(kills)::numeric END as kd_ratio
            FROM player_comprehensive_stats
            {where_clause}
            {group_by}
            {having}
            ORDER BY value DESC
            LIMIT $2
        """
    elif stat == "games":
        query = f"""
            SELECT
                {guid_select} as player_guid,
                {name_select},
                COUNT(*) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                CASE WHEN SUM(deaths) > 0 THEN ROUND(SUM(kills)::numeric / SUM(deaths), 2) ELSE SUM(kills)::numeric END as kd_ratio
            FROM player_comprehensive_stats
            {where_clause}
            {group_by}
            {having}
            ORDER BY value DESC
            LIMIT $2
        """
    elif stat == "damage":
        query = f"""
            SELECT
                {guid_select} as player_guid,
                {name_select},
                SUM(damage_given) as value,
                COUNT(*) as rounds_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                CASE WHEN SUM(deaths) > 0 THEN ROUND(SUM(kills)::numeric / SUM(deaths), 2) ELSE SUM(kills)::numeric END as kd_ratio
            FROM player_comprehensive_stats
            {where_clause}
            {group_by}
            {having}
            ORDER BY value DESC
            LIMIT $2
        """
    else:
        return []

    try:
        rows = await db.fetch_all(query, (start_date_str, limit))
    except Exception as e:

        logger.error("Leaderboard query error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Database error")

    name_map = await batch_resolve_display_names(
        db, [(row[0], row[1] or "Unknown") for row in rows]
    )
    leaderboard = []
    for i, row in enumerate(rows):
        leaderboard.append(
            {
                "rank": i + 1,
                "guid": row[0],
                "name": name_map.get(row[0], row[1] or "Unknown"),
                "value": float(row[2]) if row[2] is not None else 0,
                "rounds": row[3],  # Changed from sessions to rounds
                "kills": row[4],
                "deaths": row[5],
                "kd": float(row[6]) if row[6] is not None else 0,
            }
        )
    return leaderboard

class XpLeaderRow(BaseModel):
    """One row of the XP board. ⚠️ Its participation field is `rounds`."""

    rank: int
    guid: str
    name: str
    #: `SUM(xp)` — measured as a float on the live database, not an int.
    value: float
    rounds: int
    label: str


class DpmLeaderRow(BaseModel):
    """One row of the DPM board. ⚠️ Its participation field is `sessions`.

    ⛔ A SEPARATE MODEL, not one row type with both fields optional. The two
    boards genuinely differ, and a shared model with `rounds?`/`sessions?`
    would let either board claim the other's shape — a client could then read
    `rounds` off a DPM row and get `undefined` with the type system's blessing.
    """

    rank: int
    guid: str
    name: str
    value: float
    sessions: int
    label: str


class QuickLeaders(BaseModel):
    """Two small boards for the homepage, and their own failures.

    ⭐ `errors` IS THE POINT. Either board can fail INSIDE a 200: the query
    raises, the list comes back empty, and a token names which one. Without
    reading it, an empty board is indistinguishable from a quiet week — which
    is how "no data in this window" ended up on a page whose database was
    simply unreachable.

    ⚠️ `list[str]`, measured. The hand-written client type had `unknown[]`,
    which is weaker than the truth: the producer appends exactly
    `xp_query_failed` or `dpm_query_failed` and nothing else
    (`players_router`, the two `except` branches).
    """

    #: Fixed at 7 in the handler, not a parameter — the label cannot lie.
    window_days: int
    xp: list[XpLeaderRow]
    dpm_sessions: list[DpmLeaderRow]
    errors: list[str]


@router.get("/stats/quick-leaders", response_model=QuickLeaders)
async def get_quick_leaders(
    limit: int = 5,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Quick leaders for homepage:
    - Top XP in last 7 days
    - Top DPM per session in last 7 days
    """
    start_date = (datetime.now() - timedelta(days=7)).date()  # noqa: DTZ005 naive datetime for date-string arithmetic / SQL date filter / log timestamp display

    xp_query = """
        SELECT
            p.player_guid,
            MAX(p.player_name) as player_name,
            SUM(p.xp) as total_xp,
            COUNT(DISTINCT p.round_id) as rounds_played
        FROM player_comprehensive_stats p
        WHERE p.round_number IN (1, 2)
          AND p.time_played_seconds > 0
          AND CAST(SUBSTR(CAST(p.round_date AS TEXT), 1, 10) AS DATE) >= $1
        GROUP BY p.player_guid
        ORDER BY total_xp DESC
        LIMIT $2
    """
    errors = []
    xp_rows = []
    try:
        xp_rows = await db.fetch_all(xp_query, (start_date, limit))
    except Exception as primary_exc:
        # Local/dev SQLite (DATABASE_TYPE=sqlite via scripts/dev_up.sh) uses
        # the legacy player_comprehensive_stats schema with session_date /
        # session_id instead of round_date — the primary query raises
        # OperationalError there. Try the legacy column once before giving up.
        fallback_xp = """
            SELECT
                p.player_guid,
                MAX(p.player_name) as player_name,
                SUM(p.xp) as total_xp,
                COUNT(*) as rounds_played
            FROM player_comprehensive_stats p
            WHERE p.round_number IN (1, 2)
              AND p.time_played_seconds > 0
              AND CAST(SUBSTR(CAST(p.session_date AS TEXT), 1, 10) AS DATE) >= $1
            GROUP BY p.player_guid
            ORDER BY total_xp DESC
            LIMIT $2
        """
        logger.warning("XP primary failed, trying session_date fallback: %s", primary_exc)
        try:
            xp_rows = await db.fetch_all(fallback_xp, (start_date, limit))
        except Exception as fallback_exc:
            logger.error("XP leaderboard fallback also failed: %s", fallback_exc, exc_info=True)
            errors.append("xp_query_failed")
            xp_rows = []

    xp_name_map = await batch_resolve_display_names(
        db, [(row[0], row[1] or "Unknown") for row in xp_rows]
    )
    xp_leaders = []
    for i, row in enumerate(xp_rows):
        xp_leaders.append(
            {
                "rank": i + 1,
                "guid": row[0],
                "name": xp_name_map.get(row[0], row[1] or "Unknown"),
                "value": row[2] or 0,
                "rounds": row[3] or 0,
                "label": "XP",
            }
        )

    dpm_query = """
        WITH session_player AS (
            SELECT
                r.gaming_session_id,
                p.player_guid,
                MAX(p.player_name) as player_name,
                SUM(p.damage_given) as total_damage,
                SUM(p.time_played_seconds) as total_time
            FROM player_comprehensive_stats p
            INNER JOIN rounds r ON r.id = p.round_id
            WHERE r.gaming_session_id IS NOT NULL
              AND r.round_number IN (1, 2)
              AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
              AND p.time_played_seconds > 0
              AND CAST(SUBSTR(CAST(r.round_date AS TEXT), 1, 10) AS DATE) >= $1
            GROUP BY r.gaming_session_id, p.player_guid
        ),
        session_dpm AS (
            SELECT
                player_guid,
                MAX(player_name) as player_name,
                AVG(CASE WHEN total_time > 0 THEN (total_damage::numeric / total_time * 60) ELSE 0 END) as value,
                COUNT(*) as sessions_played
            FROM session_player
            GROUP BY player_guid
        )
        SELECT player_guid, player_name, value, sessions_played
        FROM session_dpm
        ORDER BY value DESC
        LIMIT $2
    """
    dpm_rows = []
    try:
        dpm_rows = await db.fetch_all(dpm_query, (start_date, limit))
    except Exception as e:
        logger.warning("DPM primary query failed, will retry with fallback: %s", e)
        dpm_rows = []

    if not dpm_rows:
        fallback_dpm = """
            WITH session_player AS (
                SELECT
                    r.gaming_session_id,
                    p.player_guid,
                    MAX(p.player_name) as player_name,
                    SUM(p.damage_given) as total_damage,
                    SUM(p.time_played_seconds) as total_time
                FROM player_comprehensive_stats p
                INNER JOIN rounds r
                    ON r.round_date = p.round_date
                    AND r.map_name = p.map_name
                    AND r.round_number = p.round_number
                WHERE r.gaming_session_id IS NOT NULL
                  AND r.round_number IN (1, 2)
                  AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                  AND p.time_played_seconds > 0
                  AND CAST(SUBSTR(CAST(r.round_date AS TEXT), 1, 10) AS DATE) >= $1
                GROUP BY r.gaming_session_id, p.player_guid
            ),
            session_dpm AS (
                SELECT
                    player_guid,
                    MAX(player_name) as player_name,
                    AVG(CASE WHEN total_time > 0 THEN (total_damage::numeric / total_time * 60) ELSE 0 END) as value,
                    COUNT(*) as sessions_played
                FROM session_player
                GROUP BY player_guid
            )
            SELECT player_guid, player_name, value, sessions_played
            FROM session_dpm
            ORDER BY value DESC
            LIMIT $2
        """
        try:
            dpm_rows = await db.fetch_all(fallback_dpm, (start_date, limit))
        except Exception as fallback_exc:
            # Last-resort SQLite fallback: legacy schema keys by session_id /
            # session_date and has no round_date column on
            # player_comprehensive_stats, so neither the primary nor the first
            # fallback succeeds.
            fallback_session_dpm = """
                WITH session_player AS (
                    SELECT
                        p.session_id,
                        p.player_guid,
                        MAX(p.player_name) as player_name,
                        SUM(p.damage_given) as total_damage,
                        SUM(p.time_played_seconds) as total_time
                    FROM player_comprehensive_stats p
                    WHERE p.session_id IS NOT NULL
                      AND p.round_number IN (1, 2)
                      AND p.time_played_seconds > 0
                      AND CAST(SUBSTR(CAST(p.session_date AS TEXT), 1, 10) AS DATE) >= $1
                    GROUP BY p.session_id, p.player_guid
                ),
                session_dpm AS (
                    SELECT
                        player_guid,
                        MAX(player_name) as player_name,
                        AVG(CASE WHEN total_time > 0 THEN (total_damage::numeric / total_time * 60) ELSE 0 END) as value,
                        COUNT(*) as sessions_played
                    FROM session_player
                    GROUP BY player_guid
                )
                SELECT player_guid, player_name, value, sessions_played
                FROM session_dpm
                ORDER BY value DESC
                LIMIT $2
            """
            logger.warning(
                "DPM fallback failed, trying session-based fallback: %s", fallback_exc
            )
            try:
                dpm_rows = await db.fetch_all(fallback_session_dpm, (start_date, limit))
            except Exception as session_exc:
                logger.error(
                    "DPM session fallback also failed: %s", session_exc, exc_info=True
                )
                errors.append("dpm_query_failed")
                dpm_rows = []
    # Batch resolve display names instead of N+1 per-row lookup.
    dpm_name_map = await batch_resolve_display_names(
        db, [(row[0], row[1] or "Unknown") for row in dpm_rows]
    )
    dpm_leaders = []
    for i, row in enumerate(dpm_rows):
        dpm_leaders.append(
            {
                "rank": i + 1,
                "guid": row[0],
                "name": dpm_name_map.get(row[0], row[1] or "Unknown"),
                "value": float(row[2] or 0),
                "sessions": row[3] or 0,
                "label": "DPM/session",
            }
        )

    return {
        "window_days": 7,
        "xp": xp_leaders,
        "dpm_sessions": dpm_leaders,
        "errors": errors,
    }


@router.get("/player/{player_name}/matches")
async def get_player_matches(
    player_name: str,
    limit: int = 10,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Get recent match history for a specific player.
    """
    player_guid = await resolve_player_guid(db, player_name)
    use_guid = player_guid is not None
    identifier = player_guid if use_guid else player_name

    # ⛔ ROUND-LEVEL FIELDS THE ROUND ALREADY HAS.
    # This returned 13 fields while the row carries 39 populated ones, and the
    # three it omitted — gibs, damage_received, time_played_seconds — are the
    # ones a player asks about first. The website had no other per-round path
    # to them: the session matrix drops damage_received too, so "how much did I
    # take" was answerable nowhere outside a Discord command.
    #
    # `round_status` comes along because a cancelled round is still a round the
    # player played. Filtering it out here would repeat the defect the session
    # endpoint has: the row vanishes and nothing says why.
    query = """
        SELECT
            pcs.round_id,
            pcs.round_date,
            pcs.map_name,
            pcs.round_number,
            pcs.kills,
            pcs.deaths,
            pcs.damage_given,
            pcs.time_played_seconds,
            pcs.team,
            pcs.xp,
            pcs.accuracy,
            pcs.gibs,
            pcs.damage_received,
            pcs.headshot_kills,
            pcs.revives_given,
            r.round_status,
            r.gaming_session_id
        FROM player_comprehensive_stats pcs
        LEFT JOIN rounds r ON r.id = pcs.round_id
        WHERE pcs.player_guid = $1
          -- Codex on #855, twice over: without the round filter the R0
          -- match-summary aggregates render as if they were rounds (the
          -- recorded fixture carried round 10208 with round_number 0), and
          -- ordering by the date-only round_date groups every R2 ahead of
          -- every R1 within a day, so LIMIT could drop the newest rounds.
          -- round_id is monotonic — the same ordering the profile uses.
          AND pcs.round_number IN (1, 2)
        ORDER BY pcs.round_id DESC
        LIMIT $2
    """
    if not use_guid:
        query = query.replace("pcs.player_guid = $1", "pcs.player_name ILIKE $1")

    try:
        rows = await db.fetch_all(query, (identifier, limit))
    except Exception as e:
        logger.error(f"Error fetching player matches: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not rows:
        return []

    matches = []
    for row in rows:
        time_played = row[7] or 0
        dpm = (row[6] / (time_played / 60)) if time_played > 0 else 0
        kd = row[4] / row[5] if row[5] > 0 else row[4]

        matches.append(
            {
                "round_id": row[0],
                "round_date": row[1],
                "map_name": row[2],
                "round_number": row[3],
                "kills": row[4],
                "deaths": row[5],
                "damage": row[6],
                "time_played": time_played,
                "team": row[8],
                "xp": row[9],
                "accuracy": row[10],
                "dpm": round(dpm, 1),
                "kd": round(kd, 2),
                "gibs": row[11] or 0,
                "damage_received": row[12] or 0,
                "headshot_kills": row[13] or 0,
                "revives_given": row[14] or 0,
                #: 'cancelled' rounds were played and have rows; the caller
                #: decides whether to count them, but must be able to SEE them.
                "round_status": row[15],
                "gaming_session_id": row[16],
            }
        )

    return matches


@router.get("/stats/player/{player_name}/form")
async def get_player_form(
    player_name: str,
    limit: int = 20,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Get player's recent form - session DPM (aggregated per gaming session).
    """
    player_guid = await resolve_player_guid(db, player_name)
    use_guid = player_guid is not None
    identifier = player_guid if use_guid else player_name

    query = """
        SELECT
            r.gaming_session_id,
            MIN(p.round_date) as session_date,
            SUM(p.damage_given) as total_damage,
            SUM(p.time_played_seconds) as total_time,
            COUNT(*) as rounds_played,
            SUM(p.kills) as total_kills,
            SUM(p.deaths) as total_deaths
        FROM player_comprehensive_stats p
        JOIN rounds r ON p.round_id = r.id
        WHERE p.player_guid = $1
        AND p.time_played_seconds > 0
        AND r.gaming_session_id IS NOT NULL
        GROUP BY r.gaming_session_id
        HAVING SUM(p.time_played_seconds) > 120
        ORDER BY MIN(p.round_date) DESC
        LIMIT $2
    """
    if not use_guid:
        query = query.replace("p.player_guid = $1", "p.player_name ILIKE $1")

    try:
        rows = await db.fetch_all(query, (identifier, limit))
    except Exception as e:
        logger.error(f"Error fetching player form: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not rows:
        return {"sessions": [], "avg_dpm": 0, "trend": "insufficient_data"}

    sessions = []
    for row in reversed(rows):
        total_time = row[3] or 0
        time_min = total_time / 60 if total_time > 0 else 1
        dpm = round((row[2] or 0) / time_min, 1)
        kills = row[5] or 0
        deaths = row[6] or 0
        kd = round(kills / deaths, 2) if deaths > 0 else kills

        date_obj = row[1]
        if isinstance(date_obj, str):
            date_obj = datetime.strptime(date_obj, "%Y-%m-%d")  # noqa: DTZ007 date-only parsing, no time component used
        label = date_obj.strftime("%b %d")

        sessions.append(
            {
                "label": label,
                "date": str(row[1]),
                "dpm": dpm,
                "rounds": row[4],
                "kd": kd,
            }
        )

    dpms = [s["dpm"] for s in sessions]
    avg_dpm = round(sum(dpms) / len(dpms), 1)

    if len(dpms) >= 6:
        early_avg = sum(dpms[:3]) / 3
        recent_avg = sum(dpms[-3:]) / 3
        if recent_avg > early_avg * 1.1:
            trend = "improving"
        elif recent_avg < early_avg * 0.9:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "insufficient_data"

    return {"sessions": sessions, "avg_dpm": avg_dpm, "trend": trend}


@router.get("/stats/player/{player_name}/rounds")
async def get_player_rounds(
    player_name: str,
    limit: int = 30,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Get player's recent per-round DPM (individual maps).
    """
    player_guid = await resolve_player_guid(db, player_name)
    use_guid = player_guid is not None
    identifier = player_guid if use_guid else player_name

    query = """
        SELECT
            p.round_date,
            p.map_name,
            p.damage_given,
            p.time_played_seconds
        FROM player_comprehensive_stats p
        WHERE p.player_guid = $1
        AND p.time_played_seconds > 60
        ORDER BY p.round_date DESC, p.round_id DESC
        LIMIT $2
    """
    if not use_guid:
        query = query.replace("p.player_guid = $1", "p.player_name ILIKE $1")

    try:
        rows = await db.fetch_all(query, (identifier, limit))
    except Exception as e:
        logger.error(f"Error fetching player rounds: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not rows:
        return {"rounds": [], "avg_dpm": 0}

    rounds = []
    for row in reversed(rows):
        time_min = row[3] / 60 if row[3] > 0 else 1
        dpm = round(row[2] / time_min, 1)
        raw_map = row[1] or "Unknown"
        short_map = (
            raw_map
            .replace("maps/", "")
            .replace("maps\\", "")
        )
        if short_map.lower().endswith((".bsp", ".pk3", ".arena")):
            short_map = short_map.rsplit(".", 1)[0]
        if len(short_map) > 12:
            short_map = short_map[:12]

        rounds.append(
            {
                "label": short_map,
                "date": str(row[0]),
                "dpm": dpm,
            }
        )

    dpms = [r["dpm"] for r in rounds]
    avg_dpm = round(sum(dpms) / len(dpms), 1)

    return {"rounds": rounds, "avg_dpm": avg_dpm}


@router.get("/rounds/{round_id}/player/{player_guid}/details")
async def get_player_round_details(
    round_id: int,
    player_guid: str,
    db: DatabaseAdapter = Depends(get_db)
):
    """
    Get detailed breakdown for a specific player in a specific round.
    Includes weapon stats, objectives, support stats, and sprees.
    """
    # Get round info
    round_query = "SELECT map_name, round_number, round_date FROM rounds WHERE id = $1"
    round_row = await db.fetch_one(round_query, (round_id,))

    if not round_row:
        raise HTTPException(status_code=404, detail="Round not found")

    map_name, round_number, round_date = round_row

    # Get comprehensive player stats
    stats_query = """
        SELECT
            player_name, kills, deaths, damage_given, damage_received,
            time_played_seconds, headshot_kills, headshots, gibs, revives_given, times_revived,
            accuracy, bullets_fired, team_kills, self_kills,
            most_useful_kills, useless_kills, denied_playtime,
            objectives_stolen, objectives_returned, dynamites_planted, dynamites_defused,
            double_kills, triple_kills, quad_kills, multi_kills, mega_kills,
            time_dead_minutes, xp, kill_assists
        FROM player_comprehensive_stats
        WHERE round_date = $1
          AND map_name = $2
          AND round_number = $3
          AND player_guid = $4
        LIMIT 1
    """
    stats = await db.fetch_one(stats_query, (round_date, map_name, round_number, player_guid))

    if not stats:
        raise HTTPException(status_code=404, detail="Player stats not found")

    # Get weapon stats
    weapon_query = """
        SELECT weapon_name, kills, deaths, headshots, hits, shots, accuracy
        FROM weapon_comprehensive_stats
        WHERE round_date = $1
          AND map_name = $2
          AND round_number = $3
          AND player_guid = $4
        ORDER BY kills DESC
    """
    weapons = await db.fetch_all(weapon_query, (round_date, map_name, round_number, player_guid))
    total_hits = sum((w[4] or 0) for w in weapons)

    (
        player_name,
        kills,
        deaths,
        damage_given,
        damage_received,
        time_played_seconds,
        headshot_kills,
        headshots,
        gibs,
        revives_given,
        times_revived,
        accuracy,
        bullets_fired,
        team_kills,
        self_kills,
        useful_kills,
        useless_kills,
        denied_playtime,
        objectives_stolen,
        objectives_returned,
        dynamites_planted,
        dynamites_defused,
        double_kills,
        triple_kills,
        quad_kills,
        multi_kills,
        mega_kills,
        time_dead_minutes,
        xp,
        kill_assists,
    ) = stats

    # Format response
    return {
        "player_name": player_name,
        "round": {
            "id": round_id,
            "map_name": map_name,
            "round_number": round_number,
            "round_date": str(round_date)
        },
        "combat": {
            "kills": kills or 0,
            "deaths": deaths or 0,
            "damage_given": damage_given or 0,
            "damage_received": damage_received or 0,
            "headshot_kills": headshot_kills or 0,
            "headshots": headshots or 0,
            "gibs": gibs or 0,
            "accuracy": round(accuracy or 0, 1),
            "shots": bullets_fired or 0,
            "hits": total_hits,
        },
        "support": {
            "revives_given": revives_given or 0,
            "times_revived": times_revived or 0,
            "useful_kills": useful_kills or 0,
            "useless_kills": useless_kills or 0,
            "kill_assists": kill_assists or 0,
        },
        "objectives": {
            "stolen": objectives_stolen or 0,
            "returned": objectives_returned or 0,
            "dynamites_planted": dynamites_planted or 0,
            "dynamites_defused": dynamites_defused or 0,
        },
        "sprees": {
            "double_kills": double_kills or 0,
            "triple_kills": triple_kills or 0,
            "quad_kills": quad_kills or 0,
            "multi_kills": multi_kills or 0,
            "mega_kills": mega_kills or 0,
        },
        "time": {
            "played_seconds": time_played_seconds or 0,
            "dead_minutes": time_dead_minutes or 0,
            "denied_playtime": denied_playtime or 0,
        },
        "misc": {
            "xp": xp or 0,
            "team_kills": team_kills or 0,
            "self_kills": self_kills or 0,
        },
        "weapons": [
            {
                "name": w[0],
                "kills": w[1] or 0,
                "deaths": w[2] or 0,
                "headshots": w[3] or 0,
                "hits": w[4] or 0,
                "shots": w[5] or 0,
                "accuracy": round(w[6] or 0, 1)
            }
            for w in weapons
        ]
    }
