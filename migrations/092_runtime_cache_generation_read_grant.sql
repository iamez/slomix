-- Read-only HTTP generation access; receipts and journal remain private.
-- Role provisioning precedes migrations. Role-less bootstrap/CI stays valid.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'website_app') THEN
        GRANT SELECT ON runtime_cache_generations TO website_app;
    END IF;
END $$;
