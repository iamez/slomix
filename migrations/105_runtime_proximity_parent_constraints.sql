-- Forward-only relational provenance hardening for already-applied 096/100.
-- Preserve those original migration bytes and their recorded checksums.
-- Existing incompatible rows cause refusal; do not infer or rewrite their links.
CREATE UNIQUE INDEX IF NOT EXISTS idx_runtime_round_mapping_parent_binding
    ON runtime_round_mappings(source_key, round_key, canonical_round_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_proximity_receipt_runtime_binding
    ON proximity_processed_files(filename, linked_round_id, file_hash);

ALTER TABLE runtime_proximity_mappings
    ADD CONSTRAINT runtime_proximity_mapping_parent_fkey
    FOREIGN KEY (source_key, round_key, canonical_round_id)
        REFERENCES runtime_round_mappings(source_key, round_key, canonical_round_id) ON DELETE RESTRICT;

ALTER TABLE runtime_proximity_mappings
    ADD CONSTRAINT runtime_proximity_mapping_receipt_fkey
    FOREIGN KEY (filename, canonical_round_id, source_sha256)
        REFERENCES proximity_processed_files(filename, linked_round_id, file_hash) ON DELETE RESTRICT;

ALTER TABLE proximity_processed_files
    ADD CONSTRAINT proximity_receipt_linked_provenance_check
    CHECK (linked_round_id IS NULL OR
        (runtime_parent_gate IS TRUE AND aggregates_applied IS TRUE AND file_hash IS NOT NULL));
