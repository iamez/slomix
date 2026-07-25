-- migrations/065_dedup_revive_weapon_accuracy.sql
-- Give proximity_revive and proximity_weapon_accuracy a real round identity,
-- remove the duplicates re-imports created, and add UNIQUE constraints so it
-- cannot happen again (audit 2026-07-25 S9; owner-approved dedup).
--
-- Root cause: unlike every other proximity table, these two carried no
-- (round_start_unix, round_number) round identity and no natural UNIQUE —
-- only a serial PK — while the parser inserted with a bare `ON CONFLICT DO
-- NOTHING` that had nothing to conflict against. Any reprocessed file
-- silently doubled revive counts and weapon accuracy totals (dev held 230
-- duplicate revive rows and 724 surplus weapon-accuracy rows; some dup pairs
-- even carried two DIFFERENT round_ids because the re-import re-linked, so
-- round_id cannot serve as the identity — round_start_unix, which comes from
-- the file itself, can).
--
-- KNOWN LIMITATION (Codex #549, accepted and measured after backfill):
-- a historically WRONG round_id participates in identity, because the
-- backfill can only copy identity from whatever round the row was linked
-- to. Two rows describing the SAME physical event therefore survive if a
-- re-import linked them to different rounds. This is strictly better than
-- the pre-migration state — where neither row had any identity at all and
-- nothing could be deduped — but it means dedup is not total until the
-- round-relink workstream corrects the underlying links. Measure the
-- residue after any relink run:
--   SELECT COUNT(*) FROM (
--     SELECT map_name, medic_guid, revived_guid, revive_time
--     FROM proximity_revive WHERE round_start_unix IS NOT NULL
--     GROUP BY 1,2,3,4 HAVING COUNT(DISTINCT round_start_unix) > 1) d;
--
-- IDEMPOTENT: ADD COLUMN IF NOT EXISTS, backfill only NULL rows, dedup
-- deletes nothing on a clean table, CREATE UNIQUE INDEX IF NOT EXISTS.
-- (Partial unique indexes keep legacy NULL-identity orphans out of the
-- constraint; PG14-compatible — no NULLS NOT DISTINCT.)

-- 1) Round identity columns (parser writes them from this migration on)
ALTER TABLE proximity_revive
    ADD COLUMN IF NOT EXISTS round_number INTEGER,
    ADD COLUMN IF NOT EXISTS round_start_unix BIGINT;

ALTER TABLE proximity_weapon_accuracy
    ADD COLUMN IF NOT EXISTS round_number INTEGER,
    ADD COLUMN IF NOT EXISTS round_start_unix BIGINT;

-- 2) Backfill identity (and the never-populated session_date) from rounds
--    for rows the linker attributed. Orphans stay NULL and are excluded
--    from the unique constraint below.
--    KNOWN LIMITATION (review on #549, accepted): round_id is the ONLY
--    identity source these historical rows have, and for a wrongly-linked
--    row the copied identity inherits that wrongness — exactly as wrong as
--    the round_id already was, no worse (before this migration the rows
--    were entirely unattributable). Duplicate pairs whose re-import linked
--    to two DIFFERENT rounds therefore keep both rows; repairing those
--    needs an independent attribution source (file fingerprints via
--    proximity_processed_files) — tracked in docs/KNOWN_ISSUES.md.
UPDATE proximity_revive pr
SET round_number = r.round_number,
    round_start_unix = r.round_start_unix,
    session_date = COALESCE(pr.session_date, SUBSTRING(r.round_date, 1, 10)::date)
FROM rounds r
WHERE pr.round_id = r.id
  AND pr.round_start_unix IS NULL
  AND r.round_start_unix IS NOT NULL AND r.round_start_unix > 0;

UPDATE proximity_weapon_accuracy pw
SET round_number = r.round_number,
    round_start_unix = r.round_start_unix,
    session_date = COALESCE(pw.session_date, SUBSTRING(r.round_date, 1, 10)::date)
FROM rounds r
WHERE pw.round_id = r.id
  AND pw.round_start_unix IS NULL
  AND r.round_start_unix IS NOT NULL AND r.round_start_unix > 0;

-- 3) Dedup — keep the OLDEST row (MIN id) of each identity group.
--    With round identity: (round_start_unix, map_name, actors, event key).
--    Orphan rows (no round_start_unix even after backfill): only delete
--    byte-identical content rows — never collapse two legitimately distinct
--    events we cannot tell apart.
DELETE FROM proximity_revive pr
USING proximity_revive keep
WHERE pr.id > keep.id
  AND pr.round_start_unix IS NOT NULL
  AND keep.round_start_unix = pr.round_start_unix
  AND keep.round_number IS NOT DISTINCT FROM pr.round_number
  AND keep.map_name = pr.map_name
  AND keep.medic_guid = pr.medic_guid
  AND keep.revived_guid = pr.revived_guid
  AND keep.revive_time = pr.revive_time;

