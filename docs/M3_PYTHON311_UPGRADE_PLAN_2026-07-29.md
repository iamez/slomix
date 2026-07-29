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

Per the task backlog, the production VM also runs 3.10 (not independently
re-verified here — no direct prod access from this session; confirm before
relying on it).

## Why it matters right now

`website/backend/map_geometry/pk3_index.py:10` uses `from enum import
StrEnum`, stdlib-new in 3.11. `tests/unit/test_pk3_geometry_index.py`
imports `pk3_index` directly (`from website.backend.map_geometry.pk3_index
import ...`) and collects fine in CI (which runs 3.11) but fails with an
`ImportError` on this box and presumably on prod — that's the actual
blocked test. (`tests/unit/test_bsp_reader.py` imports a sibling module,
`website.backend.map_geometry.bsp`, which doesn't touch `pk3_index` or
`StrEnum` — it collects fine on 3.10 today and isn't evidence either way.)
It's blocking Codex's tests from running locally right now, not a
future-proofing nice-to-have.

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
mv venv venv-3.10.bak
python3.11 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
venv/bin/pip check
cd ..
sudo systemctl start etlegacy-web
sudo systemctl status etlegacy-web
```

### 4. Production implication — different paths, do not reuse steps 2-3 verbatim
Per the task backlog, prod is also on 3.10, so the same `StrEnum`-triggered
`ImportError` would surface on prod's first import of `pk3_index.py`-
dependent code too, not just locally. Don't assume this document's "not
independently re-verified" caveat away — confirm prod's actual interpreter
version before treating this as done there.

The production VM does **not** use this dev box's paths or unit names.
Per `slomix_vm_setup.sh` (`APP_DIR="/opt/slomix"`,
`BOT_VENV="$APP_DIR/venv-bot"`, `WEB_VENV="$APP_DIR/venv-web"`), the
canonical layout is `/opt/slomix/venv-bot` and `/opt/slomix/venv-web` —
not `venv`/`website/venv` at `/home/samba/share/slomix_discord`. On the
canonical VM, steps 2-3 become:
```bash
sudo systemctl stop slomix-bot
cd /opt/slomix
sudo mv venv-bot venv-bot-3.10.bak
sudo python3.11 -m venv venv-bot
sudo venv-bot/bin/pip install --upgrade pip
sudo venv-bot/bin/pip install -r requirements.txt
sudo venv-bot/bin/pip check
sudo systemctl start slomix-bot

sudo systemctl stop slomix-web
sudo mv venv-web venv-web-3.10.bak
sudo python3.11 -m venv venv-web
sudo venv-web/bin/pip install --upgrade pip
sudo venv-web/bin/pip install -r website/requirements.txt
sudo venv-web/bin/pip check
sudo systemctl start slomix-web
```

### 5. Rollback, if something breaks
Conditional per phase — do **not** blanket-delete both venvs, since a bot
rebuild failure in step 2 means `website/venv-3.10.bak` (or
`venv-web-3.10.bak` on prod) was never created, and an unconditional
`mv website/venv-3.10.bak website/venv` would fail after `rm -rf
website/venv` has already destroyed the still-good original:
```bash
# Bot only, if step 2 failed:
sudo systemctl stop etlegacy-bot
[ -d venv-3.10.bak ] && rm -rf venv && mv venv-3.10.bak venv
sudo systemctl start etlegacy-bot

# Website only, if step 3 failed (bot stays on whatever step 2 left it at):
sudo systemctl stop etlegacy-web
[ -d website/venv-3.10.bak ] && rm -rf website/venv && mv website/venv-3.10.bak website/venv
sudo systemctl start etlegacy-web
```
(Substitute `venv-bot`/`venv-web`/`venv-bot-3.10.bak`/`venv-web-3.10.bak`
and `slomix-bot`/`slomix-web` for the prod paths from step 4.)

Keep the `*-3.10.bak` directories until the 3.11 venvs have run cleanly for
a few days — cheap insurance, this box has 1.7TB free per the disk checks
elsewhere in this backlog.

## Verify

```bash
venv/bin/python -m pytest tests/unit/test_pk3_geometry_index.py
# should collect and pass without an ImportError once the bot venv is on 3.11
# (this is the test that actually imports pk3_index.py / StrEnum —
# test_bsp_reader.py imports a sibling module and doesn't exercise this)
```
