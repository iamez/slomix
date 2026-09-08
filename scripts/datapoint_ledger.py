#!/usr/bin/env python3
"""Datapoint ledger — which keys of each recorded API response the new SPA reads.

Why: "capture everything" is the house rule (owner, 2026-09-07), and the
2026-09-07 audits found ~470 response keys the new app fetches and never
reads (player profile lifetime counters, the live "tonight" header, aim
circular statistics, storytelling sub-metrics, …). Endpoint-level
ratchets cannot see that: a page that calls an endpoint and prints one
field of it counts as covered. This is the field-level instrument.

Method (deliberately the same one the audits used, so the numbers agree):

- Endpoints = the paths the app calls (apiGet/apiPost/fetch literals in
  website/frontend/src/app, tests excluded), mapped to their recorded
  fixture the way lib/fixturesCoverage.test.ts maps them
  (`/api/stats/player/{player_name}/form` -> api_stats_player_player_name_form.json).
- Keys = every top-level key of the fixture plus one level below it (for a
  list, the first element's keys). Map-valued objects — keys that are data,
  not fields (a nick, a date, a guid) — are recorded as ONE `<map>` entry
  and marked `dropped: data-map` automatically.
- Read = the key's name occurs in src/app source (tests excluded, comments
  stripped the way src/app/testing/sourceText.ts strips them) as `.key`,
  `['key']`, `"key"`/`'key'`, or `key:`/`key,`/`key }` inside a
  destructuring. A name match, so it is an UPPER bound on rendering; a
  key that appears nowhere cannot be rendered, which is the half that
  matters for a ratchet.
- Decisions = docs/parity/datapoint_decisions.json: `{"<endpoint> <key>":
  "<reason>"}` for keys that are read dynamically (Object.entries), are
  debug/internal, or were dropped on purpose; `"<endpoint> <prefix>.*"`
  covers a whole sub-object. A decision needs a reason; the test refuses
  an empty one, and a decision that names a key no fixture carries is an
  error too (it would be a stale allowance).

Output: docs/parity/datapoints.json — sorted rows
`{"endpoint", "key", "status": "read"|"unread"|"dropped", "reason"?}`, the
endpoints whose recording is empty (`unmeasured`), and a summary. The
ratchet is docs/parity/datapoints_unread_baseline.txt: one line per unread
row; the script only ever removes lines from it (`--rebase-baseline`), so a
new unread row fails the test even after the ledger is regenerated. `--check`
exits 1 when the committed ledger differs from a fresh run.

Usage:
  python scripts/datapoint_ledger.py            # rewrite docs/parity/datapoints.json
  python scripts/datapoint_ledger.py --check    # compare, exit 1 on drift
  python scripts/datapoint_ledger.py --summary  # counts per endpoint to stdout
  python scripts/datapoint_ledger.py --rebase-baseline  # after reading keys: drop them from the baseline
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "website" / "frontend" / "src" / "app"
FIXTURES = APP / "pages" / "__fixtures__"
LEDGER = REPO / "docs" / "parity" / "datapoints.json"
DECISIONS = REPO / "docs" / "parity" / "datapoint_decisions.json"
# The ratchet: every unread row, one per line, `<endpoint> <key>`. The script
# never adds to it; `--rebase-baseline` only DROPS lines whose key is read
# now. A new unread row therefore fails the test even after the ledger is
# regenerated — a sum could not tell one loss from an unrelated gain.
BASELINE = REPO / "docs" / "parity" / "datapoints_unread_baseline.txt"

# READ paths only. A write's response (apiPost/apiPatch/apiDelete/apiUpload)
# is a receipt, not a datapoint a visitor sees, and the corpus records those
# under per-operation names the path cannot predict — so the ledger is the
# ledger of what the app READS. Any quoted `/api/...` literal counts: the
# proximity and storytelling hooks hand their path to a helper that calls
# apiGet, which a call-site regex never sees (Codex on #978).
_READ_PATH_RES = [
    re.compile(r"\bapiGet(?:<[^>]{0,200}>)?\(\s*'([^']+)'"),
    re.compile(r"\bfetch\(\s*'(/api/[^'?]+)'"),
    re.compile(r"['\"](/api/[a-zA-Z0-9/_{}-]+)['\"]"),
]
_WRITE_HINT_RE = re.compile(r"\b(?:apiPost|apiPatch|apiDelete|apiPut|apiUpload\w*)\(\s*'([^']+)'")
_BLOCK_COMMENT = re.compile(r"/\*[\s\S]*?\*/")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def strip_js_comments(text: str) -> str:
    """Same rule as src/app/testing/sourceText.ts: block comments, then lines
    that begin with `//` or a `*` continuation — never mid-line."""
    text = _BLOCK_COMMENT.sub("", text)
    return "\n".join(line for line in text.split("\n") if not re.match(r"^\s*(//|\*)", line))


def app_sources() -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(APP.rglob("*.ts*")):
        name = p.name
        if name.endswith((".test.ts", ".test.tsx", ".d.ts")) or "__fixtures__" in p.parts:
            continue
        # A declaration is not a read: lib/types.ts names every key of every
        # response, so counting it would mark the whole ledger "read" (the
        # audits' upper-bound caveat). The generated OpenAPI types likewise.
        if p.relative_to(APP).as_posix() == "lib/types.ts" or "generated" in p.parts:
            continue
        out[str(p.relative_to(APP))] = strip_js_comments(p.read_text(encoding="utf-8", errors="ignore"))
    return out


def called_paths(sources: dict[str, str]) -> set[str]:
    """Paths the app reads. A path that is ONLY ever handed to a write call
    is left out; one used by both a read and a write stays."""
    paths: set[str] = set()
    writes: set[str] = set()
    for file, text in sources.items():
        if file.endswith("probes.ts"):
            continue
        for rx in _READ_PATH_RES:
            for m in rx.finditer(text):
                paths.add(m.group(1))
        for m in _WRITE_HINT_RE.finditer(text):
            writes.add(m.group(1))
    reads_by_get = set()
    for text in sources.values():
        for rx in _READ_PATH_RES[:2]:
            reads_by_get.update(m.group(1) for m in rx.finditer(text))
    return {p for p in paths if p not in writes or p in reads_by_get}


def fixture_name_for(api_path: str) -> str:
    return re.sub(r"[/-]", "_", re.sub(r"[{}]", "", api_path.lstrip("/"))) + ".json"


_HEX_ID = re.compile(r"^[0-9A-Fa-f]{8}([0-9A-Fa-f]{24})?$")


def _is_data_map(obj: dict[str, Any]) -> bool:
    """A dict whose keys are values (nicks, dates, guids) rather than field
    names. Three tells, any one enough: most keys are not identifiers; the
    keys are 8/32-hex ids; or there are several keys and every value is a
    dict with the same key set — a table keyed by id, like
    greatshot's `player_stats.<nick>` (Codex on #978)."""
    keys = list(obj.keys())
    if len(keys) < 2:
        return False
    if sum(1 for k in keys if _HEX_ID.match(k)) >= len(keys) / 2:
        return True
    if len(keys) >= 4 and sum(1 for k in keys if not _IDENT.match(k)) >= len(keys) / 2:
        return True
    values = list(obj.values())
    if len(keys) >= 3 and all(isinstance(v, dict) for v in values):
        shapes = {tuple(sorted(v.keys())) for v in values}
        if len(shapes) == 1 and len(values[0]) >= 2:
            return True
    return False


