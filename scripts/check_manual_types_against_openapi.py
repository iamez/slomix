#!/usr/bin/env python3
"""Compare the hand-written client types against the generated OpenAPI schema.

READ-ONLY. Prints a report and exits non-zero when they disagree.

⛔ TWO THINGS THIS SCRIPT CANNOT SEE, both of which look like agreement:

  1. A hand type written as `export type X = …` (an ALIAS, not an `interface`)
     is invisible to the parser. That used to print "types agree" after
     comparing nothing; it now prints NOT COMPARED and exits 2.
  2. It compares TOP-LEVEL fields only. It does not descend into an inline
     object literal, so `top_map: { name: string } | null` is checked for the
     nullability of `top_map` and never for the nullability of `name` —
     which is the one that is wrong there (the API sends `top_map.name = null`
     on a season with no rounds, and never sends a null `top_map`).

A clean result means the top-level fields of a matching interface agree. It
does not mean the file is right.

WHY THIS EXISTS. `website/frontend/src/app/lib/types.ts` holds ~75 interfaces
written by hand, and `src/api/generated/openapi.d.ts` holds the same shapes
generated from `docs/api/openapi.json`. Nothing compares them, so a field that
becomes nullable on the server stays non-null in the hand-written type and the
compiler never objects.

That is not hypothetical. On 2026-08-29 the two drifted on `/rounds/recent`:
the handler writes `str(row[2]) if row[2] else None`, the hand type said
`round_date: string`, and the consequences were both SILENT —

    round_number: null   passed a `!== 0` filter and stayed in the picker as a
                         round the page cannot draw
    round_date:   null   rendered as nothing: "supply R1 — (6 players)", with
                         a hole where the date belongs

⛔ TWO KINDS OF DISAGREEMENT, AND THEY NEED DIFFERENT FIXES:

    nullable   the key is always present, the value may be null
               → the client must check the VALUE
    optional   the key may be absent entirely
               → the client must check PRESENCE

Treating an optional field as nullable is what crashed `session-detail`:
`total_votes === 0` is false for `undefined`, so the drawing branch ran anyway.

Usage:
    venv/bin/python3 scripts/check_manual_types_against_openapi.py
    venv/bin/python3 scripts/check_manual_types_against_openapi.py --schema RoundViz
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "api" / "openapi.json"
TYPES = ROOT / "website" / "frontend" / "src" / "app" / "lib" / "types.ts"


#: OpenAPI primitive -> the TypeScript spellings that satisfy it. Deliberately
#: narrow: anything structural (objects, arrays of objects, unions of models)
#: is left to the generated file, which is authoritative. This catches the
#: cheap, silent mistakes — a number typed as a string reads fine and breaks
#: only at `.toFixed`.
_PRIMITIVES = {
    "integer": ("number",),
    "number": ("number",),
    "string": ("string",),
    "boolean": ("boolean",),
}


def _primitive(schema: dict) -> str | None:
    """The scalar type of a field, seeing through a nullable anyOf."""
    if isinstance(schema.get("type"), str) and schema["type"] in _PRIMITIVES:
        return schema["type"]
    branches = [b for b in schema.get("anyOf", []) if b.get("type") != "null"]
    if len(branches) == 1:
        return _primitive(branches[0])
    return None


def _unreadable_ts(ts_type: str) -> bool:
    """True for a TS construct this parser cannot resolve, so it must not
    judge it. `SystemStage['state']` is an INDEXED ACCESS: the answer lives in
    another interface, and reporting "API says string" against it is a finding
    about the parser, not about the file. (`SystemStage['state']` ends in
    `| string`, so it does satisfy `string` — the tool simply could not see
    that.)"""
    base = ts_type.replace("| null", "").replace("| undefined", "").strip()
    return "[" in base and "]" in base and "'" in base


def _ts_is_nullable(ts_type: str) -> bool:
    """Is the FIELD nullable — not "does the word null appear anywhere".

    ⛔ Substring matching got this wrong in the direction that costs most: it
    reported a correctly-typed field as a defect. `{ name: string | null;
    plays: number }` describes an object that is never null whose `name` may
    be, and reading `null` out of the middle of it produced the finding
    "TS nullable, API never is" against a file that had just been fixed.
    Only a `| null` OUTSIDE every brace makes the field itself nullable.
    """
    depth = 0
    top = []
    for ch in ts_type:
        if ch in "{([<":
            depth += 1
        elif ch in "})]>":
            depth -= 1
        elif depth == 0:
            top.append(ch)
    outer = "".join(top)
    return "null" in outer or "undefined" in outer


def _ts_matches(primitive: str, ts_type: str) -> bool:
    base = ts_type.replace("| null", "").replace("| undefined", "").strip()
    # a string-literal union ("ok" | "no_data") satisfies `string`
    if primitive == "string" and base.startswith(("'", '"')):
        return True
    return any(base == spelling or base.startswith(f"{spelling} ")
               for spelling in _PRIMITIVES[primitive])


def _interface_body(source: str, name: str) -> str | None:
    """The body of `export interface <name> { ... }`, brace-matched.

    Not a regex to the closing brace: nested object literals contain braces of
    their own, and a lazy match stops at the first one — which silently reads
    half an interface and reports the rest as missing.
    """
    start = source.find(f"export interface {name} {{")
    if start == -1:
        return None
    i = source.index("{", start)
    depth = 0
    for j in range(i, len(source)):
        if source[j] == "{":
            depth += 1
        elif source[j] == "}":
            depth -= 1
            if depth == 0:
                return source[i + 1:j]
    return None


def _fields(body: str) -> dict[str, tuple[str, bool]]:
    """field -> (declared type, is_optional). Top level only: a nested object's
    members are part of their parent's type string, not fields of their own."""
    out: dict[str, tuple[str, bool]] = {}
    depth = 0
    buf = ""
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped.startswith(("//", "*", "/*")):
            continue
        if depth == 0:
            match = re.match(r"(\w+)(\??):\s*(.+)", stripped)
            if match:
                name, opt, rest = match.groups()
                buf = rest
                depth += rest.count("{") - rest.count("}")
                if depth == 0:
                    out[name] = (buf.rstrip(";").strip(), opt == "?")
                continue
        else:
            buf += " " + stripped
            depth += stripped.count("{") - stripped.count("}")
            # ⛔ THIS WRITE WAS MISSING, AND THE BUG WAS NOT "A FIELD IS
            # SKIPPED" — IT WAS "A FIELD IS REPORTED AS ABSENT". A type
            # written as a MULTI-LINE inline object accumulated into `buf`
            # and then fell off the end of the loop, so the field looked
            # like it had never been declared. That produced confident,
            # wrong findings against a file that was correct:
            # `SystemOverview.linkage` and `SeasonSummary.totals` are both
            # present and both were reported "absent from types.ts".
            # A parser that cannot read a construct must not answer
            # questions about it.
            if depth == 0:
                out[name] = (buf.rstrip(";").strip(), opt == "?")
    return out


