-- Forward-only sealed stats mappings, written atomically with canonical import.
-- No backfill. Trusted expected identity provisioning remains caller-owned.
CREATE TABLE IF NOT EXISTS runtime_round_mappings (
    source_key TEXT NOT NULL CHECK (source_key ~ '^[a-z0-9][a-z0-9_.-]{0,63}$'),
    round_key TEXT NOT NULL CHECK (round_key ~ '^[a-f0-9]{32}$'),
    match_key TEXT NOT NULL CHECK (match_key ~ '^[a-f0-9]{32}$'),
    round_number SMALLINT NOT NULL CHECK (round_number IN (1, 2)),
    first_round_key TEXT NOT NULL CHECK (first_round_key ~ '^[a-f0-9]{32}$'),
    generation TEXT NOT NULL CHECK (generation ~ '^[a-f0-9]{32}$'),
    filename TEXT NOT NULL UNIQUE CHECK (length(filename) BETWEEN 1 AND 240),
    source_size BIGINT NOT NULL CHECK (source_size BETWEEN 1 AND 8388608),
    source_sha256 TEXT NOT NULL CHECK (source_sha256 ~ '^[a-f0-9]{64}$'),
    map_name TEXT NOT NULL CHECK (map_name ~ '^[A-Za-z0-9_-]{1,64}$'),
    canonical_round_id INTEGER NOT NULL UNIQUE REFERENCES rounds(id) ON DELETE RESTRICT,
    payload_sha256 TEXT NOT NULL CHECK (payload_sha256 ~ '^[a-f0-9]{64}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_key, round_key),
    UNIQUE (source_key, generation),
    UNIQUE (source_key, match_key, round_number),
    UNIQUE (source_key, match_key, map_name, round_key),
    CHECK ((round_key = first_round_key) = (round_number = 1)),
    FOREIGN KEY (source_key, match_key, map_name, first_round_key)
        REFERENCES runtime_round_mappings(source_key, match_key, map_name, round_key)
        ON DELETE RESTRICT
);
COMMENT ON TABLE runtime_round_mappings IS
    'Explicit sealed stats binding to newly imported canonical rows, not engine authentication or historical repair.';
REVOKE ALL ON runtime_round_mappings FROM PUBLIC;
DO $$
DECLARE
    forbidden TEXT := 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER';
    access_role RECORD;
    role_capability TEXT := CASE WHEN current_setting('server_version_num')::integer >= 160000
                                THEN 'SET' ELSE 'MEMBER' END;
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'website_app') THEN
        REVOKE ALL ON runtime_round_mappings FROM website_app;
        IF current_setting('server_version_num')::integer >= 170000 THEN
            forbidden := forbidden || ',MAINTAIN';
        END IF;
        FOR access_role IN
            SELECT r.oid, r.rolname FROM pg_roles r
            WHERE r.rolname = 'website_app'
                OR pg_has_role('website_app', r.oid, role_capability)
        LOOP
            IF has_table_privilege(access_role.oid, 'runtime_round_mappings', forbidden)
                OR has_any_column_privilege(access_role.oid, 'runtime_round_mappings',
                    'SELECT,INSERT,UPDATE,REFERENCES')
                OR pg_has_role(access_role.oid,
                    (SELECT relowner FROM pg_class
                     WHERE oid = 'runtime_round_mappings'::regclass), 'USAGE')
            THEN
                RAISE EXCEPTION 'website_app retains inherited round mapping access through %',
                    access_role.rolname;
            END IF;
        END LOOP;
    END IF;
END $$;
