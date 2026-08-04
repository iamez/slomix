-- proximity_shot_fired joins the relinker's discovery legs, so it needs the
-- same partial index the other 24 detection tables got in migrations 014 and
-- 068. Without it the five-minute cron full-scans the largest proximity table
-- (775k rows on dev) twice per cycle -- once for the round_id IS NULL leg and
-- once for the mismatch join.
--
-- The table was created by migration 055, after 014, and was absent from the
-- relinker inventory entirely until now, so 068 had no reason to cover it.
--
-- Column order matches 068 exactly (map_name, round_number, round_start_unix,
-- session_date): the detection leg selects all four and the primary relink
-- template filters on all four.
--
-- Deliberately transactional: the migration runner rejects live CONCURRENTLY
-- statements. Production applies this while services are stopped through
-- deploy_release.sh. IF NOT EXISTS makes retries safe.

CREATE INDEX IF NOT EXISTS idx_proximity_shot_fired_round_lookup_unlinked
    ON proximity_shot_fired (map_name, round_number, round_start_unix, session_date)
    WHERE round_id IS NULL;

-- The mismatch leg reads round_id IS NOT NULL rows and joins rounds on
-- round_id, so it cannot use the partial index above. 068 left this shape out
-- because its mismatch legs run over much smaller tables; at 775k rows the
-- join source needs its own access path.
--
-- Leading on round_start_unix, not round_id: the leg's selective predicate is
-- the six-hour recency cutoff (round_start_unix >= $1), not the join key. An
-- index led by round_id would still have to read every linked row once most
-- of them are older than the cutoff, which on this table is nearly all of them
-- (Codex review on #599). round_id rides along so the join stays index-only.
CREATE INDEX IF NOT EXISTS idx_proximity_shot_fired_mismatch_recent
    ON proximity_shot_fired (round_start_unix, round_id)
    WHERE round_id IS NOT NULL;
