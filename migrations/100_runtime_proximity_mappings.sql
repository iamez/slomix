-- Forward-only admitted proximity provenance, atomic with children and receipt.
-- No backfill or legacy receipt adoption. Trusted admission remains caller-owned.
CREATE TABLE IF NOT EXISTS runtime_proximity_mappings (
    filename TEXT PRIMARY KEY REFERENCES proximity_processed_files(filename) ON DELETE RESTRICT
        CHECK (length(filename) BETWEEN 1 AND 240),
    source_key TEXT NOT NULL CHECK (source_key ~ '^[a-z0-9][a-z0-9_.-]{0,63}$'),
    generation TEXT NOT NULL CHECK (generation ~ '^[a-f0-9]{32}$'),
    round_key TEXT NOT NULL CHECK (round_key ~ '^[a-f0-9]{32}$'),
    source_size BIGINT NOT NULL CHECK (source_size BETWEEN 1 AND 8388608),
    source_sha256 TEXT NOT NULL CHECK (source_sha256 ~ '^[a-f0-9]{64}$'),
    session_date DATE NOT NULL,
    canonical_round_id INTEGER NOT NULL UNIQUE REFERENCES rounds(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_key, generation),
    FOREIGN KEY (source_key, round_key)
        REFERENCES runtime_round_mappings(source_key, round_key) ON DELETE RESTRICT
);
COMMENT ON TABLE runtime_proximity_mappings IS
    'Explicit admitted proximity binding, not engine authentication, historical adoption or source acknowledgement.';
REVOKE ALL ON runtime_proximity_mappings FROM PUBLIC;
DO $$
DECLARE
    forbidden TEXT := 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER';
    access_role RECORD;
    role_capability TEXT := CASE WHEN current_setting('server_version_num')::integer >= 160000
                                THEN 'SET' ELSE 'MEMBER' END;
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'website_app') THEN
        REVOKE ALL ON runtime_proximity_mappings FROM website_app;
        IF current_setting('server_version_num')::integer >= 170000 THEN
            forbidden := forbidden || ',MAINTAIN';
        END IF;
        FOR access_role IN
            SELECT r.oid, r.rolname FROM pg_roles r
            WHERE r.rolname = 'website_app'
                OR pg_has_role('website_app', r.oid, role_capability)
        LOOP
            IF has_table_privilege(access_role.oid, 'runtime_proximity_mappings', forbidden)
                OR has_any_column_privilege(access_role.oid, 'runtime_proximity_mappings',
                    'SELECT,INSERT,UPDATE,REFERENCES')
                OR pg_has_role(access_role.oid,
                    (SELECT relowner FROM pg_class
                     WHERE oid = 'runtime_proximity_mappings'::regclass), 'USAGE')
            THEN
                RAISE EXCEPTION 'website_app retains inherited proximity mapping access through %',
                    access_role.rolname;
            END IF;
        END LOOP;
    END IF;
END $$;
