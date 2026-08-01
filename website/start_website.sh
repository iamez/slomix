#!/bin/bash
# ET:Legacy Stats Website - Linux Startup Script
# Run this script to start the website backend on port 7000

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}     ET:Legacy Stats Website - Startup Script${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Get script directory (website folder)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo -e "${YELLOW}📁 Website directory: ${SCRIPT_DIR}${NC}"
echo -e "${YELLOW}📁 Project root: ${PROJECT_ROOT}${NC}"

# Change to project root (needed for imports)
cd "$PROJECT_ROOT"

# Check for .env file
if [ -f "$SCRIPT_DIR/.env" ]; then
    echo -e "${GREEN}✓ Found website .env file${NC}"
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
elif [ -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${YELLOW}⚠ Using project root .env file${NC}"
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
else
    echo -e "${RED}✗ No .env file found!${NC}"
    echo -e "${YELLOW}  Copy .env.example to .env and configure it${NC}"
    exit 1
fi

# Default values
WEBSITE_HOST="${WEBSITE_HOST:-0.0.0.0}"
WEBSITE_PORT="${WEBSITE_PORT:-7000}"
WEBSITE_RELOAD="${WEBSITE_RELOAD:-false}"

echo ""
echo -e "${YELLOW}Configuration:${NC}"
echo -e "  Host: ${GREEN}${WEBSITE_HOST}${NC}"
echo -e "  Port: ${GREEN}${WEBSITE_PORT}${NC}"
echo -e "  Reload: ${GREEN}${WEBSITE_RELOAD}${NC}"
echo ""

# Check Python — presence AND version.
#
# The bounds are read from pyproject.toml so they cannot drift the way the
# previous hardcoded "3.8+" did (three releases behind the real 3.11 floor).
# The version check matters as much as the message: printing "✓ Python 3.10.12"
# and starting anyway just moves the failure to an import error on
# `from enum import StrEnum`, which is the opposite of failing early on the
# real cause (Copilot review on #595).
PY_REQ=$(grep -oE 'requires-python[[:space:]]*=[[:space:]]*"[^"]+"' "$(dirname "$0")/../pyproject.toml" 2>/dev/null \
         | sed -E 's/.*"([^"]+)".*/\1/')
PY_MIN=$(printf '%s' "$PY_REQ" | grep -oE '>=[0-9]+\.[0-9]+' | tr -d '>=')
PY_MAX=$(printf '%s' "$PY_REQ" | grep -oE '<[0-9]+\.[0-9]+'  | tr -d '<')
PY_SRC="pyproject.toml: $PY_REQ"
[ -n "$PY_MIN" ] || { PY_MIN="3.11"; PY_SRC="built-in default (pyproject.toml not found or unparsable)"; }
[ -n "$PY_MAX" ] || { PY_MAX="3.14"; PY_SRC="built-in default (pyproject.toml not found or unparsable)"; }

version_ge() { [ "$(printf '%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]; }

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python3 not found! This project requires ${PY_REQ:->=3.11,<3.14}${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
if ! version_ge "$PYTHON_VERSION" "$PY_MIN"; then
    echo -e "${RED}✗ Python $PYTHON_VERSION is below the required $PY_MIN ($PY_SRC)${NC}"
    echo -e "${RED}  Starting anyway would fail on 3.11+ syntax (e.g. 'from enum import StrEnum')${NC}"
    exit 1
fi
if version_ge "$PYTHON_VERSION" "$PY_MAX"; then
    echo -e "${RED}✗ Python $PYTHON_VERSION is at or above the unsupported $PY_MAX ($PY_SRC)${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python ${PYTHON_VERSION}${NC}"

# Check if virtual environment exists
if [ -d "$PROJECT_ROOT/venv" ]; then
    echo -e "${GREEN}✓ Activating virtual environment${NC}"
    source "$PROJECT_ROOT/venv/bin/activate"
elif [ -d "$PROJECT_ROOT/.venv" ]; then
    echo -e "${GREEN}✓ Activating virtual environment${NC}"
    source "$PROJECT_ROOT/.venv/bin/activate"
else
    echo -e "${YELLOW}⚠ No virtual environment found, using system Python${NC}"
fi

# Check dependencies
echo -e "${YELLOW}Checking dependencies...${NC}"
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo -e "${RED}✗ FastAPI not installed!${NC}"
    echo -e "${YELLOW}  Run: pip install -r website/requirements.txt${NC}"
    exit 1
fi

if ! python3 -c "import uvicorn" 2>/dev/null; then
    echo -e "${RED}✗ Uvicorn not installed!${NC}"
    echo -e "${YELLOW}  Run: pip install -r website/requirements.txt${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Dependencies OK${NC}"
echo ""

# Build uvicorn command
UVICORN_CMD="python3 -m uvicorn website.backend.main:app --host ${WEBSITE_HOST} --port ${WEBSITE_PORT}"

if [ "$WEBSITE_RELOAD" = "true" ]; then
    UVICORN_CMD="$UVICORN_CMD --reload"
    echo -e "${YELLOW}🔄 Auto-reload enabled (development mode)${NC}"
fi

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🚀 Starting website on http://${WEBSITE_HOST}:${WEBSITE_PORT}${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Run uvicorn
exec $UVICORN_CMD
