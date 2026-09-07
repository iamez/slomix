#!/usr/bin/env python3
"""Create (or reuse) the Discord webhook the watchdog alerts through, and
write its URL into a .env file as WATCHDOG_WEBHOOK_URL.

The bot token and the admin channel come from the .env given (root .env by
default — never website/.env). The webhook is looked up by name first so
re-running is idempotent; only its id is ever printed. If the bot lacks
MANAGE_WEBHOOKS in that channel, the manual recipe from
docs/LUA_WEBHOOK_SETUP.md is printed instead and nothing is written.

Usage: scripts/mint_watchdog_webhook.py [--env PATH] [--channel ID] [--name NAME] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WEBHOOK_NAME = "slomix watchdog"
KEY = "WATCHDOG_WEBHOOK_URL"


def read_env(path: Path) -> dict[str, str]:
    from dotenv import dotenv_values
    return {k: v for k, v in (dotenv_values(path) or {}).items() if v is not None}


def write_key(path: Path, key: str, value: str) -> str:
    """Append or replace `key=value` as a bare line (systemd EnvironmentFile
    does not strip trailing comments), atomically, keeping mode, with a
    dated backup next to the file."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    out, done = [], False
    for line in lines:
        if line.startswith(key + "="):
            out.append(f"{key}={value}")
            done = True
        else:
            out.append(line)
    if not done:
        if out and out[-1].strip():
            out.append("")
        out.append(f"# watchdog alerts (scripts/mint_watchdog_webhook.py, {dt.date.today().isoformat()})")
        out.append(f"{key}={value}")
    backup = path.with_name(path.name + ".bak-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(path, backup)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
    shutil.copymode(path, tmp)
    os.replace(tmp, path)
    return "replaced" if done else "appended"


async def mint(token: str, channel_id: int, name: str, dry_run: bool) -> tuple[str | None, str]:
    import discord

    intents = discord.Intents.none()
    client = discord.Client(intents=intents)
    result: dict[str, str | None] = {"url": None, "note": ""}

    @client.event
    async def on_ready():
        try:
            channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                result["note"] = f"channel {channel_id} is not a text channel this bot can see"
                return
            hooks = await channel.webhooks()
            mine = [h for h in hooks if h.name == name and h.token]
            if mine:
                hook = mine[0]
                result["note"] = f"reused webhook id={hook.id} in #{channel.name}"
            elif dry_run:
                result["note"] = f"dry-run: would create '{name}' in #{channel.name} (bot has MANAGE_WEBHOOKS: {channel.permissions_for(channel.guild.me).manage_webhooks})"
                return
            else:
                hook = await channel.create_webhook(name=name, reason="slomix watchdog alerts")
                result["note"] = f"created webhook id={hook.id} in #{channel.name}"
            result["url"] = hook.url
        except discord.Forbidden:
            result["note"] = (
                "FORBIDDEN: the bot lacks Manage Webhooks in that channel. Manual route: "
                "channel settings → Integrations → Webhooks → New Webhook → copy URL "
                "(docs/LUA_WEBHOOK_SETUP.md), then add WATCHDOG_WEBHOOK_URL=<url> to .env yourself."
            )
        except Exception as e:  # noqa: BLE001 - reported, then the client closes
            result["note"] = f"failed: {type(e).__name__}: {e}"
        finally:
            await client.close()

    await client.start(token)
    return result["url"], result["note"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--env", default=str(REPO / ".env"), help="the .env to read the token from and write the key into")
    ap.add_argument("--channel", type=int, default=None, help="channel id (default: first ADMIN_CHANNEL_ID)")
    ap.add_argument("--name", default=WEBHOOK_NAME)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    env_path = Path(args.env)
    cfg = read_env(env_path)
    token = cfg.get("DISCORD_BOT_TOKEN")
    if not token:
        print("no DISCORD_BOT_TOKEN in", env_path, file=sys.stderr)
        return 2
    channel = args.channel
    if channel is None:
        raw = (cfg.get("ADMIN_CHANNEL_ID") or "").split(",")
        ids = [int(x) for x in (s.strip() for s in raw) if x.isdigit() and int(x) > 0]
        if not ids:
            print("no ADMIN_CHANNEL_ID in", env_path, file=sys.stderr)
            return 2
        channel = ids[-1]  # the last entry is the dev guild's channel on this box
    url, note = asyncio.run(mint(token, channel, args.name, args.dry_run))
    print(note)
    if url is None:
        return 1
    if args.dry_run:
        return 0
    how = write_key(env_path, KEY, url)
    print(f"{KEY} {how} in {env_path} (value not shown)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
