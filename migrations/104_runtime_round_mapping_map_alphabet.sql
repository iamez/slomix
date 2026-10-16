-- Forward-only map alphabet alignment with the sealed stats transport.
-- Do not rewrite migration 099 or its recorded checksum on existing targets.
BEGIN;
ALTER TABLE runtime_round_mappings
    DROP CONSTRAINT runtime_round_mappings_map_name_check;
ALTER TABLE runtime_round_mappings
    ADD CONSTRAINT runtime_round_mappings_map_name_check
    CHECK (map_name ~ '^[A-Za-z0-9_.+-]{1,64}$');
COMMIT;
