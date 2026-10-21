-- Forward-only strict import lineage. Never infer links for existing receipts.
-- RESTRICT preserves evidence: deleting a linked round requires an explicit
-- reconciliation decision, not silently erasing the receipt or its parent link.
ALTER TABLE proximity_processed_files
    ADD COLUMN IF NOT EXISTS linked_round_id INTEGER
        REFERENCES rounds(id) ON DELETE RESTRICT
        CHECK (linked_round_id IS NULL OR
            (runtime_parent_gate IS TRUE AND aggregates_applied IS TRUE AND file_hash IS NOT NULL));

CREATE INDEX IF NOT EXISTS idx_proximity_receipt_linked_round
    ON proximity_processed_files(linked_round_id) WHERE linked_round_id IS NOT NULL;

COMMENT ON COLUMN proximity_processed_files.linked_round_id IS
    'Strict physical-start parent verified in the import transaction; NULL means unproven. No historical adoption.';