DELETE FROM proximity_revive pr
USING proximity_revive keep
WHERE pr.id > keep.id
  AND pr.round_start_unix IS NULL AND keep.round_start_unix IS NULL
  -- round_number too: a row can lack a start timestamp yet carry a valid
  -- round number, and two rows from DIFFERENT rounds would otherwise be
  -- collapsed into one.
  AND keep.round_number IS NOT DISTINCT FROM pr.round_number
  AND keep.map_name = pr.map_name
  AND keep.medic_guid = pr.medic_guid
  AND keep.revived_guid = pr.revived_guid
  AND keep.revive_time = pr.revive_time
  AND keep.session_date IS NOT DISTINCT FROM pr.session_date
  -- byte-identical means EVERY field (review on #549): two rows differing
  -- in position, distance, pressure context, names or link are distinct
  -- telemetry and must both survive
  AND keep.revive_x IS NOT DISTINCT FROM pr.revive_x
  AND keep.revive_y IS NOT DISTINCT FROM pr.revive_y
  AND keep.revive_z IS NOT DISTINCT FROM pr.revive_z
  AND keep.distance_to_enemy IS NOT DISTINCT FROM pr.distance_to_enemy
  AND keep.under_fire IS NOT DISTINCT FROM pr.under_fire
  AND keep.nearest_enemy_guid IS NOT DISTINCT FROM pr.nearest_enemy_guid
  AND keep.medic_name IS NOT DISTINCT FROM pr.medic_name
  AND keep.revived_name IS NOT DISTINCT FROM pr.revived_name
  AND keep.round_id IS NOT DISTINCT FROM pr.round_id;

DELETE FROM proximity_weapon_accuracy pw
USING proximity_weapon_accuracy keep
WHERE pw.id > keep.id
  AND pw.round_start_unix IS NOT NULL
  AND keep.round_start_unix = pw.round_start_unix
  AND keep.round_number IS NOT DISTINCT FROM pw.round_number
  AND keep.map_name = pw.map_name
  AND keep.player_guid = pw.player_guid
  AND keep.weapon_id = pw.weapon_id;

DELETE FROM proximity_weapon_accuracy pw
USING proximity_weapon_accuracy keep
WHERE pw.id > keep.id
  AND pw.round_start_unix IS NULL AND keep.round_start_unix IS NULL
  AND keep.round_number IS NOT DISTINCT FROM pw.round_number
  AND keep.map_name = pw.map_name
  AND keep.player_guid = pw.player_guid
  AND keep.weapon_id = pw.weapon_id
  AND keep.shots_fired = pw.shots_fired
  AND keep.hits = pw.hits
  AND keep.kills IS NOT DISTINCT FROM pw.kills
  AND keep.headshots IS NOT DISTINCT FROM pw.headshots
  AND keep.accuracy_pct IS NOT DISTINCT FROM pw.accuracy_pct
  AND keep.team IS NOT DISTINCT FROM pw.team
  AND keep.player_name IS NOT DISTINCT FROM pw.player_name
  AND keep.round_id IS NOT DISTINCT FROM pw.round_id
  AND keep.session_date IS NOT DISTINCT FROM pw.session_date;

-- 4) UNIQUE identity for every row that HAS a full round identity — the
--    parser's ON CONFLICT now has a real target (see parser.py change in
--    the same PR). round_number is part of the canonical round key
--    (review on #549): stale telemetry CAN hand two rounds of one map the
--    same start timestamp, and without round_number in the key their rows
--    would dedupe/conflict across genuinely distinct rounds.
--    (DROP first: an earlier revision of this migration created the index
--    without round_number — idempotent either way.)
DROP INDEX IF EXISTS uq_prox_revive_identity;
CREATE UNIQUE INDEX IF NOT EXISTS uq_prox_revive_identity
    ON proximity_revive (round_start_unix, round_number, map_name, medic_guid, revived_guid, revive_time)
    WHERE round_start_unix IS NOT NULL AND round_number IS NOT NULL;

DROP INDEX IF EXISTS uq_prox_wacc_identity;
CREATE UNIQUE INDEX IF NOT EXISTS uq_prox_wacc_identity
    ON proximity_weapon_accuracy (round_start_unix, round_number, map_name, player_guid, weapon_id)
    WHERE round_start_unix IS NOT NULL AND round_number IS NOT NULL;
