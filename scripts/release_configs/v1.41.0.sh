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
#   install -d -o slomix_web -g slomix -m 2750 /var/lib/slomix/uploads
#   rsync -a --remove-source-files /opt/slomix/website/data/uploads/ /var/lib/slomix/uploads/
#   set UPLOAD_STORAGE_ROOT=/var/lib/slomix/uploads in /opt/slomix/.env, restart web
# ⛔ THESE NOTES ASSUME #807 IS IN THE TAG. Checked against main as it stands
# and two of them are not true without it:
#
#   * SPIDER WEB HAS NO ENTRY POINT. `route-registry.js` defines its
#     `buildHash` and nothing calls it — the only route to the page is typing
#     `#/spider-web/round/<id>` by hand. #807 adds the link from the replay
#     view. Tag without it and the release announces a page nobody can reach.
#
#   * THE TEAM-POV BOUNDARY STILL LEAKS. On main, `"clock": clock` and
#     `"nearest_teammate_separation": separation` go into the payload
#     unfiltered (round_web_service.py:1156, 1170), so a team view is handed
#     the enemy's wave phase and formation. #807 closes both, plus the belief
#     expiry that kept time with the enemy clock.
#
# If #807 is NOT in the tag, cut the last two sentences of RELEASE_NOTES and
# say the page is reachable by URL only. Announcing a guarantee the code does
# not keep is worse than announcing less.
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
