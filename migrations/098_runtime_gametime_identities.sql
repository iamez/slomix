-- Declared identity from a sealed timing artifact; NOT a canonical round link.
-- Legacy rows remain unassigned. Multiple artifacts may declare the same half.
CREATE TABLE IF NOT EXISTS runtime_gametime_identities (
    source_key TEXT NOT NULL,
    generation TEXT NOT NULL,
    match_id TEXT NOT NULL CHECK (match_id ~ '^[a-f0-9]{32}$'),
    round_id TEXT NOT NULL CHECK (round_id ~ '^[a-f0-9]{32}$'),
    round_number SMALLINT NOT NULL CHECK (round_number IN (1, 2)),
    first_round_id TEXT NOT NULL CHECK (first_round_id ~ '^[a-f0-9]{32}$'),
    retained_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_key, generation),
    FOREIGN KEY (source_key, generation)
        REFERENCES runtime_gametime_sources(source_key, generation) ON DELETE RESTRICT,
    CHECK ((round_id = first_round_id) = (round_number = 1))
);
COMMENT ON TABLE runtime_gametime_identities IS
    'Sealed artifact declarations only. Not authenticated physical identity, canonical linkage or timing repair.';
REVOKE ALL ON runtime_gametime_identities FROM PUBLIC;
DO $$
DECLARE
    forbidden TEXT := 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER';
    access_role RECORD;
    role_capability TEXT := CASE WHEN current_setting('server_version_num')::integer >= 160000
                                THEN 'SET' ELSE 'MEMBER' END;
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'website_app') THEN
        REVOKE ALL ON runtime_gametime_identities FROM website_app;
        IF current_setting('server_version_num')::integer >= 170000 THEN
            forbidden := forbidden || ',MAINTAIN';
        END IF;
        FOR access_role IN
            SELECT r.oid, r.rolname FROM pg_roles r
            WHERE r.rolname = 'website_app'
                OR pg_has_role('website_app', r.oid, role_capability)
        LOOP
            IF has_table_privilege(access_role.oid, 'runtime_gametime_identities', forbidden)
                OR has_any_column_privilege(access_role.oid, 'runtime_gametime_identities',
                    'SELECT,INSERT,UPDATE,REFERENCES')
                OR pg_has_role(access_role.oid,
                    (SELECT relowner FROM pg_class
                     WHERE oid = 'runtime_gametime_identities'::regclass), 'USAGE')
            THEN
                RAISE EXCEPTION 'website_app retains inherited gametime identity access through %',
                    access_role.rolname;
            END IF;
        END LOOP;
    END IF;
END $$;
