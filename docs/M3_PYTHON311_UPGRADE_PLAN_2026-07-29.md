# M3 — Python 3.11 upgrade: preparation, not execution (2026-07-29)

Task M3 from `docs/TASKS_FOR_SONNET_2026-07-29.md`. **Nothing in this
document is executed.** Adding a PPA and restarting services are owner-gated
system changes; per the task, the owner has already chosen the venv-upgrade
path — this documents how, so the actual work is a checklist, not a
research problem, when the owner is ready.

Do not touch `website/backend/map_geometry/pk3_index.py` (Codex's file) —
its `from enum import StrEnum` (line 10) is the reason this matters at all,
referenced below, not modified.

## Measured (2026-07-29)

```
venv/bin/python --version           -> Python 3.10.12
website/venv/bin/python --version   -> Python 3.10.12
pyproject.toml requires-python      -> >=3.11,<3.14
apt-cache policy python3.11         -> candidate 3.11.0~rc1-1~22.04 (a release
                                        candidate, not a stable release)
OS                                  -> Ubuntu 22.04.5 LTS (Jammy)
```

Both services run their venv's own interpreter directly:
```
/etc/systemd/system/etlegacy-bot.service: ExecStart=.../venv/bin/python3 bot/ultimate_bot.py
/etc/systemd/system/etlegacy-web.service: ExecStart=.../website/venv/bin/uvicorn backend.main:app ...
```
So this isn't a symlink swap — each venv has to be rebuilt against a real
3.11 interpreter once one exists on the box.

**This is a dev-box-only problem — production is already fine.** An earlier
version of this doc repeated the task backlog's claim that the production VM
also runs 3.10, flagged as un-re-verified. There is a tracked source, and it
says otherwise: `docs/VM_ACCESS.md` lists prod as **Debian 13.3 (Trixie) with
Python 3.13.5**, which already satisfies `pyproject.toml`'s
`requires-python = ">=3.11,<3.14"`. Everything below is about this Ubuntu
22.04 dev box; applying it to prod would be an unnecessary *downgrade*
(Codex review on #584, second round).

## Why it matters right now

`website/backend/map_geometry/pk3_index.py:10` uses `from enum import
StrEnum`, stdlib-new in 3.11. **Both** of the map-geometry test modules fail
to collect on this box, and it's worth being precise about why, because the
indirect case is easy to get wrong (an earlier version of this doc did):

- `tests/unit/test_pk3_geometry_index.py` imports `pk3_index` directly.
- `tests/unit/test_bsp_reader.py` imports the *sibling* module
  `website.backend.map_geometry.bsp` — but that still fails, because
  importing anything from the package runs
  `website/backend/map_geometry/__init__.py`, which itself does
  `from website.backend.map_geometry.pk3_index import (...)` (line 30). The
  package initializer, not the test's own import, is what pulls `StrEnum` in.

Confirmed on this box (Python 3.10.12):

```
$ venv/bin/python -m pytest tests/unit/test_bsp_reader.py
website/backend/map_geometry/pk3_index.py:10: in <module>
    from enum import StrEnum
E   ImportError: cannot import name 'StrEnum' from 'enum' (/usr/lib/python3.10/enum.py)
ERROR tests/unit/test_bsp_reader.py
```

Both collect fine in CI (which runs 3.11). This is blocking Codex's tests from
running locally right now, not a future-proofing nice-to-have.

## Plan (owner executes, in order)

### 1. Add deadsnakes PPA (system change, needs sudo)
```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev
python3.11 --version   # confirm a real release, not an -rc
```
Ubuntu 22.04 (Jammy) is well-supported by deadsnakes; this is the standard
path other projects use to get a stable 3.11+ on this OS release without
waiting for an Ubuntu point release to ship one.

**Stop each service before touching its venv, not after.** Renaming a
venv out from under a running process and creating a new (initially
incomplete) `site-packages` at the same path leaves that process's
`sys.path` pointing into a half-installed tree — any late/lazy import
during the `pip install` steps below can fail or pick up a mismatched
dependency. `scripts/deploy_release.sh` already does this
(`systemctl stop slomix-web slomix-bot` before touching anything, restart
only once the new tree is ready) — follow the same order here, and stop
the two services independently since they're rebuilt as separate steps.

### 2. Rebuild the bot venv
```bash
sudo systemctl stop etlegacy-bot        # stop BEFORE touching its venv
cd /home/samba/share/slomix_discord
# Refuse rather than nest: with venv-3.10.bak already present (step 5 says to
# keep it for days, so a re-run is likely) this mv would put the venv INSIDE it
# and the rollback would restore the older outer copy instead.
[ -e venv-3.10.bak ] && { echo "venv-3.10.bak exists — remove it first"; exit 1; }
mv venv venv-3.10.bak          # keep for rollback, don't delete yet
python3.11 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt -r requirements-dev.txt
venv/bin/pip check              # scripts/check_env.py isn't tracked in
                                 # this repo — pip check is the nearest
                                 # in-repo-usable dependency-consistency
                                 # verification
sudo systemctl start etlegacy-bot
sudo systemctl status etlegacy-bot
```

### 3. Rebuild the website venv
```bash
sudo systemctl stop etlegacy-web        # stop BEFORE touching its venv
cd website
[ -e venv-3.10.bak ] && { echo "website/venv-3.10.bak exists — remove it first"; exit 1; }
mv venv venv-3.10.bak
python3.11 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
venv/bin/pip check
cd ..
sudo systemctl start etlegacy-web
sudo systemctl status etlegacy-web
```

### 4. Production — verify only; do NOT run steps 1-3 there
`docs/VM_ACCESS.md` lists prod as Debian 13.3 (Trixie) / **Python 3.13.5**,
already inside `requires-python = ">=3.11,<3.14"`. Installing 3.11 and
rebuilding its venvs against it would be a pointless downgrade. Confirm the
docs match reality and stop:

```bash
ssh slomix-vm '/opt/slomix/venv-bot/bin/python --version; /opt/slomix/venv-web/bin/python --version'
```

`pyproject.toml` requires `>=3.11,<3.14`, so the acceptable window is 3.11,
3.12 or 3.13 — it is bounded at BOTH ends. A report of 3.14+ (plausible after
an OS upgrade, since Debian moves fast) is *also* out of range and needs work,
just in the other direction; saying "only < 3.11 needs work" would wave that
through (Codex review on #584, third round):

| Reported | Meaning |
|---|---|
| 3.11 – 3.13 | in range — nothing to do on prod |
| < 3.11 | too old — the `StrEnum` failure applies; see below |
| ≥ 3.14 | too new for the current pin — do NOT proceed with this plan; either widen `requires-python` after testing, or pin the venv to a supported interpreter |

Only in the too-old case does prod need the rebuild below, and it can't
reuse steps 2-3 verbatim — different paths, unit names, and ownership. Per
`slomix_vm_setup.sh`: `APP_DIR="/opt/slomix"`, `BOT_VENV="$APP_DIR/venv-bot"`,
`WEB_VENV="$APP_DIR/venv-web"`, units `slomix-bot`/`slomix-web`, and each venv
is chowned to its own service account (`chown -R slomix_bot:slomix`,
`chown -R slomix_web:slomix`, lines 785-786). A venv created with plain
`sudo python3.11 -m venv` is left root-owned and the service — which runs as
`slomix_bot`/`slomix_web` — cannot write to it, so the chown is not optional
(Codex review on #584, second round):

Two preflight checks before touching anything, because both failure modes
leave the box worse than when you started (Codex review on #584, third round):

```bash
# 1. Does a 3.11+ interpreter even exist here? The canonical bootstrap installs
#    only generic python3/python3-venv, so `python3.11` may well be absent — and
#    the sequence below stops the service and MOVES its working venv before ever
#    invoking it, so discovering this late means an outage with no environment.
ssh slomix-vm 'command -v python3.11 || echo "MISSING — install it before proceeding"'

# 2. Do stale backups from a previous run exist? `mv venv-bot venv-bot.bak` with
#    the target already present moves the venv INSIDE it
#    (/opt/slomix/venv-bot.bak/venv-bot), so the rollback below silently restores
#    the older outer environment instead. Step 5 recommends keeping backups for
#    days, which makes a re-run likely.
ssh slomix-vm 'ls -d /opt/slomix/venv-*.bak 2>/dev/null && echo "REMOVE or RENAME these first"'
```

```bash
sudo systemctl stop slomix-bot
cd /opt/slomix
# Refuse rather than nest if a previous backup is still there.
[ -e venv-bot.bak ] && { echo "venv-bot.bak exists — remove it first"; exit 1; }
sudo mv venv-bot venv-bot.bak
sudo python3.11 -m venv venv-bot
sudo venv-bot/bin/pip install --upgrade pip
sudo venv-bot/bin/pip install -r requirements.txt
sudo venv-bot/bin/pip check
sudo chown -R slomix_bot:slomix venv-bot     # match slomix_vm_setup.sh:785
sudo systemctl start slomix-bot

sudo systemctl stop slomix-web
[ -e venv-web.bak ] && { echo "venv-web.bak exists — remove it first"; exit 1; }
sudo mv venv-web venv-web.bak
sudo python3.11 -m venv venv-web
sudo venv-web/bin/pip install --upgrade pip
sudo venv-web/bin/pip install -r website/requirements.txt
sudo venv-web/bin/pip check
sudo chown -R slomix_web:slomix venv-web     # match slomix_vm_setup.sh:786
sudo systemctl start slomix-web
```

### 5. Rollback, if something breaks
Conditional per phase — do **not** blanket-delete both venvs. A bot rebuild
failure in step 2 means `website/venv-3.10.bak` was never created, and an
unconditional `mv website/venv-3.10.bak website/venv` would fail *after*
`rm -rf website/venv` had already destroyed the still-good original.

Dev box (run from the repo root — step 3 leaves you inside `website/`, and
these relative paths are wrong from there, so `cd` back first):

```bash
cd /home/samba/share/slomix_discord    # step 3 ends inside website/

# Bot only, if step 2 failed:
sudo systemctl stop etlegacy-bot
[ -d venv-3.10.bak ] && rm -rf venv && mv venv-3.10.bak venv
sudo systemctl start etlegacy-bot

# Website only, if step 3 failed (bot stays on whatever step 2 left it at):
sudo systemctl stop etlegacy-web
[ -d website/venv-3.10.bak ] && rm -rf website/venv && mv website/venv-3.10.bak website/venv
sudo systemctl start etlegacy-web
```

Prod (only relevant if step 4 found an unsupported interpreter). These paths
are under `/opt/slomix`, which the deploy account cannot write unprivileged —
every `rm`/`mv` needs `sudo`, and the restored venv keeps its original
ownership because `mv` preserves it:

```bash
cd /opt/slomix

sudo systemctl stop slomix-bot
[ -d venv-bot.bak ] && sudo rm -rf venv-bot && sudo mv venv-bot.bak venv-bot
sudo systemctl start slomix-bot

sudo systemctl stop slomix-web
[ -d venv-web.bak ] && sudo rm -rf venv-web && sudo mv venv-web.bak venv-web
sudo systemctl start slomix-web
```

Keep the `.bak` directories (`venv-3.10.bak`, `website/venv-3.10.bak`, and on
prod `venv-bot.bak`/`venv-web.bak`) until the rebuilt venvs have run cleanly
for a few days — cheap insurance, this box has 1.7TB free per the disk checks
elsewhere in this backlog.

## Verify

```bash
# Both of these currently fail to collect on 3.10 and should pass once the bot
# venv is rebuilt: the first imports pk3_index directly, the second reaches it
# through the package's __init__.py (see "Why it matters right now").
venv/bin/python -m pytest tests/unit/test_pk3_geometry_index.py tests/unit/test_bsp_reader.py
```
