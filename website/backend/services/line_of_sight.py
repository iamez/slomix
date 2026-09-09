"""Line of sight between placed players — an ORACLE DIAGNOSTIC for the spider
web (spec §6.1, §7.4 "exposure", §12 W6).

What a clear ray means, precisely: *there was an unobstructed line between an
observer's eye and at least one point of the target's body in the static
geometry*. That is a **necessary, not sufficient** condition for having seen
someone — facing is unknown between shots (§3.1 B2), and the engine's own
bullet trace also clips runtime entities and antilag positions that no offline
tracer can reproduce (W6 memo). So it is published only in the world view,
labelled as oracle, and it is never a belief source: no consumer may insert
"he knew where the enemy was" because a ray was clear.

Validation: W6 (2026-08-21/22) paired 26,695 offline segments on the eight
project maps against the engine's world-only trace (`et.trap_Trace`,
`passEntityNum = -2`): 99.92 % agreement, 0 hard errors, 9–13 µs per trace
(`scripts/build_w6_trace_fixtures.py`, `docs/SPIDERWEB_STATUS.md`).

Cost, measured on the dev box (2026-09-09): scanning the pk3 tree once per
process 4.9 s (42 maps), loading one map's BSP 0.3 s + patch compile
0.01–0.12 s, one line-of-sight availability (five body points) 0.4–1.5 ms.
A snapshot traces at most every opponent pair in both directions — 36 pairs
for 6 v 6 — so ~25–110 ms, done off the event loop.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from pathlib import Path
from typing import Any, Protocol

from website.backend.map_geometry import (
    BspPointTracer,
    PlayerStance,
    RuntimeGeometryCoverage,
    compile_bsp_patches,
)
from website.backend.map_geometry.pk3_index import Pk3GeometryIndex, Pk3IndexError

logger = logging.getLogger(__name__)

#: Where the game's pk3 tree lives on this host. Unset or missing → the
#: diagnostic is unavailable, with the reason published, never a silent zero.
ETMAIN_DIR_ENV = "ETMAIN_DIR"
DEFAULT_ETMAIN_DIR = "/home/samba/share/etmain"

#: The validation a reader can hold the diagnostic to.
W6_VALIDATION: dict[str, Any] = {
    "measured_at": "2026-08-22",
    "script": "scripts/build_w6_trace_fixtures.py",
    "segments": 26_695,
    "maps": 8,
    "agreement_pct": 99.92,
    "compared_to": "engine et.trap_Trace with passEntityNum=-2 (world-only), paired offline/live fixtures",
    "caveat": (
        "the engine's bullet trace also clips runtime entities and antilag positions "
        "(MASK_SHOT, G_HistoricalTrace); a clear static ray is an upper bound"
    ),
}

SCOPE = (
    "oracle diagnostic, world view only: a clear ray from the observer's eye to at least "
    "one point of the target's body in the static geometry — necessary, not sufficient, "
    "for having seen someone (§6.1); never a belief source"
)

#: The tracker's stance code (player_track samples) → the tracer's stance.
_STANCE = {0: PlayerStance.STANDING, 1: PlayerStance.CROUCHING, 2: PlayerStance.PRONE,
           "standing": PlayerStance.STANDING, "crouching": PlayerStance.CROUCHING,
           "prone": PlayerStance.PRONE}


def stance_of(value: Any) -> PlayerStance | None:
    """0/1/2 (or the words) → stance; anything else is unknown, which the
    tracer reports as `indeterminate / missing_stance` rather than guessing."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        return _STANCE.get(value.lower())
    try:
        # Only a whole number is a code: 0.5 truncated to 0 would turn an
        # unmeasured stance into a "standing" trace (Codex on #1006).
        if isinstance(value, float) and not value.is_integer():
            return None
        return _STANCE.get(int(value))
    except (TypeError, ValueError, OverflowError):
        return None


class Tracer(Protocol):
    def trace_line_of_sight_availability(self, observer_origin, observer_stance, target_origin, target_stance): ...


