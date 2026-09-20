-- R02d1: atomic post-import Lua correction, not import or delivery completion.
ALTER TABLE runtime_events DROP CONSTRAINT IF EXISTS runtime_events_event_type_check;
ALTER TABLE runtime_events ADD CONSTRAINT runtime_events_event_type_check
    CHECK (event_type IN ('round_stats_imported', 'round_timing_reconciled', 'round_status_changed', 'round_endstats_changed', 'round_lua_corrected'));
ALTER TABLE runtime_events DROP CONSTRAINT IF EXISTS runtime_events_details_check;
ALTER TABLE runtime_events ADD CONSTRAINT runtime_events_details_check CHECK (
    (event_type = 'round_stats_imported' AND source_filename IS NOT NULL
        AND validation_passed IS NOT NULL AND event_details IS NULL)
    OR (event_type IN ('round_timing_reconciled', 'round_status_changed', 'round_endstats_changed', 'round_lua_corrected')
        AND event_details IS NOT NULL AND jsonb_typeof(event_details) = 'object')
);
