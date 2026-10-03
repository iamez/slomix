-- Existing default ACLs may have granted website_app write access when the
-- runtime tables were created. GRANT SELECT alone never removes those grants.
-- Restrict only these runtime objects; preserve legacy ACLs and default ACLs.
-- Role-less bootstrap remains valid. Run as the runtime table/sequence owner.
DO $$
DECLARE
    sequence_name TEXT;
    table_name TEXT;
    forbidden_privileges TEXT;
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
                IF has_sequence_privilege('website_app', sequence_name, 'SELECT,UPDATE,USAGE') THEN
                    RAISE EXCEPTION 'website_app retains runtime sequence privileges on %', sequence_name;
                END IF;
            END IF;
        END LOOP;

        GRANT SELECT ON runtime_cache_generations TO website_app;
        -- PUBLIC/inherited grants or a wrong migration role must not silently
        -- record a successful repair. Do not revoke unrelated role privileges.
        FOREACH table_name IN ARRAY ARRAY[
            'runtime_events', 'lua_correction_inputs', 'lua_correction_receipts',
            'lua_correction_attempts', 'runtime_consumer_receipts', 'runtime_cache_generations'
        ] LOOP
            forbidden_privileges := 'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER';
            IF table_name <> 'runtime_cache_generations' THEN
                forbidden_privileges := forbidden_privileges || ',SELECT';
            END IF;
            IF has_table_privilege('website_app', table_name, forbidden_privileges) THEN
                RAISE EXCEPTION 'website_app retains runtime table privileges on %', table_name;
            END IF;
        END LOOP;
    END IF;
END $$;
