-- Canonical and strict proximity linkage normalize map identity at lookup.
-- Keep all three equality predicates indexable; the raw-map index remains
-- available for other callers. Non-unique intentionally: duplicate identities
-- must still be detected and deferred, not hidden or repaired by this migration.
CREATE INDEX IF NOT EXISTS idx_rounds_normalized_map_round_start
    ON rounds (LOWER(BTRIM(map_name)), round_number, round_start_unix);
