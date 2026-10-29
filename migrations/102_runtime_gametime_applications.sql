-- Scoped declared timing application receipts; no legacy adoption or backfill.
CREATE TABLE IF NOT EXISTS runtime_gametime_applications (
    source_key TEXT NOT NULL,
    generation TEXT NOT NULL,
    canonical_round_id INTEGER NOT NULL UNIQUE REFERENCES rounds(id) ON DELETE RESTRICT,
    event_id BIGINT NOT NULL UNIQUE REFERENCES runtime_events(id) ON DELETE RESTRICT,
    link_snapshot JSONB NOT NULL CHECK (jsonb_typeof(link_snapshot) = 'object'),
    before_round JSONB NOT NULL CHECK (
        jsonb_typeof(before_round) = 'object'
        AND before_round ?& ARRAY['actual_duration_seconds','total_pause_seconds','pause_count']
        AND before_round->'actual_duration_seconds' = 'null'::jsonb
        AND before_round->'total_pause_seconds' IN ('null'::jsonb, '0'::jsonb)
        AND before_round->'pause_count' IN ('null'::jsonb, '0'::jsonb)
    ),
    after_values JSONB NOT NULL CHECK (
        jsonb_typeof(after_values) = 'object'
        AND after_values ?& ARRAY['actual_duration_seconds','total_pause_seconds','pause_count']
        AND after_values - ARRAY['actual_duration_seconds','total_pause_seconds','pause_count'] = '{}'::jsonb
        AND jsonb_typeof(after_values->'actual_duration_seconds') = 'number'
        AND jsonb_typeof(after_values->'total_pause_seconds') = 'number'
        AND jsonb_typeof(after_values->'pause_count') = 'number'
        AND (after_values->>'actual_duration_seconds')::bigint BETWEEN 1 AND 2147483647
        AND (after_values->>'total_pause_seconds')::bigint BETWEEN 0 AND 2147483647
        AND (after_values->>'pause_count')::bigint BETWEEN 0 AND 2147483647
    ),
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_key, generation),
    FOREIGN KEY (source_key, generation)
        REFERENCES runtime_gametime_links(source_key, generation) ON DELETE RESTRICT
);
COMMENT ON TABLE runtime_gametime_applications IS
    'Atomic three-field timing fill with preimage and provenance. Not whole-file completion, engine authentication or source acknowledgement.';
REVOKE ALL ON runtime_gametime_applications FROM PUBLIC;
DO $$
DECLARE
    forbidden TEXT := 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER';
    access_role RECORD;
    role_capability TEXT := CASE WHEN current_setting('server_version_num')::integer >= 160000
                                THEN 'SET' ELSE 'MEMBER' END;
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'website_app') THEN
        REVOKE ALL ON runtime_gametime_applications FROM website_app;
        IF current_setting('server_version_num')::integer >= 170000 THEN
            forbidden := forbidden || ',MAINTAIN';
        END IF;
        FOR access_role IN
            SELECT r.oid, r.rolname FROM pg_roles r
            WHERE r.rolname = 'website_app'
                OR pg_has_role('website_app', r.oid, role_capability)
        LOOP
            IF has_table_privilege(access_role.oid, 'runtime_gametime_applications', forbidden)
                OR has_any_column_privilege(access_role.oid, 'runtime_gametime_applications',
                    'SELECT,INSERT,UPDATE,REFERENCES')
                OR pg_has_role(access_role.oid,
                    (SELECT relowner FROM pg_class
                     WHERE oid = 'runtime_gametime_applications'::regclass), 'USAGE')
            THEN
                RAISE EXCEPTION 'website_app retains inherited gametime application access through %',
                    access_role.rolname;
            END IF;
        END LOOP;
    END IF;
END $$;