def _merged(v: Any) -> dict[str, Any] | None:
    """A dict as itself; a list of dicts as the UNION of its elements' keys
    (a heterogeneous list — timeline events, moments — carries keys only
    its later elements have; Codex on #978)."""
    if isinstance(v, dict):
        return v
    if isinstance(v, list) and v and all(isinstance(x, dict) for x in v[:200]):
        merged: dict[str, Any] = {}
        for x in v[:200]:
            for k, val in x.items():
                merged.setdefault(k, val)
        return merged
    return None


def leaf_keys(payload: Any) -> list[tuple[str, str]] | None:
    """(key, kind) pairs: top-level keys and one level below; kind is
    'field' or 'data-map'. None when the recording is EMPTY (an empty list
    or object): an empty answer proves no schema, so the endpoint is
    reported as unmeasured rather than as covered."""
    out: list[tuple[str, str]] = []
    if payload in ([], {}, None):
        return None
    root = _merged(payload)
    if root is None:
        return None
    if _is_data_map(root):
        return [("<map>", "data-map")]
    for k, v in root.items():
        out.append((k, "field"))
        child = _merged(v)
        if child is None:
            continue
        if _is_data_map(child):
            out.append((f"{k}.<map>", "data-map"))
            continue
        out.extend((f"{k}.{ck}", "field") for ck in child)
    return out


_REF_TOKEN_RES = (
    re.compile(r"\.([A-Za-z_]\w*)\b"),                 # obj.key
    re.compile(r"['\"]([A-Za-z_]\w*)['\"]"),             # 'key' / "key" (also obj['key'])
    re.compile(r"(?<![\w.])([A-Za-z_]\w*)\s*[:,}]"),   # { key, other } / { key: v }
)


