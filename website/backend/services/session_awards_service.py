"""Session-level roll-up of the engine's per-round awards (stats 2.0, docs/design/18 §E.2).

`round_awards` holds what the server's endstats Lua handed out after each
round: one (award_name, player, value) per award per round. A session needs
ONE winner per award, which is not "sum every value and sort" — the bot's
aggregator does that and turns `Best K/D ratio` into a meaningless total
and `Least time dead` (a percentage) into an m:ss clock. Every award here
carries an explicit rule: how its per-round values combine (sum / max /
min), which direction wins, what unit the figure is in, and the gibhub-
style nickname + phrase the page renders ("The Damage Dealer award goes to
X for most damage given — 17 139"). Unknown names still roll up (sum,
engine name as nickname) so a new engine award cannot vanish.

Measured 2026-09-03 on 27 202 rows: `award_value_numeric` is populated for
every award except `Tank/Meatshield (Refuses to die)`, whose value is the
text "Damage received vs death ratio: 3.34x" — the ratio is parsed from it
here. `Quickest multikill w/ light weapons` stores the KILL COUNT as its
number ("3 kills in 0.62s" → 3); the time exists only in the text, so the
figure shown is the original text and the rank is by kills. `Least time
dead` / `Full respawn king` are percentages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

Mode = Literal["sum", "max", "min"]
Unit = Literal["count", "seconds", "percent", "ratio", "metres", "kills"]

CATEGORY_ORDER: tuple[str, ...] = (
    "computed", "combat", "skills", "weapons", "teamwork", "objectives", "timing", "deaths", "other",
)
CATEGORY_LABELS: dict[str, str] = {
    "computed": "the night",
    "combat": "combat",
    "skills": "skills",
    "weapons": "weapons",
    "teamwork": "teamwork",
    "objectives": "objectives",
    "timing": "timing",
    "deaths": "deaths & mayhem",
    "other": "other",
}


@dataclass(frozen=True)
class AwardRule:
    nickname: str
    phrase: str
    category: str
    mode: Mode = "sum"
    #: "desc" — the larger figure wins; "asc" — the smaller one does.
    direction: Literal["asc", "desc"] = "desc"
    unit: Unit = "count"
    #: Show the engine's own text instead of a re-formatted number (the
    #: number does not carry the meaning — see Quickest multikill).
    keep_text: bool = False


def _r(nickname: str, phrase: str, category: str, **kw: Any) -> AwardRule:
    return AwardRule(nickname=nickname, phrase=phrase, category=category, **kw)


#: engine award name -> rule. Every name observed in round_awards (44 on
#: 2026-09-03) plus the declared-but-never-seen ones from KNOWN_AWARDS.
AWARD_RULES: dict[str, AwardRule] = {
    # combat
    "Most damage given": _r("Damage Dealer", "most damage given", "combat"),
    "Most damage received": _r("Punching Bag", "most damage taken", "combat"),
    "Most kills per minute": _r("Machine", "most kills per minute", "combat", mode="max", unit="ratio"),
    "Most damage per minute": _r("Firehose", "most damage per minute", "combat", mode="max", unit="ratio"),
    "Best K/D ratio": _r("Best KDR", "the best kill/death ratio", "combat", mode="max", unit="ratio"),
    "Tank/Meatshield (Refuses to die)": _r("Tank", "soaking the most damage per death", "combat", mode="max", unit="ratio"),
    # skills
    "Most headshot kills": _r("Headhunter", "most headshot kills", "skills"),
    "Most headshots": _r("Head Hits", "most headshot hits", "skills"),
    "Highest light weapons accuracy": _r("Sharpshooter", "the best light-weapon accuracy", "skills", mode="max", unit="percent"),
    "Highest headshot accuracy": _r("Laser", "the best headshot accuracy", "skills", mode="max", unit="percent"),
    "Most light weapon kills": _r("Gunslinger", "most light-weapon kills", "skills"),
    "Most pistol kills": _r("Pistolero", "most pistol kills", "skills"),
    "Most rifle kills": _r("Rifleman", "most rifle kills", "skills"),
    "Most sniper kills": _r("Sniper", "most sniper kills", "skills"),
    "Most knife kills": _r("Butcher", "most knife kills", "skills"),
    "Longest killing spree": _r("Killing Spree", "the longest killing spree", "skills", mode="max"),
    "Most multikills": _r("Rampage", "most multikills", "skills"),
    "Most doublekills": _r("Double Trouble", "most double kills", "skills"),
    "Quickest multikill w/ light weapons": _r("Quick Hands", "the quickest multikill", "skills", mode="max", unit="kills", keep_text=True),
    "Most bullets fired": _r("Ammo Hose", "most bullets fired", "skills"),
    # weapons
    "Most grenade kills": _r("Grenadier", "most grenade kills", "weapons"),
    "Most panzer kills": _r("Panzerschreck", "most panzer kills", "weapons"),
    "Most mortar kills": _r("Mortar Man", "most mortar kills", "weapons"),
    "Most mine kills": _r("Minesweeper", "most landmine kills", "weapons"),
    "Most air support kills": _r("Airstrike Caller", "most air-support kills", "weapons"),
    "Most riflenade kills": _r("Riflenade", "most rifle-grenade kills", "weapons"),
    "Farthest riflenade kill": _r("Long Shot", "the farthest rifle-grenade kill", "weapons", mode="max", unit="metres"),
    "Most MG42 kills": _r("MG42 Nest", "most MG42 kills", "weapons"),
    # teamwork
    "Most revives": _r("Needler", "most revives", "teamwork"),
    "Most revived": _r("Lazarus", "being revived the most", "teamwork"),
    "Most kill assists": _r("Wingman", "most kill assists", "teamwork"),
    "Most killsteals": _r("Vulture", "most kill steals", "teamwork"),
    "Most team damage given": _r("Friendly Fire", "most team damage dealt", "teamwork"),
    "Most team damage received": _r("Bullet Sponge", "most team damage taken", "teamwork"),
    # objectives
    "Most dynamites planted": _r("Demolition", "most dynamites planted", "objectives"),
    "Most dynamites defused": _r("Bomb Squad", "most dynamites defused", "objectives"),
    "Most objectives stolen": _r("Objective Hero", "most objectives stolen", "objectives"),
    "Most objectives returned": _r("Guardian", "most objectives returned", "objectives"),
    "Most corpse gibs": _r("Gibber", "most gibs", "objectives"),
    # timing
    "Most useful kills (>Half respawn time left)": _r("Wave Breaker", "most useful kills", "timing"),
    "Most useless kills": _r("Wasted Bullets", "most useless kills", "timing"),
    "Full respawn king": _r("Full Respawn King", "waiting the full respawn the most", "timing", mode="max", unit="percent"),
    "Most playtime denied": _r("Warden", "denying the most playtime", "timing", unit="seconds"),
    "Least time dead (What spawn?)": _r("What Spawn?", "the least time dead", "timing", mode="min", direction="asc", unit="percent"),
    # deaths
    "Most deaths": _r("Cannon Fodder", "most deaths", "deaths"),
    "Most selfkills": _r("Kamikaze", "most self kills", "deaths"),
    "Most teamkills": _r("Teamkiller", "most team kills", "deaths"),
    "Longest death spree": _r("Cold Streak", "the longest death spree", "deaths", mode="max"),
    "Most panzer deaths": _r("Panzer Magnet", "most panzer deaths", "deaths"),
    "Most mortar deaths": _r("Mortar Magnet", "most mortar deaths", "deaths"),
    "Most MG42 deaths": _r("MG42 Magnet", "most MG42 deaths", "deaths"),
    "Mortarmagnet": _r("Mortar Magnet", "most mortar deaths", "deaths"),
}

_TEXT_RATIO_RE = re.compile(r"([\d.]+)\s*x\b")

# --- computed awards (from the same per-player rows the basics table shows) ---
COMPUTED_TOP_FRAGGER = "Top Fragger"
COMPUTED_IPOD = "iPod"
COMPUTED_PLAYTIME = "Playtime"
#: A player who played less than this share of the evening cannot win the
#: fewest-deaths award — leaving early is not survival.
IPOD_MIN_PLAYED_PCT = 50.0


def rule_for(award_name: str) -> AwardRule:
    return AWARD_RULES.get(award_name) or AwardRule(nickname=award_name, phrase=award_name.lower(), category="other")


def numeric_of(award_name: str, value_text: str | None, value_numeric: float | None) -> float | None:
    """The sortable figure — the stored number, or one recovered from the
    text for the one award the parser could not read."""
    if value_numeric is not None:
        return float(value_numeric)
    if value_text:
        m = _TEXT_RATIO_RE.search(value_text)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return None
    return None


def format_value(value: float | None, unit: Unit, text: str | None = None, keep_text: bool = False) -> str:
    if keep_text and text:
        return text
    if value is None:
        return text or "—"
    if unit == "seconds":
        total = int(round(value))
        return f"{total // 60}:{total % 60:02d}"
    if unit == "percent":
        return f"{value:.1f} %"
    if unit == "ratio":
        return f"{value:.2f}"
    if unit == "metres":
        return f"{value:.1f} m"
    if value == int(value):
        return f"{int(value):,}".replace(",", chr(32))
    return f"{value:.1f}"


def sentence(nickname: str, player: str, phrase: str, value: str) -> str:
    return f"The {nickname} award goes to {player} for {phrase} — {value}"


@dataclass
class _Tally:
    player: str
    guid: str | None
    figures: list[float]
    texts: list[str]
    rounds_won: int = 0


def _combined(t: _Tally, mode: Mode) -> float | None:
    if not t.figures:
        return None
    if mode == "sum":
        return float(sum(t.figures))
    if mode == "max":
        return float(max(t.figures))
    return float(min(t.figures))


def roll_up(rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    """rows: (award_name, player_name, player_guid, award_value, award_value_numeric)
    over the session's counted rounds. One winner per award."""
    per_award: dict[str, dict[str, _Tally]] = {}
    for award_name, player_name, player_guid, value_text, value_numeric in rows:
        fig = numeric_of(award_name, value_text, value_numeric)
        key = (player_guid or "").upper()[:8] or f"name:{(player_name or '').lower()}"
        tallies = per_award.setdefault(award_name, {})
        t = tallies.get(key)
        if t is None:
            t = tallies[key] = _Tally(player=player_name or "?", guid=(player_guid or None), figures=[], texts=[])
        t.rounds_won += 1
        if fig is not None:
            t.figures.append(fig)
        if value_text:
            t.texts.append(value_text)
    out: list[dict[str, Any]] = []
    for award_name, tallies in per_award.items():
        rule = rule_for(award_name)
        ranked = sorted(
            tallies.values(),
            key=lambda t, rule=rule: (
                # Figures first; a tally with no figure at all ranks last.
                (_combined(t, rule.mode) is None),
                (-(_combined(t, rule.mode) or 0.0)) if rule.direction == "desc" else (_combined(t, rule.mode) or 0.0),
                -t.rounds_won,
                t.player.lower(),
            ),
        )
        best = ranked[0]
        value = _combined(best, rule.mode)
        # For max/min modes the text that matches the winning figure is the
        # one to show verbatim (Quickest multikill); for sums there is none.
        text = None
        if best.texts and rule.mode != "sum":
            for f, tx in zip(best.figures, best.texts, strict=False):
                if value is not None and f == value:
                    text = tx
                    break
        out.append(
            {
                "engine_name": award_name,
                "nickname": rule.nickname,
                "category": rule.category,
                "player": best.player,
                "guid": best.guid,
                "value": format_value(value, rule.unit, text=text, keep_text=rule.keep_text),
                "value_numeric": value,
                "unit": rule.unit,
                "rounds_won": best.rounds_won,
                "sentence": sentence(rule.nickname, best.player, rule.phrase, format_value(value, rule.unit, text=text, keep_text=rule.keep_text)),
            }
        )
    return out


