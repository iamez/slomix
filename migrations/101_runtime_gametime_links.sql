-- Forward-only durable declared timing links, not timing application receipts.
-- No backfill; one authoritative artifact per canonical round, never overwrite.
CREATE TABLE IF NOT EXISTS runtime_gametime_links (
    source_key TEXT NOT NULL CHECK (source_key ~ '^[a-z0-9][a-z0-9_.-]{0,63}$'),
    generation TEXT NOT NULL CHECK (generation ~ '^[a-f0-9]{32}$'),
    round_key TEXT NOT NULL CHECK (round_key ~ '^[a-f0-9]{32}$'),
    canonical_round_id INTEGER NOT NULL UNIQUE REFERENCES rounds(id) ON DELETE RESTRICT,
    input_id BIGINT NOT NULL,
    filename TEXT NOT NULL CHECK (
        filename ~ '^gametime-[A-Za-z0-9_-]{1,128}-R[12]-[0-9]{1,19}[.]json$'),
    source_size INTEGER NOT NULL CHECK (source_size BETWEEN 1 AND 1048576),
    source_sha256 TEXT NOT NULL CHECK (source_sha256 ~ '^[a-f0-9]{64}$'),
    projection_sha256 TEXT NOT NULL CHECK (projection_sha256 ~ '^[a-f0-9]{64}$'),
    linked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_key, generation),
    FOREIGN KEY (source_key, generation)
        REFERENCES runtime_gametime_identities(source_key, generation) ON DELETE RESTRICT,
    FOREIGN KEY (source_key, round_key)
        REFERENCES runtime_round_mappings(source_key, round_key) ON DELETE RESTRICT,
    FOREIGN KEY (input_id, source_key)
        REFERENCES lua_correction_inputs(id, source_key) ON DELETE RESTRICT
);
COMMENT ON TABLE runtime_gametime_links IS
    'Declared artifact canonical linkage only. No timing application, correction completion, engine authentication or source acknowledgement.';
REVOKE ALL ON runtime_gametime_links FROM PUBLIC;
DO $$
DECLARE
    forbidden TEXT := 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER';
    access_role RECORD;
    role_capability TEXT := CASE WHEN current_setting('server_version_num')::integer >= 160000
                                THEN 'SET' ELSE 'MEMBER' END;
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'website_app') THEN
        REVOKE ALL ON runtime_gametime_links FROM website_app;
        IF current_setting('server_version_num')::integer >= 170000 THEN
            forbidden := forbidden || ',MAINTAIN';
        END IF;
        FOR access_role IN
            SELECT r.oid, r.rolname FROM pg_roles r
            WHERE r.rolname = 'website_app'
                OR pg_has_role('website_app', r.oid, role_capability)
        LOOP
            IF has_table_privilege(access_role.oid, 'runtime_gametime_links', forbidden)
                OR has_any_column_privilege(access_role.oid, 'runtime_gametime_links',
                    'SELECT,INSERT,UPDATE,REFERENCES')
                OR pg_has_role(access_role.oid,
                    (SELECT relowner FROM pg_class
                     WHERE oid = 'runtime_gametime_links'::regclass), 'USAGE')
            THEN
                RAISE EXCEPTION 'website_app retains inherited gametime link access through %',
                    access_role.rolname;
            END IF;
        END LOOP;
    END IF;
END $$;
