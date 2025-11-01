Project environment setup (Windows + Linux)

This project expects a local Python 3 installation and a virtual environment. Because this repository was copied from another machine, there may be a pre-existing `.venv` that points to the original system Python (it can be broken). Follow the steps below.

Windows (PowerShell)

1. Install Python 3.10+ if you don't have it:
   - Download from https://www.python.org/downloads/ and check "Add Python to PATH" during installation.
   - Alternatively install from the Microsoft Store or winget.

2. (Optional) If a `.venv` directory exists from another machine, remove it so we can recreate a local venv:

```powershell
cd C:\Users\seareal\Documents\stats
Remove-Item -Recurse -Force .venv
```

3. Run the helper script I added to create a fresh venv and install dependencies:

```powershell
# allow script execution for this session
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force
# run the helper
.\setup_env.ps1
```

This will create `.venv` and install packages from `requirements.txt`.

Linux / macOS (bash)

1. Install Python 3.10+ using your package manager.

2. Remove any copied venv folder:

```bash
cd /path/to/project
rm -rf .venv
```

3. Create and use a venv, then install requirements:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
```

Quick checks

- To validate Python is available on Windows:

```powershell
py -3 --version
# or
python --version
```

- To run a lightweight syntax check (no extra tools required):

```powershell
.venv\Scripts\python.exe -m compileall .
```

Notes

- I found a pre-existing `.venv` in the repo that likely points to the original author's Python path. If you copied the whole folder from another machine, remove `.venv` and recreate it locally.
- After you run `setup_env.ps1` successfully, tell me and I'll:
  - run quick tests (pytest) and a compile check
  - scan the repo for hard-coded absolute paths and propose fixes
  - update the README with exact start/run instructions for the bot