def computed_awards(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The three awards the engine never hands out, from the basics rows
    (`guid`, `name`, `kills`, `deaths`, `played_pct`)."""
    out: list[dict[str, Any]] = []
    if not players:
        return out
    top = max(players, key=lambda p: (p.get("kills") or 0, -(p.get("deaths") or 0), p.get("name", "")))
    if (top.get("kills") or 0) > 0:
        v = format_value(float(top["kills"]), "count")
        out.append(_computed(COMPUTED_TOP_FRAGGER, "most kills", top, v, float(top["kills"]), "count"))
    eligible = [p for p in players if (p.get("played_pct") or 0) >= IPOD_MIN_PLAYED_PCT]
    if eligible:
        ipod = min(eligible, key=lambda p: (p.get("deaths") or 0, -(p.get("kills") or 0), p.get("name", "")))
        v = format_value(float(ipod.get("deaths") or 0), "count")
        out.append(_computed(COMPUTED_IPOD, "the fewest deaths", ipod, v, float(ipod.get("deaths") or 0), "count"))
    played = [p for p in players if p.get("played_pct") is not None]
    if played:
        pt = max(played, key=lambda p: (p["played_pct"], p.get("name", "")))
        v = format_value(float(pt["played_pct"]), "percent")
        out.append(_computed(COMPUTED_PLAYTIME, "the highest playtime", pt, v, float(pt["played_pct"]), "percent"))
    return out


def _computed(nickname: str, phrase: str, p: dict[str, Any], value: str, numeric: float, unit: Unit) -> dict[str, Any]:
    return {
        "engine_name": nickname,
        "nickname": nickname,
        "category": "computed",
        "player": p.get("name") or "?",
        "guid": p.get("guid"),
        "value": value,
        "value_numeric": numeric,
        "unit": unit,
        "rounds_won": 0,
        "sentence": sentence(nickname, p.get("name") or "?", phrase, value),
    }


def group_by_category(awards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for a in awards:
        buckets.setdefault(a["category"], []).append(a)
    out = [
        {"key": key, "label": CATEGORY_LABELS.get(key, key), "awards": buckets[key]}
        for key in CATEGORY_ORDER
        if key in buckets
    ]
    out.extend({"key": key, "label": key, "awards": items} for key, items in buckets.items() if key not in CATEGORY_ORDER)
    return out
