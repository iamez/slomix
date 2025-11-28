#!/bin/bash
# Pre-commit validation script
# Run this before pushing to catch errors early

echo "🔍 Running pre-commit checks..."
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FAILED=0

# 1. Python syntax check
echo "📝 Checking Python syntax..."
for file in bot/**/*.py; do
    if [ -f "$file" ]; then
        python3 -m py_compile "$file" 2>/dev/null
        if [ $? -ne 0 ]; then
            echo -e "${RED}❌ Syntax error in: $file${NC}"
            python3 -m py_compile "$file"
            FAILED=1
        fi
    fi
done

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All Python files have valid syntax${NC}"
fi
echo ""

# 2. Check for common issues
echo "🔎 Checking for common issues..."

# Check for missing imports
echo "  - Checking datetime imports..."
grep -l "datetime.now()" bot/**/*.py | while read file; do
    if ! grep -q "from datetime import datetime\|import datetime" "$file"; then
        echo -e "${YELLOW}⚠️  Missing datetime import in: $file${NC}"
        FAILED=1
    fi
done

grep -l "asyncio.sleep" bot/**/*.py | while read file; do
    if ! grep -q "import asyncio" "$file"; then
        echo -e "${YELLOW}⚠️  Missing asyncio import in: $file${NC}"
        FAILED=1
    fi
done

# Check for f-strings with user input (potential injection)
echo "  - Checking for potential injection vulnerabilities..."
if grep -rn 'f".*{.*command.*}"' bot/cogs/server_control.py | grep -v sanitize | grep -v "^#"; then
    echo -e "${YELLOW}⚠️  Potential command injection found${NC}"
fi

echo ""

# 3. Check method calls match definitions
echo "🔗 Verifying method calls..."
python3 << 'PYTHON'
import re
import sys

with open('bot/cogs/last_session_cog.py', 'r') as f:
    cog_content = f.read()

services = {
    'data_service': 'bot/services/session_data_service.py',
    'stats_aggregator': 'bot/services/session_stats_aggregator.py',
    'embed_builder': 'bot/services/session_embed_builder.py',
    'view_handlers': 'bot/services/session_view_handlers.py'
}

all_ok = True
for service_name, filepath in services.items():
    pattern = f'self\\.{service_name}\\.(\w+)\\('
    calls = set(re.findall(pattern, cog_content))

    with open(filepath, 'r') as f:
        content = f.read()
    methods = set(re.findall(r'(?:async )?def (\w+)\(', content))
    methods = {m for m in methods if not m.startswith('_')}

    missing = calls - methods
    if missing:
        print(f"❌ {service_name}: Methods called but not defined: {missing}")
        all_ok = False

if all_ok:
    print("✅ All method calls are valid")
    sys.exit(0)
else:
    sys.exit(1)
PYTHON

if [ $? -ne 0 ]; then
    FAILED=1
fi

echo ""

# 4. Summary
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}═══════════════════════════════════════${NC}"
    echo -e "${GREEN}✅ ALL CHECKS PASSED - SAFE TO COMMIT${NC}"
    echo -e "${GREEN}═══════════════════════════════════════${NC}"
    exit 0
else
    echo -e "${RED}═══════════════════════════════════════${NC}"
    echo -e "${RED}❌ SOME CHECKS FAILED - FIX BEFORE COMMIT${NC}"
    echo -e "${RED}═══════════════════════════════════════${NC}"
    exit 1
fi
