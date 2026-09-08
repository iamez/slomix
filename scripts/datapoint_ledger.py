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
`{"endpoint", "key", "status": "read"|"unread"|"dropped", "reason"?}` plus a
summary. `--check` exits 1 when the committed file differs from a fresh
run (the test does the same in-process).

Usage:
  python scripts/datapoint_ledger.py            # rewrite docs/parity/datapoints.json
  python scripts/datapoint_ledger.py --check    # compare, exit 1 on drift
  python scripts/datapoint_ledger.py --summary  # counts per endpoint to stdout
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

_CALL_RES = [
    re.compile(r"\b(?:apiGet|apiPost|apiPatch|apiDelete|apiPut)(?:<[^>]{0,200}>)?\(\s*'([^']+)'"),
    re.compile(r"\bfetch\(\s*'(/api/[^'?]+)'"),
]
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
    paths: set[str] = set()
    for file, text in sources.items():
        if file.endswith("probes.ts"):
            continue
        for rx in _CALL_RES:
            for m in rx.finditer(text):
                paths.add(m.group(1))
    return paths


def fixture_name_for(api_path: str) -> str:
    return re.sub(r"[/-]", "_", re.sub(r"[{}]", "", api_path.lstrip("/"))) + ".json"


def _is_data_map(obj: dict[str, Any]) -> bool:
    """A dict whose keys are values (nicks, dates, guids) rather than field
    names: many keys, and most are not identifiers."""
    keys = list(obj.keys())
    if len(keys) < 4:
        return False
    non_ident = sum(1 for k in keys if not _IDENT.match(k))
    return non_ident >= len(keys) / 2


def leaf_keys(payload: Any) -> list[tuple[str, str]]:
    """(key, kind) pairs: top-level keys and one level below. kind is
    'field' or 'data-map'."""
    out: list[tuple[str, str]] = []

    def first_obj(v: Any) -> dict[str, Any] | None:
        if isinstance(v, dict):
            return v
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return v[0]
        return None

    root = first_obj(payload)
    if root is None:
        return out
    if _is_data_map(root):
        return [("<map>", "data-map")]
    for k, v in root.items():
        out.append((k, "field"))
        child = first_obj(v)
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
    seen_fixture: set[str] = set()
    for path in sorted(called_paths(sources)):
        fx = FIXTURES / fixture_name_for(path)
        if not fx.exists():
            continue  # fixturesCoverage.test.ts is the guard for that
        if fx.name in seen_fixture:
            continue
        seen_fixture.add(fx.name)
        try:
            payload = json.loads(fx.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for key, kind in leaf_keys(payload):
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
        "method": "keys of each called endpoint's recorded fixture (top level + one below) vs a name match over comment-stripped src/app source; a name match is an upper bound on rendering",
        "summary": {**counts, "endpoints": len(per_endpoint), "endpoints_fully_read": sum(1 for d in per_endpoint.values() if d["unread"] == 0)},
        "per_endpoint": per_endpoint,
        "rows": rows,
    }


def load_decisions() -> dict[str, str]:
    if not DECISIONS.exists():
        return {}
    data = json.loads(DECISIONS.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def render(ledger: dict[str, Any]) -> str:
    return json.dumps(ledger, indent=1, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--summary", action="store_true")
    args = ap.parse_args(argv)
    ledger = build(app_sources(), load_decisions())
    text = render(ledger)
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
