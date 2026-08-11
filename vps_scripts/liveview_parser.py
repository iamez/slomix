"""liveview_parser — turn ``legacy3.log`` lines into structured live events.

S0 of the Live-view plan (docs/research/LIVE_VIEW_RESEARCH_2026-08-11.md).
This module is deliberately **stdlib-only**: the same parser will run inside
the future tail daemon on the game server (S2) and inside the website
ingestion path (S1), and the game box offers no virtualenv.

Source-of-truth grammar: research doc §A.3, verified against 600k historical
lines plus the 2026-08-11 bot-test fixture. Key facts the parser encodes:

- Every line starts with an 8-char right-aligned level time in **ms** (it can
  exceed 8 digits after long uptimes). Level time is *relative* to map load —
  never reconstruct wall clock from it; a jump backwards means map restart.
  Only ``gametime:`` carries an absolute timestamp, once per InitGame.
- ``legacy popup:`` is the most reliable objective feed: fixed grammar
  ``<team> <verb> "<objective>"`` with verbs stole/returned/planted/defused.
- ``legacy announce:`` is free text from the map script (>70 variants; the
  same map differs across pk3 versions) — carry the text through, do NOT
  enum-match it. Stage mapping happens later via map_geometry (S4).
- ``axis:NNN  allies:NNN`` are end-of-round team XP sums, NOT round scores —
  typed as TEAM_XP so nobody mistakes them for a result.
- No GUIDs anywhere: identity is slot+name and that is fine for display,
  but must never be joined to the database by name (project rule).
- Team chat (sayteam/saybuddy/sayteamnl) is recognised so callers can count
  it, but its text is **redacted** at parse time — it must never leave the
  box (research §e).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

COLOR_RE = re.compile(r"\^[0-9a-zA-Z]")


def strip_colors(text: str) -> str:
    """Remove Quake ``^X`` colour codes."""
    return COLOR_RE.sub("", text)


@dataclass
class LiveEvent:
    type: str
    level_ms: int | None
    fields: dict = field(default_factory=dict)
    raw: str = ""


_LINE_RE = re.compile(r"^\s*(\d+)\s(.*)$")

_POPUP_RE = re.compile(r'^legacy popup: (?P<team>\S+?)\^?7? (?P<verb>stole|returned|planted|defused) "(?P<objective>[^"]+)"')
_ANNOUNCE_RE = re.compile(r'^legacy announce: "(?P<text>.*)"\s*$')
_KILL_RE = re.compile(
    r"^Kill: (?P<killer_slot>\d+) (?P<victim_slot>\d+) (?P<mod_id>\d+): "
    r"(?P<killer>.*) killed (?P<victim>.*) by (?P<mod>MOD_\S+)$"
)
_USERINFO_RE = re.compile(r"^ClientUserinfoChanged: (?P<slot>\d+) (?P<info>.*)$")
_ITEM_FLAG_RE = re.compile(r"^Item: (?P<slot>\d+) (?P<item>team_CTF_(?:red|blue)flag)$")
_DYNAMITE_RE = re.compile(r"^Dynamite_(?P<action>Plant|Diffuse): (?P<slot>\d+) (?P<objective>.*)$")
_EXIT_RE = re.compile(r"^Exit: (?P<reason>.+?)\s*$")
_SCORE_RE = re.compile(r"^score: (?P<xp>-?\d+)\s+ping: (?P<ping>-?\d+)\s+client: (?P<slot>\d+) (?P<name>.*)$")
_TEAM_XP_RE = re.compile(r"^axis:(?P<axis>\d+)\s+allies:(?P<allies>\d+)\s*$")
_CALLVOTE_RE = re.compile(r"^callvote: (?P<slot>\d+) (?P<vote>.*)$")
_SAY_RE = re.compile(r"^(?P<kind>say|sayteam|saybuddy|sayteamnl): (?P<rest>.*)$")
_SIMPLE = {
    "map: ": ("MAP", "map_name"),
    "gametype: ": ("GAMETYPE", "gametype"),
    "gametime: ": ("GAMETIME", "wallclock"),
    "ClientConnect: ": ("CONNECT", "slot"),
    "ClientBegin: ": ("BEGIN", "slot"),
    "ClientDisconnect: ": ("DISCONNECT", "slot"),
    "Medic_Revive: ": ("REVIVE", "slots"),
    "Objective_Destroyed: ": ("OBJECTIVE_DESTROYED", "detail"),
    "Health_Pack: ": ("SUPPLY", "slots"),
    "Ammo_Pack: ": ("SUPPLY", "slots"),
    "Shove: ": ("SHOVE", "slots"),
    "Repair: ": ("REPAIR", "slots"),
    "ShutdownGame:": ("SHUTDOWN", "detail"),
    "ExitLevel:": ("EXIT_LEVEL", "detail"),
}
_LUA_EVENTS = {
    "LUA event: Round starting!": "ROUND_START",
    "LUA event: Round ended!": "ROUND_END",
    "LUA event: Stats saved!": "STATS_SAVED",
}


def _userinfo_get(info: str, key: str) -> str | None:
    # userinfo is \-separated: n\<ime>\t\<team>\c\<class>\...
    parts = info.split("\\")
    # a leading key may start at index 0 (no leading backslash)
    for i in range(0, len(parts) - 1):
        if parts[i] == key:
            return parts[i + 1]
    return None


def _xyz(token: str) -> dict:
    parts = token.split(",")
    out = {}
    for key, val in zip(("x", "y", "z"), parts):
        out[key] = int(val) if val.lstrip("-").isdigit() else None
    return out


def _parse_livex(body: str) -> LiveEvent | None:
    """Parse a line from live_events.lua's slomix-live.log (LIVEX grammar).

    Grammar (design doc LIVE_EVENTS_LUA_DESIGN_2026-08-12):
      I <ms> map <name>
      K <ms> <ks> <vs> <mod> <kx,ky,kz> <vx,vy,vz> <khp> <dist>
      A <ms> <slot> <dg> <dr> <k> <d>
      M <ms> <slot>:<x>,<y>[,<yaw>] ...
    Timestamps are absolute epoch-ms (or level-ms fallback); stored as
    level_ms so the existing pipeline treats them uniformly.
    """
    tok = body.split()
    if len(tok) < 2 or not tok[1].isdigit():
        return None
    kind, ms = tok[0], int(tok[1])
    if kind == "K" and len(tok) >= 9:
        return LiveEvent("LIVE_KILL", ms, {
            "killer_slot": int(tok[2]) if tok[2].lstrip("-").isdigit() else None,
            "victim_slot": int(tok[3]) if tok[3].lstrip("-").isdigit() else None,
            "mod_id": int(tok[4]) if tok[4].isdigit() else None,
            "killer_pos": _xyz(tok[5]),
            "victim_pos": _xyz(tok[6]),
            "killer_health": int(tok[7]) if tok[7].lstrip("-").isdigit() else None,
            "distance": int(tok[8]) if tok[8].lstrip("-").isdigit() else None,
        }, raw=body)
    if kind == "A" and len(tok) >= 7:
        nums = [int(t) if t.lstrip("-").isdigit() else 0 for t in tok[2:7]]
        return LiveEvent("LIVE_AGGREGATE", ms, {
            "slot": nums[0], "damage_given": nums[1],
            "damage_received": nums[2], "kills": nums[3], "deaths": nums[4],
        }, raw=body)
    if kind == "M" and len(tok) >= 3:
        players = []
        for t in tok[2:]:
            if ":" not in t:
                continue
            slot, _, coords = t.partition(":")
            c = coords.split(",")
            if not slot.isdigit() or len(c) < 2:
                continue
            entry = {"slot": int(slot),
                     "x": int(c[0]) if c[0].lstrip("-").isdigit() else None,
                     "y": int(c[1]) if c[1].lstrip("-").isdigit() else None}
            if len(c) >= 3 and c[2].lstrip("-").isdigit():
                entry["yaw"] = int(c[2])
            players.append(entry)
        return LiveEvent("LIVE_MOVEMENT", ms, {"players": players}, raw=body)
    if kind == "I" and len(tok) >= 4 and tok[2] == "map":
        return LiveEvent("LIVE_MAP", ms, {"map_name": tok[3]}, raw=body)
    return None


def parse_line(line: str) -> LiveEvent | None:
    """Parse one ``legacy3.log`` line; None when the line carries no event
    we model (Endstats table art, empty lines, vote tallies mid-line...)."""
    m = _LINE_RE.match(line.rstrip("\n"))
    if not m:
        stripped = line.strip()
        # continuation lines (e.g. "         Vote Passed: (Y:4-N:0)")
        if stripped.startswith("Vote Passed:"):
            return LiveEvent("VOTE_PASSED", None, {"detail": stripped}, raw=line)
        # LIVEX lines from live_events.lua's own slomix-live.log start with a
        # single type letter, not a level-time digit, so they land here.
        livex = _parse_livex(stripped)
        if livex is not None:
            return livex
        return None
    level_ms = int(m.group(1))
    body = m.group(2)

    if body.startswith("InitGame:"):
        return LiveEvent("INIT_GAME", level_ms, {}, raw=line)

    for prefix, (etype, fname) in _SIMPLE.items():
        if body.startswith(prefix):
            value = body[len(prefix):].strip()
            fields = {fname: int(value)} if fname == "slot" else {fname: value}
            return LiveEvent(etype, level_ms, fields, raw=line)

    lua = _LUA_EVENTS.get(body.strip())
    if lua:
        return LiveEvent(lua, level_ms, {}, raw=line)

    pm = _POPUP_RE.match(body)
    if pm:
        return LiveEvent("POPUP", level_ms, {
            "team": strip_colors(pm.group("team")).lower(),
            "verb": pm.group("verb"),
            "objective": pm.group("objective"),
        }, raw=line)

    am = _ANNOUNCE_RE.match(body)
    if am:
        return LiveEvent("ANNOUNCE", level_ms, {"text": strip_colors(am.group("text"))}, raw=line)

    km = _KILL_RE.match(body)
    if km:
        return LiveEvent("KILL", level_ms, {
            "killer_slot": int(km.group("killer_slot")),
            "victim_slot": int(km.group("victim_slot")),
            "killer": strip_colors(km.group("killer")),
            "victim": strip_colors(km.group("victim")),
            "mod": km.group("mod"),
        }, raw=line)

    um = _USERINFO_RE.match(body)
    if um:
        info = um.group("info")
        name = _userinfo_get(info, "n") or ""
        team = _userinfo_get(info, "t")
        return LiveEvent("TEAM_CHANGE", level_ms, {
            "slot": int(um.group("slot")),
            "name": strip_colors(name),
            # 1=Axis 2=Allies 3=spectator (research §A.3.3, potrjeno v podatkih)
            "team": int(team) if team is not None and team.lstrip("-").isdigit() else None,
        }, raw=line)

    fm = _ITEM_FLAG_RE.match(body)
    if fm:
        return LiveEvent("FLAG_PICKUP", level_ms, {
            "slot": int(fm.group("slot")),
            "flag": fm.group("item"),
        }, raw=line)

    if body.startswith("Item: "):
        # Non-flag pickups (health, ammo, weapons) — parsed so coverage stays
        # strict; live consumers filter them out.
        rest = body[len("Item: "):].split(" ", 1)
        return LiveEvent("ITEM_PICKUP", level_ms, {
            "slot": int(rest[0]) if rest[0].isdigit() else None,
            "item": rest[1] if len(rest) > 1 else "",
        }, raw=line)

    dm = _DYNAMITE_RE.match(body)
    if dm:
        return LiveEvent("DYNAMITE", level_ms, {
            "action": "plant" if dm.group("action") == "Plant" else "defuse",
            "slot": int(dm.group("slot")),
            "objective": dm.group("objective"),
        }, raw=line)

    em = _EXIT_RE.match(body)
    if em and body.startswith("Exit: "):
        return LiveEvent("EXIT", level_ms, {"reason": em.group("reason")}, raw=line)

    sm = _SCORE_RE.match(body)
    if sm:
        return LiveEvent("SCORELINE", level_ms, {
            "xp": int(sm.group("xp")),
            "ping": int(sm.group("ping")),
            "slot": int(sm.group("slot")),
            "name": strip_colors(sm.group("name")),
        }, raw=line)

    tm = _TEAM_XP_RE.match(body)
    if tm:
        # End-of-round team XP sums — NOT the round score (research §A.3.2).
        return LiveEvent("TEAM_XP", level_ms, {
            "axis_xp": int(tm.group("axis")),
            "allies_xp": int(tm.group("allies")),
        }, raw=line)

    cm = _CALLVOTE_RE.match(body)
    if cm:
        return LiveEvent("CALLVOTE", level_ms, {
            "slot": int(cm.group("slot")),
            "vote": strip_colors(cm.group("vote")),
        }, raw=line)

    ym = _SAY_RE.match(body)
    if ym:
        kind = ym.group("kind")
        if kind == "say":
            rest = strip_colors(ym.group("rest"))
            name, _, text = rest.partition(": ")
            return LiveEvent("SAY", level_ms, {"name": name, "text": text}, raw=line)
        # Team/buddy chat never leaves the box: type kept, text dropped.
        return LiveEvent("TEAM_CHAT_REDACTED", level_ms, {}, raw="")

    return None


def parse_lines(lines) -> list[LiveEvent]:
    """Parse an iterable of lines, skipping non-events."""
    out = []
    for line in lines:
        ev = parse_line(line)
        if ev is not None:
            out.append(ev)
    return out