def referenced_names(corpus: str) -> set[str]:
    """Every identifier the corpus reads as a property, a quoted key or a
    destructured name — built once, so each ledger key is a set lookup
    rather than four regex passes over 1.5 MB of source."""
    names: set[str] = set()
    for rx in _REF_TOKEN_RES:
        names.update(rx.findall(corpus))
    return names


def build(sources: dict[str, str], decisions: dict[str, str]) -> dict[str, Any]:
    names = referenced_names("\n".join(sources.values()))

    def is_read(leaf: str) -> bool:
        return leaf.split(".")[-1] in names

    rows: list[dict[str, Any]] = []
    unmeasured: list[str] = []
    # One row set per CALLED PATH, even when two paths share a fixture name
    # (`/api/stats/weapons/by_player` and `/by-player` both map to
    # api_stats_weapons_by_player.json) — dropping the second hid a call.
    for path in sorted(called_paths(sources)):
        fx = FIXTURES / fixture_name_for(path)
        if not fx.exists():
            continue  # fixturesCoverage.test.ts is the guard for that
        try:
            payload = json.loads(fx.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        keys = leaf_keys(payload)
        if keys is None:
            unmeasured.append(path)
            continue
        for key, kind in keys:
            decision_key = f"{path} {key}"
            if kind == "data-map":
                rows.append({"endpoint": path, "key": key, "status": "dropped", "reason": "data-map: keys are values, not fields"})
                continue
            reason = decisions.get(decision_key) or next(
                (v for k, v in decisions.items() if k.endswith(".*") and decision_key.startswith(k[:-1])), None
            )
            if reason:
                rows.append({"endpoint": path, "key": key, "status": "dropped", "reason": reason})
                continue
            rows.append({"endpoint": path, "key": key, "status": "read" if is_read(key) else "unread"})
    rows.sort(key=lambda r: (r["endpoint"], r["key"]))
    counts = {"read": 0, "unread": 0, "dropped": 0}
    for r in rows:
        counts[r["status"]] += 1
    per_endpoint: dict[str, dict[str, int]] = {}
    for r in rows:
        d = per_endpoint.setdefault(r["endpoint"], {"read": 0, "unread": 0, "dropped": 0})
        d[r["status"]] += 1
    return {
        "_note": "Generated by scripts/datapoint_ledger.py — do not edit by hand; decisions go to datapoint_decisions.json.",
        "unmeasured": sorted(unmeasured),
        "method": "keys of each called endpoint's recorded fixture (top level + one below) vs a name match over comment-stripped src/app source; a name match is an upper bound on rendering",
        "summary": {**counts, "endpoints": len(per_endpoint), "endpoints_fully_read": sum(1 for d in per_endpoint.values() if d["unread"] == 0), "unmeasured": len(unmeasured)},
        "per_endpoint": per_endpoint,
        "rows": rows,
    }


def load_decisions() -> dict[str, str]:
    if not DECISIONS.exists():
        return {}
    data = json.loads(DECISIONS.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def unread_lines(ledger: dict[str, Any]) -> set[str]:
    return {f"{r['endpoint']} {r['key']}" for r in ledger["rows"] if r["status"] == "unread"}


def render(ledger: dict[str, Any]) -> str:
    return json.dumps(ledger, indent=1, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--rebase-baseline", action="store_true", help="drop baseline lines that are read now (never adds)")
    args = ap.parse_args(argv)
    ledger = build(app_sources(), load_decisions())
    text = render(ledger)
    if args.rebase_baseline:
        current = unread_lines(ledger)
        old = set(BASELINE.read_text(encoding="utf-8").splitlines()) if BASELINE.exists() else set()
        kept = sorted(old & current) if old else sorted(current)
        BASELINE.write_text("\n".join(kept) + "\n", encoding="utf-8")
        print(f"baseline: {len(old)} -> {len(kept)} lines" + ("" if old else " (seeded)"))
        return 0
    if args.summary:
        s = ledger["summary"]
        print(f"read={s['read']} unread={s['unread']} dropped={s['dropped']} endpoints={s['endpoints']} fully_read={s['endpoints_fully_read']}")
        for ep, d in sorted(ledger["per_endpoint"].items(), key=lambda kv: -kv[1]["unread"]):
            if d["unread"]:
                print(f"  {d['unread']:3d} unread  {ep}")
        return 0
    if args.check:
        current = LEDGER.read_text(encoding="utf-8") if LEDGER.exists() else ""
        if current != text:
            print("docs/parity/datapoints.json is stale — run: python scripts/datapoint_ledger.py", file=sys.stderr)
            return 1
        print("datapoints.json is current")
        return 0
    LEDGER.write_text(text, encoding="utf-8")
    s = ledger["summary"]
    print(f"wrote {LEDGER} — read={s['read']} unread={s['unread']} dropped={s['dropped']} endpoints={s['endpoints']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
