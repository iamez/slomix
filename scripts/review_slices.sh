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
#   scripts/review_slices.sh cut [--push]       # (re)create review-base/* branches from origin/main
#   scripts/review_slices.sh prs                # open the draft review PRs (needs --push first)
# Re-run `cut --push` whenever main moves: a stale base would show every later
# commit of every other area in the diff.
set -euo pipefail
BASE_TAG="${BASE_TAG:-v1.39.0}"
HEAD_REF="${HEAD_REF:-origin/main}"
LIMIT_LINES=8000
LIMIT_FILES=500
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

measure_one() {  # name pathspecs...
  local name="$1"; shift
  local stat
  stat=$(git diff --numstat "$BASE_TAG" "$HEAD_REF" -- "$@" "${GLOBAL_EXCL[@]}" | awk '$1!="-"{l+=$1+$2; f++} END{printf "%d %d", f+0, l+0}')
  local files=${stat% *} lines=${stat#* }
  local flag="ok"
  { [ "$lines" -gt $LIMIT_LINES ] || [ "$files" -gt $LIMIT_FILES ]; } && flag="OVER"
  printf "%-28s files=%4d lines=%6d %s\n" "$name" "$files" "$lines" "$flag"
}

cmd="${1:-measure}"; shift || true
case "$cmd" in
  measure)
    git fetch -q origin main
    for s in "${SLICES[@]}"; do
      name="${s%%|*}"; read -r -a paths <<< "${s#*|}"
      measure_one "$name" "${paths[@]}"
    done ;;
  cut)
    push=0; [ "${1:-}" = "--push" ] && push=1
    git fetch -q origin main
    tmp=$(mktemp -d)
    git worktree add -q --detach "$tmp" "$HEAD_REF"
    for s in "${SLICES[@]}"; do
      name="${s%%|*}"; read -r -a paths <<< "${s#*|}"
      br="review-base/$name"
      ( cd "$tmp"
        git checkout -q --detach "$HEAD_REF"
        # Put the area back to its production state inside the throwaway
        # worktree, using exactly the file set the diff names: files ADDED
        # since the tag go away, files MODIFIED/DELETED/TYPE-CHANGED come back
        # as they were at the tag. (`git checkout <tag> -- <pathspec>` was the
        # first version and aborted the whole command whenever one path did
        # not exist at the tag, which every slice with a new file has.)
        git diff -z --name-only --no-renames --diff-filter=A "$BASE_TAG" HEAD -- "${paths[@]}" "${GLOBAL_EXCL[@]}" \
          | xargs -0 -r git rm -q --ignore-unmatch --
        git diff -z --name-only --no-renames --diff-filter=MDT "$BASE_TAG" HEAD -- "${paths[@]}" "${GLOBAL_EXCL[@]}" \
          | xargs -0 -r git checkout -q "$BASE_TAG" --
        git commit -q -m "review-base: $name reverted to $BASE_TAG (never merge)" --allow-empty
        git branch -f "$br" HEAD
        # The PR head cannot be main itself: main is an ancestor of the base,
        # and GitHub refuses a PR with "no commits between". So the head is a
        # commit whose TREE is exactly main's and whose parent is the base —
        # the diff is the area's change in the right direction, and the
        # checkout a reviewer works in is byte-identical to main.
        head=$(git commit-tree "$HEAD_REF^{tree}" -p "$br" -m "review: $name — main's tree on top of the review base (never merge)")
        git branch -f "review/$name" "$head"
        printf "%-28s base=%s head=%s  " "$name" "$(git rev-parse --short "$br")" "$(git rev-parse --short "$head")"
        git diff --numstat "$br" "review/$name" -- . "${GLOBAL_EXCL[@]}" | awk '$1!="-"{l+=$1+$2; f++} END{printf "files=%d lines=%d\n", f+0, l+0}'
      )
      # --no-verify: the pre-push guard caps a push at 25 files because a real
      # PR should fit one reviewer's attention; a review-base commit is a
      # mechanical revert of a whole area (up to ~40 files) and is never
      # merged. The credential scan is not skipped in spirit: the revert
      # restores v1.39.0 content, which the 2026-08-27 history rewrite scrubbed.
      if [ $push -eq 1 ]; then
        git push -q --force --no-verify origin "refs/heads/$br:refs/heads/$br"
        git push -q --force --no-verify origin "refs/heads/review/$name:refs/heads/review/$name"
      fi
    done
    git worktree remove --force "$tmp" ;;
  prs)
    for s in "${SLICES[@]}"; do
      name="${s%%|*}"; br="review-base/$name"
      n=$(gh pr list --base "$br" --head "review/$name" --state open --json number -q '.[0].number')
      if [ -n "$n" ]; then echo "$br -> #$n (exists)"; continue; fi
      body=$(awk -v s="## $name" 'BEGIN{p=0} /^## /{p=($0==s)} p' docs/review/SLICES.md | tail -n +2)
      [ -n "$body" ] || { echo "no body for $name in docs/review/SLICES.md" >&2; continue; }
      gh pr create --draft --base "$br" --head "review/$name" \
        --title "review: $name — NEVER MERGE" \
        --body "$body" >/dev/null && echo "$br -> opened"
    done ;;
  *) echo "usage: $0 measure|cut [--push]|prs" >&2; exit 2 ;;
esac
