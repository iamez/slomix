-- Raw-artifact provenance for timing-only retention, not whole-file import or ACK.
CREATE UNIQUE INDEX IF NOT EXISTS idx_lua_correction_inputs_id_source
    ON lua_correction_inputs(id, source_key);
CREATE TABLE IF NOT EXISTS runtime_gametime_sources (
    source_key TEXT NOT NULL CHECK (source_key ~ '^[a-z0-9][a-z0-9_.-]{0,63}$'),
    generation TEXT NOT NULL CHECK (generation ~ '^[a-f0-9]{32}$'),
    filename TEXT NOT NULL CHECK (
        filename ~ '^gametime-[A-Za-z0-9_-]{1,128}-R[12]-[0-9]{1,19}[.]json$'),
    source_size INTEGER NOT NULL CHECK (source_size BETWEEN 1 AND 1048576),
    source_sha256 TEXT NOT NULL CHECK (source_sha256 ~ '^[a-f0-9]{64}$'),
    input_id BIGINT NOT NULL,
    retained_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_key, generation),
    FOREIGN KEY (input_id, source_key)
        REFERENCES lua_correction_inputs(id, source_key) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_runtime_gametime_sources_input
    ON runtime_gametime_sources(input_id);
COMMENT ON TABLE runtime_gametime_sources IS
    'Timing-only source provenance. No whole-file completion, producer authentication or canonical round linkage.';

-- Do not inherit broad website defaults for a new runtime table.
REVOKE ALL ON runtime_gametime_sources FROM PUBLIC;
DO $$
DECLARE
    forbidden TEXT := 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER';
    access_role RECORD;
    role_capability TEXT := CASE WHEN current_setting('server_version_num')::integer >= 160000
                                THEN 'SET' ELSE 'MEMBER' END;
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'website_app') THEN
        REVOKE ALL ON runtime_gametime_sources FROM website_app;
        IF current_setting('server_version_num')::integer >= 170000 THEN
            forbidden := forbidden || ',MAINTAIN';
        END IF;
        -- NOINHERIT does not prevent SET ROLE; ownership can restore revoked ACLs.
        FOR access_role IN
            SELECT r.oid, r.rolname FROM pg_roles r
            WHERE r.rolname = 'website_app'
                OR pg_has_role('website_app', r.oid, role_capability)
        LOOP
            IF has_table_privilege(access_role.oid, 'runtime_gametime_sources', forbidden)
                OR has_any_column_privilege(access_role.oid, 'runtime_gametime_sources',
                    'SELECT,INSERT,UPDATE,REFERENCES')
                OR pg_has_role(access_role.oid,
                    (SELECT relowner FROM pg_class
                     WHERE oid = 'runtime_gametime_sources'::regclass), 'USAGE')
            THEN
                RAISE EXCEPTION 'website_app retains inherited gametime source access through %',
                    access_role.rolname;
            END IF;
        END LOOP;
    END IF;
END $$;
