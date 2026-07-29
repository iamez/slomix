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
StrEnum`, stdlib-new in 3.11. Three test modules that import it
(`tests/unit/test_bsp_reader.py` and others in Codex's §9 W1-W2 work) collect
fine in CI (which runs 3.11) but fail with an `ImportError` on this box and
presumably on prod. It's blocking Codex's tests from running locally right
now, not a future-proofing nice-to-have.

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

### 2. Rebuild the bot venv
```bash
cd /home/samba/share/slomix_discord
mv venv venv-3.10.bak          # keep for rollback, don't delete yet
python3.11 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt -r requirements-dev.txt
venv/bin/python scripts/check_env.py --requirements requirements.txt --requirements requirements-dev.txt
```

### 3. Rebuild the website venv
```bash
cd website
mv venv venv-3.10.bak
python3.11 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
venv/bin/python ../scripts/check_env.py --requirements website/requirements.txt
cd ..
```

### 4. Restart both services
```bash
sudo systemctl restart etlegacy-bot etlegacy-web
sudo systemctl status etlegacy-bot etlegacy-web
```
(Or the prod-side unit names — `slomix-bot`/`slomix-web` — if running this
on the canonical VM instead of this dev box.)

### 5. Production implication
The same steps apply to the production VM once verified there independently
— per the task backlog, prod is also on 3.10, so the same
`StrEnum`-triggered `ImportError` would surface on prod's first import of
`pk3_index.py`-dependent code too, not just locally. Don't assume this
document's "not independently re-verified" caveat away — confirm prod's
actual interpreter version before treating this as done there.

### 6. Rollback, if something breaks
```bash
rm -rf venv website/venv
mv venv-3.10.bak venv
mv website/venv-3.10.bak website/venv
sudo systemctl restart etlegacy-bot etlegacy-web
```
Keep both `*-3.10.bak` directories until the 3.11 venvs have run cleanly for
a few days — cheap insurance, this box has 1.7TB free per the disk checks
elsewhere in this backlog.

## Verify

```bash
venv/bin/python -m pytest tests/unit/test_bsp_reader.py
# should collect without an ImportError once the bot venv is on 3.11
```
