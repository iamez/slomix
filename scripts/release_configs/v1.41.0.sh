# Release config for v1.41.0 — the round, reconstructed and drawn.
#
# NO NEW MIGRATIONS. 078 is still the highest in migrations/, so this carries
# the same 045..078 range as v1.40.0 — a straight upgrade from an older tag
# still applies everything and the ledger skips what is already applied.
#
# Ships (v1.40.0..main):
#   #790, #798  pre-push guard: it counted files inherited from main, and it
#               could not see the shape credentials actually take
#   #792  Layer 1 — one moment of a round reconstructed from the tracks,
#         with staleness, overlap conflicts and a causal velocity
#   #793  the page names what it cannot read instead of going dark
#   #794  LUA: the tracker captures what its header claims to capture
#   #795  the capture capability manifest — three states, and `unknown`
#         is never `disabled`
#   #796  the page states its own measured error; the reinforcement clock
#         joins the web, with an INDEPENDENT validation gate
#   #797  W6 trace evidence in the repository, dormant
#   #799  Layer 3 — what each player could plausibly have known
#   #800, #803, #804  Spider Web: BSP floor geometry for 8 maps, the belief
#         regions, team point of view withheld SERVER-side, one palette,
#         the clock panel and the snapshot's own integrity
#   #802, #805, #806  the standalone /app shell, Chart.js bundled, and the
#         first page of the new design
#   #807  the team view stopped leaking: separation, the enemy wave phase and
#         the belief timing that kept step with it — plus the entry point the
#         Spider Web page had never had
#   #808  the live surfaces can be told apart from their own failures: a map
#         that outlived its evidence, a voice report that stopped, a
#         timestamp that travelled without its zone
#   #809, #811, #813, #814  the rest of the new design's phases 1 and 2 —
#         system/diag/About, home/sessions, leaderboards/record-book/awards,
#         maps/weapons/form/retro-viz. ⛔ NONE OF IT IS SERVED (see /app note)
#   #786  docs/ boundary: publish what code points at, retire 121 others
#   #801  the contract said R0 rows had stopped; they had not
#   #812  the API starts describing what it returns: response_model on
#         /api/stats/overview and /api/stats/quick-leaders, plus the guard
#         that makes adding schemas safe at all (response_model FILTERS —
#         a field the handler returns and the model omits is dropped
#         silently, with a 200)
#
# ⛔ REGENERATE THIS LIST AT TAG TIME, do not extend it by hand:
#
#   diff <(git log --oneline v1.40.0..main | grep -oE "#[0-9]+" | sort -u) \
#        <(sed -n '/^# Ships/,/REGENERATE/p' "$0" | grep -oE "#[0-9]+" | sort -u)
#
# ⛔ SCOPED TO THE Ships BLOCK, not the whole file. The plain grep reported
# "nothing missing" for BOTH #812 and #807 while each appeared only in prose
# elsewhere — a grep finds the NUMBER, not the entry. Mentioned is not
# shipped, and the check that cannot tell them apart is not a check.
#
# It was written when #806 was the tip and had missed EIGHT merges by the
# time anyone looked (#786, #801, #808, #809, #811, #813, #814 — and #807,
# added a round earlier). That is not one oversight: a list written from
# "what is here now" misses everything that arrives after, every time. The
# command above cannot go stale; a hand-kept list always does.
#
#
# ⛔ /app IS NOT BUILT BY THIS DEPLOY, AND THAT IS THE POLICY, NOT AN
# OVERSIGHT. `deploy_release.sh` deliberately does not run `npm run
# build:app`; production stays vanilla-only until the new design reaches
# parity. `main.py` guards the mount on the build output existing, so /app
# answers 404 on production rather than erroring. Adding the build to the
# deploy IS the switchover, and that is the owner's call on the day.
#
# ⚠️ THE GUNFIRE CHANNEL WILL BE EMPTY. `proximity_shot_fired` has recorded
# nothing since 2026-08-11 (measured: 16/16 rounds had shots on 08-04, 0 of
# 96 across the eight session days since). Spider Web's audible-gunfire
# beliefs and its radius control therefore drive an empty channel on every
# new round; 427 older rounds still carry the data. Turning capture back on
# is a game-server change and the owner's decision — it is not in this tag.
#
# NOTE: ~1.4 MB of exported map geometry ships in the checkout
# (`website/assets/maps/geometry/`, 8 maps + manifest). It is git-tracked, so
# the normal checkout carries it; no extra step, and no CDN dependency —
# Spider Web fetches it same-origin.
#
# POST-DEPLOY (owner, still outstanding from v1.40.0 — see PR #781):
#
# ⛔ THE v1.40.0 VERSION OF THIS NOTE IS WRONG AND I COPIED IT. It says to set
# the variable in `/opt/slomix/.env`. On a VM provisioned by
# `slomix_vm_setup.sh` the web unit runs with `EnvironmentFile=website/.env`,
# and `main.py:35-39` reads the ROOT file only when the website file is
# ABSENT — so the web process never sees it. Since the rsync step empties the
# old directory first, following the old instruction leaves existing uploads
# unserved and sends new ones back into the checkout (Codex, PR #810). The
# deploy script already learned this once: its FLAGS upsert writes BOTH files
# for exactly this reason (`deploy_release.sh`, "Codex on #516").
#
# ⛔ AND THE ORDER MATTERS. Setting the variable before the move points the
# service at an empty directory — `UploadStorageService` creates it
# (`upload_store.py:112`, `mkdir(parents=True, exist_ok=True)`) and serves
# nothing, while the old files sit unreferenced. Move first, then point.
#
# ⛔ AND MY "UNTIL ALL FOUR ARE DONE, NOTHING CHANGES" WAS FALSE. Step 2 uses
# `--remove-source-files`: the moment it runs, the directory the RUNNING
# service still points at is empty. An interrupted procedure is not a safe
# one, and saying it was made a half-finished move sound survivable
# (Codex, PR #810).
#
# ⛔ THE SERVICE MUST BE DOWN FOR THE MOVE. `slomix-web` accepts uploads while
# it runs, and a file written after rsync has scanned that part of the tree
# stays under `website/data/uploads` — where step 3 then stops looking.
# Resumable chunks make the window worse, not better.
#
# So: ONE window, service stopped, and nothing half-done left overnight.
#
#   1. install -d -o slomix_web -g slomix -m 2750 /var/lib/slomix/uploads
#   2. systemctl stop slomix-web
#   3. rsync -a --remove-source-files \
#        /opt/slomix/website/data/uploads/ /var/lib/slomix/uploads/
#   4. set UPLOAD_STORAGE_ROOT=/var/lib/slomix/uploads in BOTH
#        /opt/slomix/.env AND /opt/slomix/website/.env (if it exists)
#   5. systemctl start slomix-web
#
# ROLLBACK, if step 3 or 4 fails: rsync the files back
#   (`rsync -a --remove-source-files /var/lib/slomix/uploads/ \
#     /opt/slomix/website/data/uploads/`), remove the variable from both
#   files, and start the service. The old default names the original
#   directory, so a clean revert is a revert of steps 3 and 4 only.
#
# Not starting the move at all is safe. STOPPING PART-WAY IS NOT.
# ✅ #807 IS IN THE TAG (merged as `83e777a8`), so the two claims below that
# depended on it now hold: Spider Web has an entry point from the replay
# view, and the team point of view withholds the other side's positions,
# wave phase and formation on the SERVER.
#
# ⚠️ THIS BLOCK USED TO SAY THE OPPOSITE, with a replacement paragraph to
# paste if #807 was absent. That warning was correct when written and
# FALSE the moment #807 landed — the same failure as the stale Ships list
# above, in the other direction: a note written from "what is here now"
# misleads once the world moves, and a note that OVERSTATES safety is the
# worse half. Verified against main before deleting it:
#   grep '"clock": clock' website/backend/services/round_web_service.py  -> gone
#   grep getRouteHash website/js/replay.js                                -> present
#
# shellcheck shell=bash
# shellcheck disable=SC2034
MIGRATIONS=(
  "045_drop_orphan_monitoring_tables.sql"
  "046_fix_proximity_round_id_exact_match.sql"
  "047_orphan_recovery_null_round_id.sql"
  "048_orphan_recovery_drift_tolerance.sql"
  "049_add_round_canonical_id.sql"
  "050_round_canonical_id_unique.sql"
  "051_add_audit_indexes.sql"
  "052_composite_indexes_proximity.sql"
  "053_add_weapon_stats_mv.sql"
  "054_add_storytelling_kis_shadow_audit.sql"
  "055_add_proximity_shot_fired.sql"
  "056_add_player_links_locale_twitch.sql"
  "057_add_rounds_is_valid.sql"
  "058_add_proximity_v7_tables.sql"
  "059_add_rounds_start_unix_index.sql"
  "060_add_kis_formula_version.sql"
  "061_prediction_shadow_v2.sql"
  "062_proximity_processed_files_capabilities.sql"
  "063_kis_gaming_session_id.sql"
  "064_backfill_kis_gaming_session_id.sql"
  "065_dedup_revive_weapon_accuracy.sql"
  "066_drop_orphan_monitoring_tables_tolerant.sql"
  "067_repair_lua_round_links.sql"
  "068_add_relinker_unlinked_indexes.sql"
  "069_add_shot_fired_relinker_index.sql"
  "070_uploads_expires_at.sql"
  # 071 ships with this tag (PR #645).
  # (copied from this one) ships it, and so the no-orphan-migration contract
  # test covers it. A checkout of the v1.30.1 TAG does not see this line.
  "071_add_round_id_coverage_indexes.sql"
  "072_repair_miscancelled_complete_rounds.sql"
  "073_player_identity_links.sql"
  "074_seed_ownator_sick_leave.sql"
  "075_canonical_guid_function.sql"
  "076_uploads_poster.sql"
  # 077 ships with this tag: player_aim_summary, the cached true-aim summary
  # (PR #746). Derived data only — safe to TRUNCATE, every row rebuilds itself
  # on the next profile read.
  "077_player_aim_summary.sql"
  # 078 ships with this tag: the player_match_stats VIEW (PR for the R0
  # retirement). Derived only — it holds no rows of its own, so applying it on
  # a host that already has it is a no-op CREATE OR REPLACE.
  "078_player_match_stats_view.sql"
)
FLAGS=(
  "TRUSTED_HOSTS=www.slomix.fyi,slomix.fyi,localhost,127.0.0.1"
)
RELEASE_NOTES="A round can now be looked at. Spider Web draws one moment of a match over the map's real floor geometry — where everyone stood, what each player could plausibly have known, and how far off the reconstruction is, measured rather than asserted. A team point of view withholds the other side's positions on the SERVER, not in the drawing. The reinforcement clock is reconstructed and independently validated, and every round now declares what it was able to capture in the first place, with 'unknown' kept distinct from 'off'. The new design's first page ships in this tag but is NOT served: /app stays dormant on production until it reaches parity, and building it is the switchover, not this release."
