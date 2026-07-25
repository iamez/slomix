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
  AND keep.map_name = pr.map_name
  AND keep.medic_guid = pr.medic_guid
  AND keep.revived_guid = pr.revived_guid
  AND keep.revive_time = pr.revive_time;

DELETE FROM proximity_revive pr
USING proximity_revive keep
WHERE pr.id > keep.id
  AND pr.round_start_unix IS NULL AND keep.round_start_unix IS NULL
  AND keep.map_name = pr.map_name
  AND keep.medic_guid = pr.medic_guid
  AND keep.revived_guid = pr.revived_guid
  AND keep.revive_time = pr.revive_time
  AND keep.session_date IS NOT DISTINCT FROM pr.session_date;

DELETE FROM proximity_weapon_accuracy pw
USING proximity_weapon_accuracy keep
WHERE pw.id > keep.id
  AND pw.round_start_unix IS NOT NULL
  AND keep.round_start_unix = pw.round_start_unix
  AND keep.map_name = pw.map_name
  AND keep.player_guid = pw.player_guid
  AND keep.weapon_id = pw.weapon_id;

DELETE FROM proximity_weapon_accuracy pw
USING proximity_weapon_accuracy keep
WHERE pw.id > keep.id
  AND pw.round_start_unix IS NULL AND keep.round_start_unix IS NULL
  AND keep.map_name = pw.map_name
  AND keep.player_guid = pw.player_guid
  AND keep.weapon_id = pw.weapon_id
  AND keep.shots_fired = pw.shots_fired
  AND keep.hits = pw.hits
  AND keep.kills IS NOT DISTINCT FROM pw.kills
  AND keep.headshots IS NOT DISTINCT FROM pw.headshots
  AND keep.session_date IS NOT DISTINCT FROM pw.session_date;

-- 4) UNIQUE identity for every row that HAS a round identity — the parser's
--    ON CONFLICT now has a real target (see parser.py change in the same PR).
CREATE UNIQUE INDEX IF NOT EXISTS uq_prox_revive_identity
    ON proximity_revive (round_start_unix, map_name, medic_guid, revived_guid, revive_time)
    WHERE round_start_unix IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_prox_wacc_identity
    ON proximity_weapon_accuracy (round_start_unix, map_name, player_guid, weapon_id)
    WHERE round_start_unix IS NOT NULL;
