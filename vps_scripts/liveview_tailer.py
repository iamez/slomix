#!/usr/bin/env python3
"""liveview_tailer — S2 of the Live-view plan: tail the game server's log(s)
and POST parsed events to the website's live ingest endpoint.

Stdlib-only (the game box has no virtualenv) and deliberately boring:
tail -F semantics (survives rotation/truncation), small batches, a bounded
in-memory delivery queue with exponential backoff. 2026-08-18 hardening —
the previous drop-after-one-retry design lost 44 batches to Cloudflare
403/530 windows in one evening, and every lost MAP/TEAM_CHANGE corrupted
the live state for a whole map.

ONE process now tails BOTH sources (design doc LIVE_EVENTS_LUA_DESIGN
option (b)): the raw engine log and live_events.lua's LIVEX log share
ordering, batching and backpressure, and every event carries its source.

Deployment (pattern proven by vektor's log_monitor.sh on the same box):
  - config via environment or /home/et/.liveview_tailer.env (KEY=VALUE)
  - LIVEVIEW_ENABLED=true|false   master flag (default FALSE — flag off)
  - LIVEVIEW_LOGS=path[=source],path[=source]
      default: legacy3.log=legacy3,slomix-live.log=livex (both under
      /home/et/.etlegacy/legacy). LIVEVIEW_LOG (single path) is still
      honoured for backward compatibility.
  - LIVEVIEW_URL=https://www.slomix.fyi/api/live/events
      ⚠️ must be the www host and IPv4 — the apex A record and the box's
      IPv6 route are both dead from here (research: transportna past)
  - INTERNAL_API_SECRET=...       same secret the website checks
  - start via ~/start.sh + ONE @reboot cron with a pgrep guard, NOT systemd
Run `python3 liveview_tailer.py --check` to validate config and exit.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import urllib.request
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from liveview_parser import parse_line  # noqa: E402

_DEFAULT_LOGS = (
    "/home/et/.etlegacy/legacy/legacy3.log=legacy3,"
    "/home/et/.etlegacy/legacy/slomix-live.log=livex"
)
ENV_FILE = Path(os.environ.get(
    "LIVEVIEW_ENV", "/home/et/.liveview_tailer.env"))
BATCH_MAX = 100          # events per POST (server caps at 200)
FLUSH_SECONDS = 2.0
POST_TIMEOUT = 4.0

# Delivery queue: batches waiting to be sent. Bounded so a long outage can't
# grow without limit; when over budget, TELEMETRY-only batches are evicted
# first — control events (map, roster, round bounds) are once-per-map facts
# whose loss corrupts live state for minutes, so they are never the first out.
QUEUE_MAX_BATCHES = 40
BACKOFF_START = 1.0
BACKOFF_MAX = 30.0

_CONTROL_TYPES = frozenset({
    "MAP", "LIVE_MAP", "GAMETYPE", "GAMETIME", "INIT_GAME",
    "ROUND_START", "ROUND_END", "STATS_SAVED", "EXIT",
    "TEAM_CHANGE", "CONNECT", "DISCONNECT", "BEGIN",
})

# The engine buffers nothing (g_logSync 1); we still coalesce for ~2 s so a
# kill burst becomes one POST instead of five.

# Force IPv4: the box resolves AAAA records for the website but has no
# working v6 route, so every connection would hang for the timeout first.
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(*args, **kwargs):
    return [ai for ai in _orig_getaddrinfo(*args, **kwargs)
            if ai[0] == socket.AF_INET]


socket.getaddrinfo = _ipv4_getaddrinfo


def _load_env_file() -> None:
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _log_specs() -> list[tuple[Path, str]]:
    """[(path, source), ...] from LIVEVIEW_LOGS, or the legacy single-file
    LIVEVIEW_LOG, or the two-source default."""
    single = os.environ.get("LIVEVIEW_LOG")
    if single:
        return [(Path(single), "tailer")]
    specs = []
    for item in os.environ.get("LIVEVIEW_LOGS", _DEFAULT_LOGS).split(","):
        item = item.strip()
        if not item:
            continue
        path, _, source = item.partition("=")
        specs.append((Path(path), source or "tailer"))
    return specs


def _config() -> tuple[bool, str, str]:
    _load_env_file()
    enabled = os.environ.get("LIVEVIEW_ENABLED", "false").lower() == "true"
    url = os.environ.get("LIVEVIEW_URL", "")
    secret = os.environ.get("INTERNAL_API_SECRET", "")
    return enabled, url, secret


def _url_allowed(url: str) -> bool:
    """https only — the internal secret rides in a header. Plain http is
    allowed solely toward loopback (local testing), never over the wire
    (coderabbit, PR #773)."""
    if url.startswith("https://"):
        return True
    return url.startswith(("http://127.0.0.1", "http://localhost"))


def _post_once(url: str, secret: str, batch: list[dict], source: str) -> bool:
    """One delivery attempt; retries are the queue's job, not this function's."""
    if not _url_allowed(url):
        return False
    req = urllib.request.Request(  # noqa: S310 # nosec B310 — https-only, scheme checked above
        url,
        data=json.dumps({"events": batch, "source": source}).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Internal-Token": secret,
            # Cloudflare's Browser Integrity Check 403s the default
            # Python-urllib UA at the edge (measured 2026-08-11); any
            # honest custom UA passes.
            "User-Agent": "slomix-liveview-tailer/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=POST_TIMEOUT) as resp:  # noqa: S310 # nosec B310 — operator config URL, scheme checked
            resp.read()
        return True
    except Exception as exc:  # noqa: BLE001 — the queue handles the failure
        print(f"[liveview_tailer] post failed ({len(batch)} events): {exc}",
              flush=True)
        return False


class _Delivery:
    """Bounded batch queue with exponential backoff.

    A failed POST leaves the batch at the head and pushes the next attempt
    ``backoff`` seconds out; success resets the backoff. Over budget, the
    newest TELEMETRY-only batch is evicted first (loudly); a batch carrying
    control events is only dropped when every batch in the queue is control
    — which would take a multi-hour outage.
    """

    def __init__(self, url: str, secret: str, source: str) -> None:
        self._url = url
        self._secret = secret
        self._source = source
        self._queue: deque[list[dict]] = deque()
        self._backoff = BACKOFF_START
        self._next_try = 0.0

    def push(self, batch: list[dict]) -> None:
        self._queue.append(batch)
        while len(self._queue) > QUEUE_MAX_BATCHES:
            victim = None
            for i in range(len(self._queue) - 1, -1, -1):
                if not any(e.get("type") in _CONTROL_TYPES for e in self._queue[i]):
                    victim = i
                    break
            if victim is None:
                victim = len(self._queue) - 1  # all control — drop newest
            dropped = self._queue[victim]
            del self._queue[victim]
            print(f"[liveview_tailer] queue full — evicted {len(dropped)} "
                  f"events (control={any(e.get('type') in _CONTROL_TYPES for e in dropped)})",
                  flush=True)

    def pump(self) -> None:
        now = time.monotonic()
        if not self._queue or now < self._next_try:
            return
        if _post_once(self._url, self._secret, self._queue[0], self._source):
            self._queue.popleft()
            self._backoff = BACKOFF_START
            self._next_try = 0.0
        else:
            self._next_try = now + self._backoff
            self._backoff = min(self._backoff * 2, BACKOFF_MAX)

    @property
    def depth(self) -> int:
        return len(self._queue)


class _Tail:
    """tail -F one file: start at EOF, survive rotation; on in-place
    truncation read from offset 0 — the file was just cut, its content is
    tiny and brand new. (The old seek-to-EOF raced live_events.lua's
    truncate-on-init and skipped the single `I ... map ...` marker.)"""

    def __init__(self, path: Path, source: str) -> None:
        self.path = path
        self.source = source
        self._fh = None
        self._inode = None

    def read_lines(self, max_lines: int = 200) -> list[str]:
        try:
            st = self.path.stat()
        except FileNotFoundError:
            return []
        if self._fh is None or st.st_ino != self._inode:
            if self._fh:
                self._fh.close()
            self._fh = self.path.open("r", encoding="utf-8", errors="ignore")
            self._inode = st.st_ino
            self._fh.seek(0, os.SEEK_END)  # never replay history into the feed
        if st.st_size < self._fh.tell():  # truncated in place
            self._fh.seek(0)
        lines: list[str] = []
        while len(lines) < max_lines:
            line = self._fh.readline()
            if not line:
                break
            lines.append(line)
        return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="validate config, exit")
    args = ap.parse_args()

    enabled, url, secret = _config()
    specs = _log_specs()
    if args.check:
        logs = ", ".join(f"{p} ({s}, exists={p.exists()})" for p, s in specs)
        print(f"enabled={enabled} url={url or '(unset)'} "
              f"secret={'set' if secret else 'MISSING'} logs=[{logs}]")
        return 0
    if not enabled:
        print("[liveview_tailer] LIVEVIEW_ENABLED != true — exiting (flag off)")
        return 0
    if not url or not secret:
        print("[liveview_tailer] missing LIVEVIEW_URL or INTERNAL_API_SECRET")
        return 1

    tails = [_Tail(p, s) for p, s in specs]
    delivery = _Delivery(url, secret, "tailer")
    print(f"[liveview_tailer] following {[str(t.path) for t in tails]} -> {url}",
          flush=True)

    batch: list[dict] = []
    last_flush = time.monotonic()
    last_depth_report = 0.0
    while True:
        got_line = False
        for tail in tails:
            for line in tail.read_lines():
                got_line = True
                ev = parse_line(line)
                # TEAM_CHAT_REDACTED never leaves the box, not even as a type.
                if ev is not None and ev.type != "TEAM_CHAT_REDACTED":
                    batch.append({
                        "type": ev.type,
                        "level_ms": ev.level_ms,
                        "fields": {**ev.fields, "src": tail.source},
                    })
        now = time.monotonic()
        if batch and (len(batch) >= BATCH_MAX or now - last_flush >= FLUSH_SECONDS):
            # Whole batch enters the queue in BATCH_MAX slices — nothing is
            # silently discarded (the old code posted batch[:50] and zeroed
            # the rest).
            for i in range(0, len(batch), BATCH_MAX):
                delivery.push(batch[i:i + BATCH_MAX])
            batch = []
            last_flush = now
        delivery.pump()
        if delivery.depth and now - last_depth_report > 30:
            print(f"[liveview_tailer] delivery queue depth={delivery.depth}",
                  flush=True)
            last_depth_report = now
        if not got_line:
            time.sleep(0.25)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
