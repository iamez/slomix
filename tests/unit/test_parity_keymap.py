"""H2 finally answers its question: the keymap joins two vocabularies.

`docs/parity/inventory.json` froze the LEGACY DOM (2026-08-27) under human
route names and panel titles; the SPA marks panels with `parity="route.slug"`.
The two key sets have no intersection by construction, so the parity audit
could never actually compare them (plan 2c). `docs/parity/keymap.json` is the
join. This test enforces that the join is total and truthful:

- the keymap covers EXACTLY the inventory's route keys (drift in either
  direction fails — a renamed inventory key must not leave a stale mapping);
- every inventory panel title, tab and table key of a mapped route has an
  entry, and every entry either names a parity key that EXISTS in the SPA
  source, or carries an explicit status with a note;
- the amount of named debt is pinned, so a new inventory item cannot slide
  into "unmapped" without this file changing in review.

Structural reading, not prose: parity keys are collected from the SPA source
with a regex over `parity="…"` attributes, which is the same shape the
runtime attribute carries; a key that only appears in a comment cannot
satisfy it because the sources are stripped of comments first.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INVENTORY = REPO / "docs" / "parity" / "inventory.json"
KEYMAP = REPO / "docs" / "parity" / "keymap.json"
APP_SRC = REPO / "website" / "frontend" / "src" / "app"

STATUSES = {"phase-5", "phase-6", "phase-7", "retired", "unmapped"}

# Growth is fine (a page maps more of the inventory); shrinkage of coverage —
# a mapped panel demoted to a status — moves this number UP and must be a
# reviewed, deliberate edit of this line.
UNMAPPED_BUDGET = 2  # Map Distribution (home), Charts (session-detail)

_PARITY_RE = re.compile(r'parity="([a-z0-9.-]+)"')
_COMMENT_RE = re.compile(r"/\*.*?\*/|(?<![:\\'\"])//[^\n]*", re.S)


def _spa_parity_keys() -> set[str]:
    keys: set[str] = set()
    for f in APP_SRC.rglob("*.tsx"):
        if f.name.endswith((".test.tsx",)):
            continue
        text = _COMMENT_RE.sub("", f.read_text(encoding="utf-8"))
        keys.update(_PARITY_RE.findall(text))
    return keys


def _load() -> tuple[dict, dict]:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    keymap = json.loads(KEYMAP.read_text(encoding="utf-8"))
    return inventory, keymap


def _inventory_pieces(route: dict) -> set[str]:
    pieces: set[str] = set()
    pieces.update(route.get("panelTitles") or [])
    pieces.update(route.get("tabs") or [])
    pieces.update((route.get("tableColumns") or {}).keys())
    return pieces


def test_keymap_covers_exactly_the_inventory_routes():
    inventory, keymap = _load()
    inv_keys = set(inventory["routes"])
    map_keys = set(keymap["routes"])
    assert inv_keys == map_keys, (
        f"missing from keymap: {sorted(inv_keys - map_keys)}; stale in keymap: {sorted(map_keys - inv_keys)}"
    )


def test_every_piece_is_mapped_or_carries_a_named_status():
    inventory, keymap = _load()
    spa_keys = _spa_parity_keys()
    assert spa_keys, "no parity keys found in the SPA source — the collector is broken"
    problems: list[str] = []
    for route_key, route in inventory["routes"].items():
        entry = keymap["routes"][route_key]
        if "status" in entry:
            if entry["status"] not in STATUSES:
                problems.append(f"{route_key}: unknown status {entry['status']!r}")
            if not entry.get("note"):
                problems.append(f"{route_key}: a status needs a note")
            continue
        panels = entry.get("panels")
        if panels is None:
            problems.append(f"{route_key}: mapped route without a panels object")
            continue
        for piece in sorted(_inventory_pieces(route)):
            got = panels.get(piece)
            if got is None:
                problems.append(f"{route_key}: {piece!r} has no keymap entry")
            elif "parity" in got:
                if got["parity"] not in spa_keys:
                    problems.append(f"{route_key}: {piece!r} maps to {got['parity']!r}, which no SPA source carries")
            elif got.get("status") not in STATUSES or not got.get("note"):
                problems.append(f"{route_key}: {piece!r} needs parity, or status+note")
    assert not problems, "\n".join(problems)


def test_named_debt_is_pinned():
    inventory, keymap = _load()
    unmapped = [
        f"{route_key}: {piece}"
        for route_key, entry in keymap["routes"].items()
        if "panels" in entry
        for piece, val in entry["panels"].items()
        if val.get("status") == "unmapped"
    ]
    assert len(unmapped) == UNMAPPED_BUDGET, (
        f"unmapped debt is {len(unmapped)}, budget {UNMAPPED_BUDGET}: {unmapped} — "
        "mapping a piece lowers the budget here; demoting one raises it, and "
        "both are review-visible edits of this file"
    )
