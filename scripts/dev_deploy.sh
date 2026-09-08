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
# The SPA is built with npm run build:app after committing the exact target.
# Its provenance and staged bytes are checked before the run clone changes.
# Legacy static/modern is preserved, not copied without provenance.
# Only the owner runs deployment. DEV_PREFLIGHT_ONLY=1 checks/stages without
# changing the run clone or services; SKIP_STATIC=1 is intentionally rejected.
#
# Usage: scripts/dev_deploy.sh [ref]     (default: origin/main)
set -euo pipefail
RUN="${DEV_RUN_DIR:-/home/samba/share/slomix-dev-run}"
SRC="${DEV_SRC_DIR:-/home/samba/share/slomix_discord}"
REF="${1:-origin/main}"

[ "${SKIP_STATIC:-0}" != "1" ] || { echo "SKIP_STATIC=1 is no longer supported: every dev deploy requires proven SPA artifacts" >&2; exit 3; }
[ -d "$RUN/.git" ] || { echo "no run clone at $RUN" >&2; exit 2; }
[ "$(realpath "$RUN")" != "$(realpath "$SRC")" ] || { echo "source and run clone must differ" >&2; exit 2; }
[ ! -L "$RUN/website" ] && [ ! -L "$RUN/website/static" ] && [ ! -L "$RUN/website/static/app" ] || { echo "symlinked run artifacts are unsupported" >&2; exit 3; }
[ -z "$(git -C "$RUN" status --porcelain --untracked-files=no)" ] || { echo "run clone has tracked changes; refusing deploy" >&2; exit 3; }
# Resolve the requested source once. Fetch source refs explicitly BEFORE building.
target=$(git -C "$SRC" rev-parse --verify "$REF^{commit}")
helper="$(cd "$(dirname "$0")" && pwd)/spa_artifact.py"
# Same filesystem as RUN, but outside its active tree; no stale .new directory reuse.
stage=$(mktemp -d "$(dirname "$RUN")/.slomix-artifact.XXXXXXXX")
cleanup() {
  python3 -c 'import shutil,sys; shutil.rmtree(sys.argv[1])' "$stage"
}
trap cleanup EXIT
python3 "$helper" stage --source "$SRC" --target "$target" --stage "$stage/app"
if [ "${DEV_PREFLIGHT_ONLY:-0}" = "1" ]; then
  echo "preflight passed; staged artifact verified; run checkout and services unchanged"
  exit 0
fi

# No fetch, checkout or service action occurs before artifact staging succeeds.
git -C "$RUN" fetch -q "$SRC" "$target"
python3 "$helper" verify --source "$SRC" --target "$target" --stage "$stage/app"
before=$(git -C "$RUN" rev-parse --short HEAD)
git -C "$RUN" checkout -q -B main "$target"
after=$(git -C "$RUN" rev-parse --short HEAD)
echo "run dir: $before -> $after"
mkdir -p "$RUN/website/static"
# Preserve previous assets in a unique recovery directory; never delete by glob.
if [ -e "$RUN/website/static/app" ]; then
  previous=$(mktemp -d "$(dirname "$RUN")/.slomix-app-previous.XXXXXXXX")
  mv "$RUN/website/static/app" "$previous/app"
  echo "previous SPA retained at $previous/app"
fi
mv "$stage/app" "$RUN/website/static/app"
echo "SPA copied from verified stage for $target"
echo "WARNING: legacy static/modern preserved; its provenance is not verified or copied" >&2

if [ "${SKIP_RESTART:-0}" != "1" ]; then
  sudo -n systemctl restart etlegacy-bot etlegacy-web
  sleep 8
  for u in etlegacy-bot etlegacy-web; do
    pid=$(systemctl show "$u" -p MainPID --value)
    echo "$u: $(systemctl is-active "$u") pid=$pid cwd=$(readlink "/proc/$pid/cwd" 2>/dev/null || echo '?')"
  done
  curl -s -m 5 http://127.0.0.1:8000/api/build | head -c 160; echo
fi
