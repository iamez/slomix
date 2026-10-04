-- Existing default ACLs may have granted website_app write access when the
-- runtime tables were created. GRANT SELECT alone never removes those grants.
-- Restrict only these runtime objects; preserve legacy ACLs and default ACLs.
-- Role-less bootstrap remains valid. Run as the runtime table/sequence owner.
DO $$
DECLARE
    sequence_name TEXT;
    sequence_names TEXT[] := ARRAY[]::TEXT[];
    table_name TEXT;
    forbidden_privileges TEXT;
    forbidden_columns TEXT;
    access_role RECORD;
    server_version INTEGER := current_setting('server_version_num')::INTEGER;
    -- PG16 separates SET capability from membership; PG14/15 MEMBER implies SET.
    role_capability TEXT := CASE WHEN current_setting('server_version_num')::INTEGER >= 160000
                                THEN 'SET' ELSE 'MEMBER' END;
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'website_app') THEN
        REVOKE ALL PRIVILEGES ON TABLE
            runtime_events, lua_correction_inputs, lua_correction_receipts,
            lua_correction_attempts, runtime_consumer_receipts,
            runtime_cache_generations FROM website_app;

        -- Resolve owned serial/identity sequences, not assumed sequence names.
        FOR sequence_name IN
            SELECT DISTINCT pg_get_serial_sequence(a.attrelid::regclass::text, a.attname)
            FROM pg_attribute AS a
            WHERE a.attrelid IN (
                'runtime_events'::regclass, 'lua_correction_inputs'::regclass,
                'lua_correction_receipts'::regclass, 'lua_correction_attempts'::regclass,
                'runtime_consumer_receipts'::regclass, 'runtime_cache_generations'::regclass
            ) AND a.attnum > 0 AND NOT a.attisdropped
        LOOP
            IF sequence_name IS NOT NULL THEN
                EXECUTE format('REVOKE ALL PRIVILEGES ON SEQUENCE %s FROM website_app', sequence_name);
                sequence_names := array_append(sequence_names, sequence_name);
            END IF;
        END LOOP;

        GRANT SELECT ON runtime_cache_generations TO website_app;
        -- Inspect both immediately effective permissions and every transitively
        -- SET-able role. NOINHERIT is not a boundary against SET ROLE.
        -- PUBLIC/inherited/column grants are not revoked from unrelated roles:
        -- fail closed instead of recording a falsely successful repair.
        FOR access_role IN
            SELECT r.oid, r.rolname FROM pg_roles AS r
            WHERE r.rolname = 'website_app'
                OR pg_has_role('website_app', r.oid, role_capability)
        LOOP
            FOREACH sequence_name IN ARRAY sequence_names LOOP
                IF has_sequence_privilege(access_role.oid, sequence_name, 'SELECT,UPDATE,USAGE')
                    OR pg_has_role(access_role.oid,
                        (SELECT relowner FROM pg_class WHERE oid = sequence_name::regclass), 'USAGE')
                THEN
                    RAISE EXCEPTION 'website_app retains runtime sequence privileges on % through %',
                        sequence_name, access_role.rolname;
                END IF;
            END LOOP;
            FOREACH table_name IN ARRAY ARRAY[
                'runtime_events', 'lua_correction_inputs', 'lua_correction_receipts',
                'lua_correction_attempts', 'runtime_consumer_receipts', 'runtime_cache_generations'
            ] LOOP
                forbidden_privileges := 'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER';
                forbidden_columns := 'INSERT,UPDATE,REFERENCES';
                IF server_version >= 170000 THEN
                    forbidden_privileges := forbidden_privileges || ',MAINTAIN';
                END IF;
                IF table_name <> 'runtime_cache_generations' THEN
                    forbidden_privileges := forbidden_privileges || ',SELECT';
                    forbidden_columns := forbidden_columns || ',SELECT';
                END IF;
                IF has_table_privilege(access_role.oid, table_name, forbidden_privileges)
                    OR has_any_column_privilege(access_role.oid, table_name, forbidden_columns)
                    OR pg_has_role(access_role.oid,
                        (SELECT relowner FROM pg_class WHERE oid = table_name::regclass), 'USAGE')
                THEN
                    RAISE EXCEPTION 'website_app retains runtime table privileges on % through %',
                        table_name, access_role.rolname;
                END IF;
            END LOOP;
        END LOOP;
        IF NOT has_table_privilege('website_app', 'runtime_cache_generations', 'SELECT') THEN
            RAISE EXCEPTION 'website_app lacks runtime generation read privilege';
        END IF;
    END IF;
END $$;
