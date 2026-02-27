#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v node >/dev/null 2>&1; then
    echo "node is required for JS lint checks"
    exit 1
fi

mapfile -t files < <(find website/js -type f -name "*.js" | sort)
if [ "${#files[@]}" -eq 0 ]; then
    echo "No JS files found under website/js"
    exit 0
fi

for file in "${files[@]}"; do
    node --check "$file"
done

echo "JS syntax lint passed (${#files[@]} files)"