class GeometryProvider:
    """One pk3 index per process, one tracer per map, built lazily and off
    the event loop. `tracer_for` answers (tracer, geometry label) or
    (None, reason) — the reason is published, so a missing tree on a host
    reads as "no geometry" and not as "nobody could see anyone"."""

    def __init__(self, etmain_dir: str | os.PathLike[str] | None = None):
        self._etmain = Path(etmain_dir or os.environ.get(ETMAIN_DIR_ENV) or DEFAULT_ETMAIN_DIR)
        self._index: Pk3GeometryIndex | None = None
        self._index_error: str | None = None
        self._tracers: dict[str, tuple[Tracer | None, str]] = {}
        self._lock = threading.Lock()

    def _build_index(self) -> None:
        if self._index is not None or self._index_error is not None:
            return
        if not self._etmain.is_dir():
            self._index_error = f"no geometry: {self._etmain} is not a directory on this host"
            return
        try:
            self._index = Pk3GeometryIndex.scan(self._etmain)
        except Exception as exc:  # noqa: BLE001 — the reason is the product
            self._index_error = f"no geometry: scanning {self._etmain} failed ({type(exc).__name__}: {exc})"

    def tracer_for_sync(self, map_name: str | None) -> tuple[Tracer | None, str]:
        if not map_name:
            return None, "no geometry: the round names no map"
        with self._lock:
            if map_name in self._tracers:
                return self._tracers[map_name]
            self._build_index()
            if self._index is None:
                result: tuple[Tracer | None, str] = (None, self._index_error or "no geometry")
            else:
                try:
                    bsp = self._index.load_bsp(map_name)
                    tracer = BspPointTracer(
                        bsp,
                        patch_collisions=compile_bsp_patches(bsp),
                        # Static geometry only: the diagnostic states this in
                        # its scope, so the coverage flags do not downgrade
                        # every result to indeterminate.
                        runtime_entity_completeness=RuntimeGeometryCoverage.VERIFIED,
                        runtime_entity_state=RuntimeGeometryCoverage.VERIFIED,
                    )
                    selected = self._index.resolve(map_name).selected
                    label = f"{map_name} from {selected.pk3_path.name if selected else 'an unknown pk3'}"
                    result = (tracer, label)
                except Pk3IndexError as exc:
                    result = (None, f"no geometry for {map_name}: {exc}")
                except Exception as exc:  # noqa: BLE001
                    logger.warning("line of sight: tracer for %s failed: %s", map_name, exc)
                    result = (None, f"no geometry for {map_name}: {type(exc).__name__}")
            self._tracers[map_name] = result
            return result

    async def tracer_for(self, map_name: str | None) -> tuple[Tracer | None, str]:
        if map_name in self._tracers:
            return self._tracers[map_name]
        return await asyncio.to_thread(self.tracer_for_sync, map_name)


_DEFAULT: GeometryProvider | None = None


def default_provider() -> GeometryProvider:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = GeometryProvider()
    return _DEFAULT


def _verdict(result) -> dict[str, str]:
    return {"status": str(result.status), "reason": str(result.reason)}


def line_of_sight_for_edges(players: dict[str, Any], edges: list[Any], tracer: Tracer) -> dict[tuple[str, str], dict[str, Any]]:
    """Both directions of every OPPONENT edge whose two players are alive
    and placed. Teammate pairs are not traced (a teammate's whereabouts is
    the voice channel's business, §6.2), and a down player neither sees nor
    is a target. Keyed by (a_guid, b_guid) as the edge names them."""
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for e in edges:
        if e.kind != "opponent":
            continue
        a = players.get(e.a_guid)
        b = players.get(e.b_guid)
        if a is None or b is None or not a.alive or not b.alive:
            continue
        if a.x is None or a.y is None or a.z is None or b.x is None or b.y is None or b.z is None:
            continue
        pa = (float(a.x), float(a.y), float(a.z))
        pb = (float(b.x), float(b.y), float(b.z))
        out[(e.a_guid, e.b_guid)] = {
            "a_to_b": _verdict(tracer.trace_line_of_sight_availability(pa, stance_of(a.stance), pb, stance_of(b.stance))),
            "b_to_a": _verdict(tracer.trace_line_of_sight_availability(pb, stance_of(b.stance), pa, stance_of(a.stance))),
        }
    return out


def exposure(players: dict[str, Any], by_edge: dict[tuple[str, str], dict[str, Any]]) -> dict[str, int | None]:
    """Per living player in a traced opponent pair: how many living enemies
    had a clear ray TO them (the §7.4 "exposure" candidate's oracle form).
    Zero is a count, not an absence — a player with no traced pair is simply
    not listed. ⛔ A player with an INDETERMINATE incoming ray and no clear
    one is None, not 0: the tracer could not decide (a missing stance, an
    uncompiled patch), and a zero would turn that into a measurement. With
    at least one clear ray the count stands as a lower bound."""
    clear: dict[str, int] = {}
    undecided: dict[str, int] = {}
    for (a, b), v in by_edge.items():
        for who, incoming in ((a, v["b_to_a"]["status"]), (b, v["a_to_b"]["status"])):
            clear.setdefault(who, 0)
            undecided.setdefault(who, 0)
            if incoming == "clear":
                clear[who] += 1
            elif incoming == "indeterminate":
                undecided[who] += 1
    return {g: (clear[g] if clear[g] > 0 or undecided[g] == 0 else None) for g in clear}


async def annotate(map_name: str | None, players: dict[str, Any], edges: list[Any], *, provider: GeometryProvider | None = None) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, Any]]]:
    """The payload block and the per-edge verdicts for the world view."""
    prov = provider or default_provider()
    tracer, label = await prov.tracer_for(map_name)
    base = {"scope": SCOPE, "validated_by": dict(W6_VALIDATION)}
    if tracer is None:
        return {**base, "available": False, "reason": label, "geometry": None, "pairs_traced": 0, "exposure": {}}, {}
    by_edge = await asyncio.to_thread(line_of_sight_for_edges, players, edges, tracer)
    return {
        **base, "available": True, "reason": None, "geometry": label,
        "pairs_traced": len(by_edge), "exposure": exposure(players, by_edge),
    }, by_edge


def withheld(reason: str) -> dict[str, Any]:
    """The block a point of view gets: nothing traced, and why."""
    return {"scope": SCOPE, "validated_by": dict(W6_VALIDATION), "available": False,
            "reason": reason, "geometry": None, "pairs_traced": 0, "exposure": {}}
