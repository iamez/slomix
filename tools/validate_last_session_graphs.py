import asyncio
import os
import io
import traceback
from datetime import datetime

# Make repo root imports work
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord
from bot.ultimate_bot import UltimateETLegacyBot, ETLegacyCommands

OUT_DIR = os.path.join(os.path.dirname(__file__), "tmp")
os.makedirs(OUT_DIR, exist_ok=True)

class DummyMessage:
    def __init__(self):
        self.mentions = []

class DummyCtx:
    def __init__(self):
        self.sent = []
        self.message = DummyMessage()

    async def send(self, *args, **kwargs):
        # Capture text/embed/file(s)
        try:
            if 'file' in kwargs and kwargs['file'] is not None:
                f = kwargs['file']
                if isinstance(f, discord.File):
                    data = f.fp.read() if hasattr(f.fp, 'read') else None
                    filename = getattr(f, 'filename', f"file-{len(self.sent)}")
                    path = os.path.join(OUT_DIR, filename)
                    if data:
                        with open(path, 'wb') as fh:
                            fh.write(data)
                    else:
                        # try to seek/rewind
                        try:
                            f.fp.seek(0)
                            with open(path, 'wb') as fh:
                                fh.write(f.fp.read())
                        except Exception:
                            with open(path, 'wb') as fh:
                                fh.write(b'')
                    print(f"Saved file: {path}")
                    self.sent.append(('file', path))
                    return
            if 'files' in kwargs and kwargs['files']:
                files = kwargs['files']
                for idx, f in enumerate(files):
                    if isinstance(f, discord.File):
                        data = f.fp.read() if hasattr(f.fp, 'read') else None
                        filename = getattr(f, 'filename', f"file-{len(self.sent)}_{idx}")
                        path = os.path.join(OUT_DIR, filename)
                        if data:
                            with open(path, 'wb') as fh:
                                fh.write(data)
                        else:
                            try:
                                f.fp.seek(0)
                                with open(path, 'wb') as fh:
                                    fh.write(f.fp.read())
                            except Exception:
                                with open(path, 'wb') as fh:
                                    fh.write(b'')
                        print(f"Saved file: {path}")
                        self.sent.append(('file', path))
                return
            if 'embed' in kwargs and kwargs['embed'] is not None:
                emb = kwargs['embed']
                title = getattr(emb, 'title', None)
                print(f"Sent embed: {title}")
                self.sent.append(('embed', title))
                return
            # Fallback: print args
            if args:
                for a in args:
                    print(f"send arg: {a}")
                self.sent.append(('text', str(args)))
            elif kwargs.get('content'):
                print(f"send content: {kwargs.get('content')}")
                self.sent.append(('text', kwargs.get('content')))
            else:
                print(f"send called with kwargs: {kwargs}")
                self.sent.append(('other', str(kwargs)))
        except Exception as e:
            print("Error in DummyCtx.send:", e)
            traceback.print_exc()

async def run_test():
    try:
        bot = UltimateETLegacyBot()
        print(f"Using DB: {bot.db_path}")
        cog = ETLegacyCommands(bot)
        ctx = DummyCtx()

        # Call last_session with graphs subcommand
        print("Invoking last_session graphs...")
        # discord.py wraps commands as Command objects; call the underlying callback
        # passing the cog instance as the first arg (self)
        cmd = getattr(cog, 'last_session')
        # If it's a Command, use its callback attr; otherwise call directly
        if hasattr(cmd, 'callback'):
            await cmd.callback(cog, ctx, "graphs")
        else:
            await cmd(cog, ctx, "graphs")

        # Summary
        print("--- SUMMARY ---")
        print(f"Total send calls: {len(ctx.sent)}")
        counts = {}
        for kind, val in ctx.sent:
            counts[kind] = counts.get(kind, 0) + 1
        print(f"By kind: {counts}")
        for i, (kind, val) in enumerate(ctx.sent, 1):
            print(f"{i}. {kind}: {val}")

    except Exception as e:
        print("TEST ERROR:")
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(run_test())
