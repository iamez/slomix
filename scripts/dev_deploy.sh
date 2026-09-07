#!/usr/bin/env bash
# Deploy main to the DEV run directory and restart the dev services.
#
# WHY (2026-09-07): the dev services used to run straight out of the agents'
# working tree, so any `git checkout` there was a silent deploy at the next
# restart. They now run from a separate clone kept on `main`:
#   /home/samba/share/slomix-dev-run
# venv/ and website/venv/ are symlinks into the agents' tree (same packages;
# a fresh venv is the next step), local_proximity/, data/greatshot/ and
# website/data/uploads/ are symlinks (one corpus, one store), local_stats/,
# local_gametimes/ and logs/ are the run dir's own. .env lives in the run
# dir with its four absolute paths pointing there.
#
# The SPA (website/static/app) and the legacy bundle (static/modern) are
# BUILT in the agents' tree (the run dir has no node_modules — this box has
# 1.8 GB RAM, a vite build here would thrash) and COPIED by this script.
#
# Usage: scripts/dev_deploy.sh [ref]     (default: origin/main)
set -euo pipefail
RUN="${DEV_RUN_DIR:-/home/samba/share/slomix-dev-run}"
SRC="${DEV_SRC_DIR:-/home/samba/share/slomix_discord}"
REF="${1:-origin/main}"

[ -d "$RUN/.git" ] || { echo "no run dir at $RUN — see docs/CLAUDE.md (Building & Running)" >&2; exit 2; }
git -C "$RUN" fetch -q --tags origin
before=$(git -C "$RUN" rev-parse --short HEAD)
git -C "$RUN" checkout -q -B main "$REF"
after=$(git -C "$RUN" rev-parse --short HEAD)
echo "run dir: $before -> $after ($(git -C "$RUN" log -1 --format=%s))"

# The bundles are artefacts, not code: the tree can be on the right commit
# while static/app was built hours before the SPA source last changed
# (2026-09-07: bundle 11:03, source 00:23 next day — /api/build reads the
# commit and would have looked right). Refuse to copy a bundle older than
# its source; SKIP_STATIC=1 deploys the code alone.
if [ "${SKIP_STATIC:-0}" != "1" ]; then
  newest_src=$(git -C "$SRC" log -1 --format=%ct -- website/frontend/src/app website/frontend/src/api website/frontend/package.json)
  built=$(stat -c %Y "$SRC/website/static/app/app.html" 2>/dev/null || echo 0)
  if [ "$built" -lt "$newest_src" ]; then
    echo "⛔ static/app in $SRC was built $(date -d @"$built" +%F\ %R) but website/frontend/src/app changed $(date -d @"$newest_src" +%F\ %R):" >&2
    echo "   run (cd $SRC/website/frontend && npm run build:app) first, or SKIP_STATIC=1 to deploy the code alone" >&2
    exit 3
  fi
fi

for d in app modern; do
  if [ "${SKIP_STATIC:-0}" = "1" ]; then break; fi
  if [ -d "$SRC/website/static/$d" ]; then
    rm -rf "$RUN/website/static/$d.new"
    cp -a "$SRC/website/static/$d" "$RUN/website/static/$d.new"
    rm -rf "$RUN/website/static/$d.prev"
    [ -d "$RUN/website/static/$d" ] && mv "$RUN/website/static/$d" "$RUN/website/static/$d.prev"
    mv "$RUN/website/static/$d.new" "$RUN/website/static/$d"
    echo "static/$d copied from the agents' tree ($(du -sh "$RUN/website/static/$d" | cut -f1))"
  fi
done

if [ "${SKIP_RESTART:-0}" != "1" ]; then
  sudo -n systemctl restart etlegacy-bot etlegacy-web
  sleep 8
  for u in etlegacy-bot etlegacy-web; do
    pid=$(systemctl show "$u" -p MainPID --value)
    echo "$u: $(systemctl is-active "$u") pid=$pid cwd=$(readlink "/proc/$pid/cwd" 2>/dev/null || echo '?')"
  done
  curl -s -m 5 http://127.0.0.1:8000/api/build | head -c 160; echo
fi
