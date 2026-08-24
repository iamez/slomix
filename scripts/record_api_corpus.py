#!/usr/bin/env python3
"""Record a corpus of live GET responses from the dev backend.

The "highest-leverage accelerator" of the new-site build (docs/design/06 §4):
one artifact, three uses — (1) ground truth for response_model shapes,
(2) MSW mocks so page tests need no database, (3) golden data for the parity
harness (docs/design/09 §H4: every path the new tree calls must exist in the
corpus, i.e. was really executed once and its shape is known).

Reads the committed OpenAPI snapshot (docs/api/openapi.json) for the path
list, mints the owner's session cookie the same way
scripts/audit_website_browser.mjs does, substitutes reference IDs, and saves
JSON bodies. Output defaults to tests/fixtures/api/recorded/ (gitignored);
phase tests copy the fixtures they rely on next to themselves and commit
those copies.

Usage: python scripts/record_api_corpus.py [--base http://127.0.0.1:8000]
           [--out tests/fixtures/api/recorded] [--only /api/proximity]
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = REPO_ROOT / "docs" / "api" / "openapi.json"

# Reference IDs known-good on the dev database (docs/design/14): session 150
# (2026-08-20), round 11277 (supply R1, same round as the spiderweb data
# contract), an 8-char GUID from that session. Override via CLI when the dev
# database moves on.
DEFAULT_SUBS: dict[str, str] = {
    "gaming_session_id": "150",
    "session_id": "150",
    "round_id": "11277",
    "match_id": "11321",
    "guid": "1C747DF1",
    "player_guid": "1C747DF1",
    "player_name": "SuperBoyy",
    "session_date": "2026-08-20",
    "date": "2026-08-20",
    "map_name": "supply",
    "season_id": "2026-Q3",
    "channel": "etl",
}

# Query battery applied when a bare call answers 422 — the storytelling
# family takes gaming_session_id XOR session_date (client.ts:124's rule,
# confirmed live), the combat-position family requires map_name.
RETRY_QUERY = {"gaming_session_id": "150", "map_name": "supply", "limit": "5"}


def mint_owner_cookie() -> str:
    """Same technique as scripts/audit_website_browser.mjs:116 — the server
    verifies with the real itsdangerous, so we sign with it too."""
    sys.path.insert(0, str(REPO_ROOT))
    import itsdangerous  # noqa: PLC0415
    from dotenv import dotenv_values  # noqa: PLC0415

    env = dotenv_values(REPO_ROOT / "website" / ".env")
    secret = env.get("SESSION_SECRET") or os.getenv("SESSION_SECRET")
    if not secret:
        raise SystemExit("SESSION_SECRET not found in website/.env")
    payload = base64.b64encode(
        json.dumps({"user": {"id": "231165917604741121", "username": "corpus-recorder"}}).encode()
    )
    return itsdangerous.TimestampSigner(str(secret)).sign(payload).decode()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow redirects: /auth/login 302s to discord.com, and following
    it would ship the minted owner session cookie to a third party (Codex P1
    on #802). A 3xx is recorded as the endpoint's answer, not chased."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def http_get(base: str, url: str, cookie: str, timeout: int = 60):
    req = urllib.request.Request(  # noqa: S310 — base is a caller-supplied http(s) dev URL
        base + url,
        headers={"Cookie": f"session={cookie}", "Accept": "application/json"},
    )
    started = time.time()
    try:
        with _OPENER.open(req, timeout=timeout) as res:  # noqa: S310
            return res.status, res.read(), time.time() - started
    except urllib.error.HTTPError as err:
        body = err.read()
        location = err.headers.get("Location") if err.headers else None
        if location and not body:
            body = f"redirect (not followed) -> {location}".encode()
        return err.code, body, time.time() - started
    except Exception as err:  # noqa: BLE001
        return -1, str(err).encode(), time.time() - started


def fill_path(path: str, subs: dict[str, str]) -> str | None:
    url = path
    for match in re.finditer(r"\{([^}]+)\}", path):
        value = subs.get(match.group(1))
        if value is None:
            return None
        url = url.replace(f"{{{match.group(1)}}}", urllib.parse.quote(value, safe=""))
    return url


def slug_for(path: str) -> str:
    """Bijective enough for the spec: '/' becomes '__', '-' survives — a plain
    non-alnum squash collided /api/live-status with /api/live/status and both
    weapons spellings, silently overwriting fixtures (Codex P2 on #802)."""
    cleaned = path.strip("/").replace("{", "").replace("}", "")
    return re.sub(r"[^A-Za-z0-9_.-]", "_", cleaned.replace("/", "__"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--out", default="tests/fixtures/api/recorded")
    parser.add_argument("--only", default="", help="record only paths with this prefix")
    args = parser.parse_args()

    spec = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    out_dir = (REPO_ROOT / args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    cookie = mint_owner_cookie()

    index: list[dict] = []
    skipped: list[str] = []
    for path, ops in sorted(spec["paths"].items()):
        op = ops.get("get")
        if not op or (args.only and not path.startswith(args.only)):
            continue
        url = fill_path(path, DEFAULT_SUBS)
        if url is None:
            skipped.append(path)
            continue
        # required query defaults straight from the spec
        query = {
            p["name"]: DEFAULT_SUBS.get(p["name"], p.get("schema", {}).get("default", 1))
            for p in op.get("parameters", [])
            if p.get("in") == "query" and p.get("required")
        }
        full = url + (("?" + urllib.parse.urlencode(query)) if query else "")
        status, body, elapsed = http_get(args.base, full, cookie)
        if status in (400, 422):
            retry = url + "?" + urllib.parse.urlencode({**RETRY_QUERY, **query})
            r_status, r_body, r_elapsed = http_get(args.base, retry, cookie)
            if r_status == 200:
                status, body, elapsed, full = r_status, r_body, r_elapsed, retry
        record: dict = {
            "path": path,
            "url": full,
            "status": status,
            "ms": round(elapsed * 1000),
            "bytes": len(body),
        }
        if status == 200 and body[:1] in (b"{", b"["):
            fixture = slug_for(path) + ".json"
            (out_dir / fixture).write_bytes(body)
            record["file"] = fixture
        else:
            record["body_head"] = body[:200].decode("utf-8", "replace")
        index.append(record)
        print(f"{status:4} {record['ms']:6}ms {len(body):9}B {full}")

    (out_dir / "_index.json").write_text(
        json.dumps(
            {"recorded": time.strftime("%Y-%m-%d %H:%M"), "base": args.base,
             "subs": DEFAULT_SUBS, "skipped_no_param": skipped, "results": index},
            indent=1,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    ok = sum(1 for r in index if r["status"] == 200)
    print(f"\nDONE: {len(index)} GET, {ok}x200, {len(skipped)} skipped -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
