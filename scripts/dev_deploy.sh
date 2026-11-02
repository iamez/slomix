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
# Only the owner runs deployment. DEV_PREFLIGHT_ONLY=1 stages and reads both
# DB schemas and systemd unit configuration without
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
# A clean status can hide modified runtime bytes behind index flags. Reject
# these before status (which can refresh the index), source fetch or staging.
# NUL records preserve arbitrary Git paths; lowercase tags mean assume-unchanged,
# S means skip-worktree (s means both). Git failures must abort, not look empty.
python3 - "$RUN" "$SRC" <<'PY'
import subprocess
import sys

for root in sys.argv[1:]:
    entries = subprocess.check_output(["git", "-C", root, "ls-files", "-v", "-z"])
    if any(entry[:1].islower() or entry[:1] == b"S" for entry in entries.split(b"\0") if entry):
        sys.exit("source/run clone has unsupported index flags; refusing deploy")
PY
[ -z "$(git -C "$RUN" status --porcelain --untracked-files=no)" ] || { echo "run clone has tracked changes; refusing deploy" >&2; exit 3; }
# Refresh the default source ref before pinning it; explicit commits stay offline.
if [ "$REF" = "origin/main" ]; then
  git -C "$SRC" fetch -q origin refs/heads/main:refs/remotes/origin/main
fi
target=$(git -C "$SRC" rev-parse --verify "$REF^{commit}")
helper="$SRC/scripts/spa_artifact.py"
# Same filesystem as RUN, but outside its active tree; no stale .new directory reuse.
stage=$(mktemp -d "$(dirname "$RUN")/.slomix-artifact.XXXXXXXX")
cleanup() {
  python3 -c 'import shutil,sys; shutil.rmtree(sys.argv[1])' "$stage"
}
trap cleanup EXIT
python3 "$helper" stage --source "$SRC" --target "$target" --stage "$stage/app"
# Artifact provenance includes these tracked tools and migration bytes. Never
# fall back to bot/owner credentials when the web role cannot pass this gate.
gate_python="${DEV_GATE_PYTHON:-$SRC/venv/bin/python}"
"$gate_python" "$SRC/scripts/dev_verify_health.py" capture --run "$RUN" > "$stage/services-before.json"
for consumer in bot web; do
  if [ "$consumer" = bot ]; then
    env_file="$RUN/.env"
    db_host="${DEV_BOT_DB_HOST:-192.168.64.116}"
    db_user=etlegacy_user
  else
    env_file="$RUN/website/.env"
    db_host="${DEV_WEB_DB_HOST:-localhost}"
    db_user=website_app
  fi
  echo "checking $consumer schema compatibility for $target"
  "$gate_python" "$SRC/scripts/dev_schema_preflight.py" \
    --env-file "$env_file" --expected-host "$db_host" \
    --expected-port "${DEV_DB_PORT:-5432}" --expected-database "${DEV_DB_NAME:-etlegacy}" \
    --expected-user "$db_user" --migrations-dir "$SRC/migrations"
done
python3 "$helper" verify --source "$SRC" --target "$target" --stage "$stage/app"
if [ "${DEV_PREFLIGHT_ONLY:-0}" = "1" ]; then
  echo "preflight passed; staged artifact verified; run checkout and services unchanged"
  exit 0
fi

# No run-clone fetch, checkout or service action precedes successful staging.
git -C "$RUN" fetch -q "$SRC" "$target"
python3 "$helper" verify --source "$SRC" --target "$target" --stage "$stage/app"
before=$(git -C "$RUN" rev-parse HEAD)
previous="not-present"
deploy_failed() {
  echo "DEV deployment incomplete; previous source=$before retained SPA=$previous; no automatic rollback performed" >&2
}
trap deploy_failed ERR
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
  "$gate_python" "$SRC/scripts/dev_verify_health.py" verify --run "$RUN" \
    --target "$target" --previous "$stage/services-before.json"
  echo "DEV source, schema, services and HTTP build verified for $target"
else
  echo "Files installed only; services NOT restarted or certified healthy" >&2
fi