def _is_nullable(schema: dict) -> bool:
    """OpenAPI 3.1 expresses null as a member of anyOf or of `type`."""
    if schema.get("type") == "null":
        return True
    if "null" in (schema.get("type") or []):
        return True
    return any(_is_nullable(s) for s in schema.get("anyOf", []))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", help="check one schema instead of all")
    parser.add_argument(
        "--types", type=Path, default=TYPES,
        help="which types.ts to compare against. ⛔ THE DEFAULT IS THIS "
             "WORKTREE'S COPY, which is not necessarily the one the "
             "frontend author is editing — every finding below is about "
             "the file named in the header, and a stale file produces "
             "confident findings about problems that were already fixed.")
    args = parser.parse_args()

    if not SPEC.exists():
        print(f"missing {SPEC} — run scripts/dump_openapi.py first")
        return 2

    schemas = json.loads(SPEC.read_text())["components"]["schemas"]
    types_path = args.types
    source = types_path.read_text()

    compared = 0
    findings: list[tuple[str, str, str, str]] = []
    unreadable: list[tuple[str, str, str]] = []
    for name, schema in sorted(schemas.items()):
        if args.schema and name != args.schema:
            continue
        body = _interface_body(source, name)
        if body is None:
            continue
        compared += 1
        declared = _fields(body)
        required = set(schema.get("required", []))
        properties = schema.get("properties") or {}

        # ⛔ THE OTHER DIRECTION, WHICH THIS SCRIPT USED TO IGNORE ENTIRELY.
        # Iterating only the OpenAPI properties means a field declared SOLELY
        # in TypeScript is never examined, so a removed or renamed API field
        # can stay `required` on the client while this exits clean — the drift
        # that actually breaks a page, since the client reads a key the server
        # stopped sending (Codex on #830). A clean exit must cover both sets.
        findings.extend(
            (name, field, "declared in types.ts, absent from the API",
             declared[field][0])
            for field in sorted(set(declared) - set(properties)))

        for field, field_schema in properties.items():
            if field not in declared:
                findings.append((name, field, "absent from types.ts", ""))
                continue
            ts_type, ts_optional = declared[field]
            ts_nullable = _ts_is_nullable(ts_type)
            api_nullable = _is_nullable(field_schema)
            api_optional = field not in required

            # ⛔ BOTH DIRECTIONS. The first version of this script only looked
            # for TS being too strict, and a control mutation walked straight
            # past it: changing `gaming_session_id: number` to `string`, and
            # marking a required field optional, were both reported clean. A
            # checker that cannot fail proves nothing, so each rule below has a
            # counterpart.
            if api_nullable and not ts_nullable:
                findings.append((name, field, "API nullable, TS is not", ts_type))
            if ts_nullable and not (api_nullable or api_optional):
                findings.append((name, field, "TS nullable, API never is", ts_type))
            # ⛔ `ts_nullable` DOES NOT SATISFY `api_optional`. An optional API
            # field may be ABSENT, which arrives as `undefined`, and
            # `field: T | null` forbids undefined just as firmly as `field: T`
            # does. Accepting nullability here let the checker print agreement
            # for exactly the optional-versus-nullable drift its own docstring
            # claims to detect (Codex on #830). Optionality needs `?`.
            if api_optional and not ts_optional:
                findings.append((name, field, "API optional, TS is required", ts_type))
            if ts_optional and not api_optional:
                findings.append((name, field, "TS optional, API always sends it", ts_type))

            expected = _primitive(field_schema)
            if expected and _unreadable_ts(ts_type):
                unreadable.append((name, field, ts_type))
            elif expected and not _ts_matches(expected, ts_type):
                findings.append(
                    (name, field, f"API says {expected}", ts_type))

    stamp = datetime.fromtimestamp(types_path.stat().st_mtime, tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    print(f"types.ts: {types_path}  (last modified {stamp})")
    print(f"schemas compared: {compared}   disagreements: {len(findings)}")
    for name, field, ts_type in unreadable:
        print(f"  ~ {name}.{field}: NOT JUDGED — this parser cannot resolve "
              f"`{ts_type}`")
    for name, field, why, ts_type in findings:
        suffix = f"   (types.ts: {ts_type})" if ts_type else ""
        print(f"  {name}.{field}: {why}{suffix}")
    if compared == 0:
        # ⛔ NOT THE SAME AS AGREEMENT. An empty comparison and a clean
        # comparison have the same shape — zero disagreements — and printing
        # the reassuring line for both is how a tool tells you it checked
        # something it never looked at. Measured: `--schema StatsRecords`
        # reported "agree" while comparing nothing, because the hand-written
        # side is `export type StatsRecords = Record<string, RecordEntry[]>`
        # — a TYPE ALIAS. This parser reads `interface` declarations only, so
        # every alias is invisible to it and silently counts as fine.
        print("NOT COMPARED — no matching `interface` in types.ts.")
        print("  A `type X = ...` alias is invisible to this parser; absence of")
        print("  a finding here is absence of a check, not a clean result.")
        return 2
    if not findings:
        if unreadable:
            print(f"top-level fields agree, EXCEPT {len(unreadable)} this parser "
                  f"could not read — that is not agreement about them")
        else:
            print("hand-written types agree with the generated schema")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
