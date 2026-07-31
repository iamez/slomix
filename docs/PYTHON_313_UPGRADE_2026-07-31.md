# Python 3.13 upgrade on the dev box — what was actually done (2026-07-31)

**Status: EXECUTED.** This document replaces the M3 and M4 preparation notes (PRs #584
and #583), which planned an upgrade to **3.11** that never happened — neither of those
files ever reached `main`. The upgrade that ran on 2026-07-31 targeted **3.13.14**, and
it surfaced two failure modes that neither plan anticipated. This is the record of what
happened, not a proposal.

Why 3.13 and not the planned 3.11: on this box `apt-cache policy python3.11` offered only
`3.11.0~rc1-1~22.04` — a release candidate. The deadsnakes PPA carries a stable
`python3.13` (3.13.14), and production already runs **3.13.5**, so 3.13 both avoids
shipping an RC and *narrows* the dev↔prod gap instead of creating a third version.

`website/backend/map_geometry/pk3_index.py` was not modified — its `from enum import
StrEnum` (line 10) is the reason this mattered, not a thing to change.

---

## Result

| | before (3.10.12) | after (3.13.14) |
|---|---|---|
| `venv/bin/python -m pytest tests/` | `Interrupted: 2 errors during collection` | **3971 passed, 64 skipped, 0 failed** (47 s) |
| `tests/unit/test_pk3_geometry_index.py` + `tests/integration/test_map_geometry_real_assets.py` | 2 errors | 11 passed, 4 skipped |
| dev vs prod | 3.10.12 vs 3.13.5 | 3.13.14 vs 3.13.5 |
| `pyproject.toml` `requires-python = ">=3.11,<3.14"` | dev violated it | satisfied |

**No repository file needed to change for the upgrade itself** — 3.13 is inside the
existing `requires-python`. `pyproject.toml`'s `requires-python`, ruff `target-version`
and mypy `python_version` stay pinned at the *lower* edge of the supported window, which
is correct.

Interpreter installed side-by-side as `/usr/bin/python3.13` (deadsnakes PPA);
`/usr/bin/python3` is still 3.10, so the OS and unrelated tooling did not move.

---

## Trap 1 — renaming a venv breaks console scripts

Venvs were built alongside the live ones as `venv313` / `website/venv313`, validated,
then swapped in by rename. The bot came up; **the web service went into a `203/EXEC`
restart loop**:

```
etlegacy-web.service: Failed to execute .../website/venv/bin/uvicorn: No such file or directory
etlegacy-web.service: Main process exited, code=exited, status=203/EXEC
etlegacy-web.service: Scheduled restart job, restart counter is at 5.
```

`uvicorn` was present. Its **shebang was not**: venv console scripts bake an absolute
interpreter path at build time, so after `mv venv313 venv` every one of them pointed at
a directory that no longer existed.

```
#!/home/samba/share/slomix_discord/website/venv313/bin/python3.13   <- stale
```

Why the bot survived and the web did not, straight from the unit files:

```
etlegacy-bot: ExecStart=.../venv/bin/python3 bot/ultimate_bot.py        <- symlink, path-independent
etlegacy-web: ExecStart=.../website/venv/bin/uvicorn backend.main:app   <- console script, baked path
```

Affected: 33 scripts in `venv/bin`, 23 in `website/venv/bin`. Fixed by rewriting the
shebangs; `pyvenv.cfg` needed nothing functional (`home`/`executable` already point at
`/usr/bin`; `venv313` appears there only in the informational `command =` line).

**Rules this establishes:**
- If a venv is built under one name and renamed into place, rewrite the shebangs
  **before** starting anything: `sed -i 's#/<buildname>/#/<finalname>/#g' <venv>/bin/*`
  (text files only).
- Better, because it is immune to the whole class: point units at
  `venv/bin/python -m uvicorn …` rather than at the `uvicorn` console script.
- Build the venv at its final path when you can. The side-by-side build is still worth
  it — it is what let the old venvs keep serving traffic throughout validation — but the
  rename is not free.

---

## Trap 2 — `website/requirements.txt` does not describe the web service

The freshly built web venv could not import the app:

```
website/backend/main.py -> bot/services/__init__.py:48 -> import discord
ModuleNotFoundError: No module named 'discord'
```

`website/requirements.txt` says it is *"synced with root requirements.txt"* and that
*"prod runs the web service from venv-web built off THIS file"*. **Both claims are
false.** It is missing 34 packages the service actually needs, among them `discord.py`,
`trueskill`, `matplotlib`, `Pillow`, `paramiko`, `scp`, `aiofiles`, `aiosqlite`,
`watchdog`, `numpy`, `cryptography`, `bcrypt`, `pynacl`. The old `website/venv` worked
because it was effectively `requirements.txt ∪ website/requirements.txt`.

Verified against the canonical VM rather than assumed (this is the measurement Codex
asked for on #583):

```
$ ssh slomix-vm '/opt/slomix/venv-web/bin/pip show discord.py; /opt/slomix/venv-web/bin/python --version'
Name: discord.py
Version: 2.6.4
Python 3.13.5
# 71 packages installed
```

So **production's `venv-web` was not built from that manifest either.**

**Latent risk, not a live outage:** `deploy_release.sh` and `deploy_clean.sh` never
*create* venvs — they only `pip install -r` into existing ones — so nothing rebuilds
`venv-web` from the incomplete manifest today. The day something does, the web service
dies on import. Resolved on dev by installing `-r requirements.txt` on top of
`-r website/requirements.txt`. **Fixing the manifest itself is deliberately not part of
this change** — it alters what production installs and deserves its own PR.

---

## Two more things the dry run got wrong

- **`pip install --dry-run --python-version 3.13` evaluates environment markers against
  the *running* interpreter, not the target.** It therefore never showed `audioop-lts`
  (which discord.py declares as `audioop-lts; python_version >= "3.13"` and which is
  mandatory on 3.13, since `audioop` left the stdlib and `import discord` pulls
  `player.py`). Same artifact for `backports-asyncio-runner`. The real install pulled
  `audioop_lts-0.2.2-cp313` correctly. **Treat marker-gated dependencies as verifiable
  only after the build, or against a real target interpreter.**
- **`trueskill==0.4.5` publishes no wheel.** It is pure Python and builds from sdist
  without a compiler, but it means the install must **not** use `--only-binary=:all:` —
  which is exactly what makes `--only-binary` safe for *dry runs* and wrong for the
  real thing.

---

## Answers to the review findings on the superseded plans

The three findings Codex raised against the M3 plan were all correct, and two of them
are no longer hypothetical:

**"Wait for services to become healthy before declaring success."** Confirmed the hard
way. The units are `Type=simple` with `Restart=always`, so `systemctl start` returns
while the process is still starting. Immediately after the swap, `systemctl is-active`
reported `active` / `activating` — and the web service was already in a crash loop. A
status check taken at `start` time proves nothing. **What actually caught it:** reading
`journalctl -u etlegacy-web`, then `curl` against `/health` and `/api/status`, then
`scripts/verify_post_deploy.sh`. Post-swap verification must exercise the service, not
ask systemd how it feels.

**"Gate service startup on successful rollback"** and **"abort rollback when entering
the repository root fails."** Both are the same defect: a pasted block whose later,
destructive steps run even though an earlier step failed. Every command in the executed
sequence was `&&`-chained end to end, so `systemctl start` could not run on a
half-swapped tree:

```bash
cd /home/samba/share/slomix_discord \
  && sudo systemctl stop etlegacy-bot etlegacy-web \
  && mv venv venv-3.10.bak && mv venv313 venv \
  && mv website/venv website/venv-3.10.bak && mv website/venv313 website/venv \
  && sudo systemctl start etlegacy-bot etlegacy-web
```

The `cd` being first and chained is what makes the relative `mv`s safe. **Rule: any
runbook block containing a destructive step is `&&`-chained from its first `cd`, or it
uses absolute paths throughout.** A block that "stops partway and leaves the service
down deliberately" is the correct behaviour — but only if it genuinely stops.

---

## Rollback

The 3.10 venvs are retained as `venv-3.10.bak` and `website/venv-3.10.bak` (648 MB;
578 GB free on `/home/samba/share`). Rollback is a rename plus a restart, in one chain:

```bash
cd /home/samba/share/slomix_discord \
  && sudo systemctl stop etlegacy-bot etlegacy-web \
  && rm -rf venv website/venv \
  && mv venv-3.10.bak venv && mv website/venv-3.10.bak website/venv \
  && sudo systemctl start etlegacy-bot etlegacy-web
```

Note that `systemctl restart etlegacy-bot` / `etlegacy-web` are available **without a
password** via `/etc/sudoers.d/samba-slomix`; `stop`/`start` are not. `sudo -n -l <cmd>`
checks authorization without executing, and the NOPASSWD match is exact — extra flags
make it miss.

---

## Unpinned transitives now sit above production

These were never pinned, so they float by design; dev being ahead means an
incompatibility shows up locally before it reaches prod.

| package | prod | dev now |
|---|---|---|
| cryptography | 46.0.5 | 49.0.0 |
| aiohttp | 3.13.3 | 3.14.3 |
| numpy | 2.4.2 | 2.5.1 |
| pydantic | 2.12.5 | 2.13.4 |
| httptools | 0.7.1 | 0.8.0 |
| watchfiles | 1.1.1 | 1.2.0 |
| uvloop, audioop-lts | 0.22.1, 0.2.2 | identical |

If exact parity is ever wanted, `--constraint` from prod's `pip freeze` is the lever.

---

## Still open (each its own change, not this one)

- `website/requirements.txt` — 34 missing packages; the file's own comments are wrong.
- `install.sh:518` — checks `>= 3.10` while the manifest requires `>=3.11`, and only
  `print_warning`s, so a too-old interpreter passes and fails later at `StrEnum`.
- `website/start_website.sh:55` — stale "Please install Python 3.8+".
- `pytest.ini:37` — `minversion = 3.11` commented as "Minimum Python version";
  `minversion` is pytest's version, not Python's.
- CI pins `python-version: "3.11"` in four places (`tests.yml:69,171`, `codeql.yml:40`,
  `repo-hygiene.yml:16`). A 3.11 + 3.13 matrix would cover both edges of
  `requires-python`; two earlier audits proposed the same.
- `slomix_vm_setup.sh:611` installs a bare unversioned `python3`, so prod's interpreter
  is whatever the distribution ships. Since the deploy scripts do not recreate venvs, a
  future `apt upgrade` on the VM could silently invalidate `venv-bot`/`venv-web`.
