-- 077: cache the true-aim lifetime summary per player.
--
-- WHY
-- The aim section of /api/players/{guid}/profile is the most expensive thing the
-- website computes: five trigonometric aggregates, a LAG window partitioned by
-- round, and two percentile_cont sorts over a player's entire shot history.
-- Measured on the heaviest player (103,258 rows in proximity_shot_fired):
-- 2,770 ms warm, 16,887 ms on a cold cache — while the twelve other profile
-- sections together cost ~500 ms. The data is lifetime and only changes when
-- rounds import, so recomputing it per request is the actual waste. PR #744
-- stopped the page WAITING for it; this stops it being recomputed at all.
--
-- A covering index does not help and was tried and dropped: guid_canonical =
-- selects 12.8 % of the table, so the planner takes a bitmap heap scan anyway.
--
-- FRESHNESS, without an invalidation policy to get wrong
-- The row carries a fingerprint of exactly the inputs the summary is derived
-- from, taken in one indexed aggregate (~45 ms warm):
--   shot_count      new or deleted shots
--   last_event_time new shots, even in the pathological equal-count case
--   round_id_sum    re-linking, which changes the flick index because that
--                   window is partitioned by round even when no shot moved
-- A read compares the stored fingerprint with a fresh one; anything different
-- means recompute. There is no TTL to tune and no import hook to forget.
--
-- formula_version is bumped in code whenever the computation changes, so a
-- change in the maths invalidates every cached row without a migration.
--
-- OWNERSHIP NOTE: created by etlegacy_user (same as proximity_shot_fired), but
-- the WEB process writes it, and website/.env connects as website_app — hence
-- the explicit grants. Apply with POSTGRES_USER=etlegacy_user.

CREATE TABLE IF NOT EXISTS player_aim_summary (
    guid_canonical   TEXT PRIMARY KEY,
    formula_version  INTEGER     NOT NULL,
    shot_count       BIGINT      NOT NULL,
    last_event_time  BIGINT      NULL,
    round_id_sum     NUMERIC     NULL,
    payload          JSONB       NOT NULL,
    computed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE player_aim_summary IS
    'Cached true-aim lifetime summary per player (PR #746). Derived data only: '
    'safe to TRUNCATE, every row rebuilds itself on the next profile read.';
COMMENT ON COLUMN player_aim_summary.round_id_sum IS
    'SUM(round_id) over the player''s shots — part of the freshness fingerprint. '
    'Catches re-linking, which moves shots between rounds and so changes the '
    'flick index without changing shot_count or last_event_time.';
COMMENT ON COLUMN player_aim_summary.formula_version IS
    'Bumped in code (_AIM_FORMULA_VERSION) when the computation changes; rows '
    'from an older version are ignored and recomputed.';

-- Grant each role only if it exists, so a fresh CI/test database (which has
-- etlegacy_user but NOT website_app) applies cleanly while dev and prod get the
-- real grants. Same pattern as migration 073.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'website_app') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON player_aim_summary TO website_app;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'etlegacy_user') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON player_aim_summary TO etlegacy_user;
  END IF;
END $$;
