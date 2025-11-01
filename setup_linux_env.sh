#!/usr/bin/env bash
set -euo pipefail

# setup_linux_env.sh
# Detects common Linux distros, installs Python3 and venv support (requires sudo),
# removes any copied .venv, creates a new .venv in project root, upgrades pip,
# and installs requirements from requirements.txt.

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

echo "Project root: $PROJECT_ROOT"

# Recommend Python version
REQUIRED_PYTHON_MAJOR=3
REQUIRED_PYTHON_MINOR=10

# Helper: compare versions (returns 0 if installed >= required)
version_ge() {
  # usage: version_ge found_version required_version
  [ "$(printf '%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]
}

# Check python3 exists and version
if command -v python3 >/dev/null 2>&1; then
  PY_VER_FULL=$(python3 -V 2>&1 | awk '{print $2}')
  PY_MAJOR=$(echo "$PY_VER_FULL" | cut -d. -f1)
  PY_MINOR=$(echo "$PY_VER_FULL" | cut -d. -f2)
  echo "Found python3 version $PY_VER_FULL"
  if version_ge "$PY_VER_FULL" "$REQUIRED_PYTHON_MAJOR.$REQUIRED_PYTHON_MINOR"; then
    echo "python3 meets required version >= $REQUIRED_PYTHON_MAJOR.$REQUIRED_PYTHON_MINOR"
  else
    echo "python3 is too old (< $REQUIRED_PYTHON_MAJOR.$REQUIRED_PYTHON_MINOR). Will attempt to install newer python3 via package manager."
    INSTALL_PYTHON=1
  fi
else
  echo "python3 not found. Will attempt to install via package manager."
  INSTALL_PYTHON=1
fi

if [ "${INSTALL_PYTHON-0}" = "1" ]; then
  # Detect package manager
  if command -v apt-get >/dev/null 2>&1; then
    echo "Detected apt-get (Debian/Ubuntu).";
    echo "Running: sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip";
    sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip
  elif command -v dnf >/dev/null 2>&1; then
    echo "Detected dnf (Fedora/RHEL).")
    sudo dnf install -y python3 python3-venv python3-pip || sudo dnf install -y python3
  elif command -v yum >/dev/null 2>&1; then
    echo "Detected yum (older RHEL/CentOS).";
    sudo yum install -y python3 python3-venv python3-pip || sudo yum install -y python3
  elif command -v pacman >/dev/null 2>&1; then
    echo "Detected pacman (Arch).";
    sudo pacman -Syu --noconfirm python python-pip
  elif command -v zypper >/dev/null 2>&1; then
    echo "Detected zypper (openSUSE).";
    sudo zypper refresh && sudo zypper install -y python3 python3-pip
  else
    echo "Could not detect package manager. Please install Python 3.10+ manually and re-run this script.";
    exit 1
  fi
fi

# Remove a copied venv if it looks broken (optional prompt)
if [ -d ".venv" ]; then
  echo ".venv exists. It's safe to remove and recreate a local venv. Remove it now? [y/N]"
  read -r REPLY
  if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    rm -rf .venv
    echo "Removed existing .venv"
  else
    echo "Keeping existing .venv";
  fi
fi

# Create .venv if missing
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  echo "Created .venv"
fi

# Use venv python to upgrade pip and install requirements
.VENV_PY="${PROJECT_ROOT}/.venv/bin/python"
"$VENV_PY" -m pip install -U pip setuptools wheel
if [ -f requirements.txt ]; then
  "$VENV_PY" -m pip install -r requirements.txt
else
  echo "requirements.txt not found in project root; skipping pip install -r requirements.txt"
fi

# Quick compile check
echo "Running a quick compile check (no tests)"
"$VENV_PY" -m compileall -q . || true

echo "Done. Activate venv by running: source .venv/bin/activate"
