#!/usr/bin/env bash
# Cut the "review slices" for the ultra code review.
#
# WHY: the review accepts <= 8 000 changed lines and <= 500 files per run, and
# the code changed since production (v1.39.0) is ~93 k lines. So each area
# gets its own base branch: `main` with that area's paths put back to their
# v1.39.0 state, and a head branch `review/<area>` whose tree is exactly
# main's (parent = the base; GitHub refuses a PR whose head is an ancestor
# of its base, which main would be). The PR shows exactly the area's change
# since production, while the reviewer's checkout is byte-identical to main.
# These PRs are NEVER merged.
#
# Usage:
#   scripts/review_slices.sh measure            # sizes per slice against origin/main
#   scripts/review_slices.sh cut [--push]       # create immutable versioned snapshots
#   scripts/review_slices.sh prs                # retired: create new drafts explicitly
# Fetch explicitly before use. HEAD_REF and BASE_TAG are pinned once; reruns
# reuse identical refs, never refresh historical review PRs (#924-943).
set -euo pipefail
BASE_TAG="${BASE_TAG:-v1.39.0}"
HEAD_REF="${HEAD_REF:-origin/main}"
# Applied to every slice: generated bundles, lockfiles, recordings and images are not review material.
GLOBAL_EXCL=( ":!*.json" ":!*.lock" ":!*.svg" ":!*.png" ":!*.ico" ":!website/static/app" ":!website/static/dist" ":!*.min.js" ":!*.map" )

# name|pathspecs (space separated, git pathspec syntax; ':!' excludes allowed).
# NOTE: in a git pathspec a bare '*' also matches '/', so 'dir/*.ts' is
# recursive; use ':(glob)dir/*.ts' when you mean one directory level only.
SLICES=(
  "01-proximity-spiderweb-lua|proximity website/backend/services/round_web_service.py website/backend/services/replay_service.py website/backend/routers/replay_router.py website/backend/services/proximity website/backend/services/storytelling website/backend/routers/proximity_router.py website/backend/routers/storytelling_router.py scripts/build_w6_trace_fixtures.py scripts/compare_w6_engine_vs_offline.py tests/unit/test_w6_control_expectations.py"
  "01b-lua-modules|vps_scripts"
  "02-backend-routers|website/backend/routers :!website/backend/routers/replay_router.py :!website/backend/routers/proximity_router.py :!website/backend/routers/storytelling_router.py"
  "03-spa-core-lib|website/frontend/src/app/lib :!website/frontend/src/app/lib/proximity :!website/frontend/src/app/lib/geo :!website/frontend/src/app/lib/uploads :!website/frontend/src/app/lib/*.test.ts :!website/frontend/src/app/lib/*.test.tsx"
  "04-spa-core-shell|website/frontend/src/app/components website/frontend/src/app/lib/proximity website/frontend/src/app/lib/geo website/frontend/src/app/lib/uploads website/frontend/src/app/api website/frontend/src/app/routes.ts website/frontend/src/app/routes.data.json website/frontend/src/app/main.tsx website/frontend/src/app/*.css :!website/frontend/src/app/components/*.test.tsx :!website/frontend/src/app/components/*.test.ts"
  "05-spa-pages-a|website/frontend/src/app/pages :!website/frontend/src/app/pages/*.test.tsx :!website/frontend/src/app/pages/Proximity* :!website/frontend/src/app/pages/SpiderWeb* :!website/frontend/src/app/pages/Session* :!website/frontend/src/app/pages/Stats* :!website/frontend/src/app/pages/Availability* :!website/frontend/src/app/pages/Uploads* :!website/frontend/src/app/pages/Greatshot* :!website/frontend/src/app/pages/Live* :!website/frontend/src/app/pages/__fixtures__"
  "06-spa-pages-b|website/frontend/src/app/pages/Proximity* website/frontend/src/app/pages/SpiderWeb* website/frontend/src/app/pages/Session* website/frontend/src/app/pages/Stats* :!website/frontend/src/app/pages/*.test.tsx"
  "07-spa-pages-c|website/frontend/src/app/pages/Availability* website/frontend/src/app/pages/Uploads* website/frontend/src/app/pages/Greatshot* website/frontend/src/app/pages/Live* :!website/frontend/src/app/pages/*.test.tsx"
  "08-backend-services|website/backend :!website/backend/routers :!website/backend/services/round_web_service.py :!website/backend/services/replay_service.py :!website/backend/services/proximity :!website/backend/services/storytelling"
  "09-legacy-js-bot-db-tools|website/js website/templates bot migrations tools shared .github Makefile install.sh postgresql_database_manager.py slomix_vm_setup.sh pyproject.toml .env.example .gitignore .codacy.yaml .pre-commit-config.yaml README.md CHANGELOG.md"
  "10-frontend-legacy-react|website/frontend/src :!website/frontend/src/app :!website/frontend/src/api/generated"
  "11-frontend-e2e-config|website/frontend/e2e :(glob)website/frontend/*.ts :(glob)website/frontend/*.js :(glob)website/frontend/*.cjs :(glob)website/frontend/*.mjs website/frontend/public"
  "12-spa-tests-pages|website/frontend/src/app/pages/*.test.tsx"
  "13-spa-tests-lib-components|website/frontend/src/app/lib/*.test.ts website/frontend/src/app/lib/*.test.tsx website/frontend/src/app/components/*.test.tsx website/frontend/src/app/components/*.test.ts :(glob)website/frontend/src/app/*.test.ts :(glob)website/frontend/src/app/*.test.tsx website/frontend/src/app/test website/frontend/src/app/__mocks__"
  "14-scripts-a|scripts/[a-l]* :!scripts/build_w6_trace_fixtures.py :!scripts/compare_w6_engine_vs_offline.py"
  "15-scripts-b|scripts/[m-z]* scripts/[A-Z]*"
  "16-python-tests-a|tests :!tests/unit :!tests/unit/test_w6_control_expectations.py"
  "17-python-tests-unit-a|tests/unit/test_[a-h]*"
  "18-python-tests-unit-b|tests/unit/test_[i-o]*"
  "18b-python-tests-unit-b2|tests/unit/test_[p-r]*"
  "19-python-tests-unit-c|tests/unit/test_[s-z]* tests/unit/[!t]* :!tests/unit/test_w6_control_expectations.py"
)

exec python3 "$(dirname "$0")/review_snapshots.py" \
  --base "$BASE_TAG" --source "$HEAD_REF" \
  "${SLICES[@]/#/--area=}" "${GLOBAL_EXCL[@]/#/--exclude=}" "$@"
