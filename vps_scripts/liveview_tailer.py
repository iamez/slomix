#!/usr/bin/env python3
"""liveview_tailer — S2 of the Live-view plan: tail ``legacy3.log`` on the
game server and POST parsed events to the website's live ingest endpoint.

Stdlib-only (the game box has no virtualenv) and deliberately boring:
tail -F semantics (survives rotation/truncation), small batches, spool-less
best-effort delivery — live events are worthless minutes later, so a failed
POST is dropped after one retry; legacy3.log remains the authority.

Deployment (pattern proven by vektor's log_monitor.sh on the same box):
  - config via environment or /home/et/.liveview_tailer.env (KEY=VALUE)
  - LIVEVIEW_ENABLED=true|false   master flag (default FALSE — flag off)
  - LIVEVIEW_URL=https://www.slomix.fyi/api/live/events
      ⚠️ must be the www host and IPv4 — the apex A record and the box's
      IPv6 route are both dead from here (research: transportna past)
  - INTERNAL_API_SECRET=...       same secret the website checks
  - start via ~/start.sh + @reboot cron with a pgrep guard, NOT systemd
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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from liveview_parser import parse_line  # noqa: E402

LOG_PATH = Path(os.environ.get(
    "LIVEVIEW_LOG", "/home/et/.etlegacy/legacy/legacy3.log"))
ENV_FILE = Path(os.environ.get(
    "LIVEVIEW_ENV", "/home/et/.liveview_tailer.env"))
BATCH_MAX = 25
FLUSH_SECONDS = 2.0

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


def _config() -> tuple[bool, str, str]:
    _load_env_file()
    enabled = os.environ.get("LIVEVIEW_ENABLED", "false").lower() == "true"
    url = os.environ.get("LIVEVIEW_URL", "")
    secret = os.environ.get("INTERNAL_API_SECRET", "")
    return enabled, url, secret


def _post(url: str, secret: str, batch: list[dict]) -> bool:
    if not url.startswith(("http://", "https://")):
        return False
    req = urllib.request.Request(  # noqa: S310 # nosec B310 — https-only, scheme checked above
        url,
        data=json.dumps({"events": batch, "source": "tailer"}).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Internal-Token": secret,
        },
    )
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310 # nosec B310 — operator config URL, scheme checked
                resp.read()
            return True
        except Exception as exc:  # noqa: BLE001 — best-effort by design
            if attempt == 2:
                print(f"[liveview_tailer] drop {len(batch)} events: {exc}",
                      flush=True)
    return False


def _follow(path: Path):
    """tail -F: start at EOF, survive truncation and rotation."""
    fh = None
    inode = None
    while True:
        try:
            st = path.stat()
        except FileNotFoundError:
            time.sleep(1.0)
            continue
        if fh is None or st.st_ino != inode:
            if fh:
                fh.close()
            fh = path.open("r", encoding="utf-8", errors="ignore")
            inode = st.st_ino
            fh.seek(0, os.SEEK_END)  # never replay history into the feed
        line = fh.readline()
        if line:
            yield line
        else:
            if st.st_size < fh.tell():  # truncated in place
                fh.seek(0, os.SEEK_END)
            time.sleep(0.25)
            yield None  # let the caller flush on quiet periods


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="validate config, exit")
    args = ap.parse_args()

    enabled, url, secret = _config()
    if args.check:
        print(f"enabled={enabled} url={url or '(unset)'} "
              f"secret={'set' if secret else 'MISSING'} log={LOG_PATH} "
              f"log_exists={LOG_PATH.exists()}")
        return 0
    if not enabled:
        print("[liveview_tailer] LIVEVIEW_ENABLED != true — exiting (flag off)")
        return 0
    if not url or not secret:
        print("[liveview_tailer] missing LIVEVIEW_URL or INTERNAL_API_SECRET")
        return 1

    print(f"[liveview_tailer] following {LOG_PATH} -> {url}", flush=True)
    batch: list[dict] = []
    last_flush = time.monotonic()
    for line in _follow(LOG_PATH):
        if line is not None:
            ev = parse_line(line)
            # TEAM_CHAT_REDACTED never leaves the box, not even as a type.
            if ev is not None and ev.type != "TEAM_CHAT_REDACTED":
                batch.append({
                    "type": ev.type,
                    "level_ms": ev.level_ms,
                    "fields": ev.fields,
                })
        now = time.monotonic()
        if batch and (len(batch) >= BATCH_MAX or now - last_flush >= FLUSH_SECONDS):
            _post(url, secret, batch[:BATCH_MAX * 2])
            batch = []
            last_flush = now
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
