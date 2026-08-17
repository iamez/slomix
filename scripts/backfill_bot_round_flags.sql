-- backfill_bot_round_flags.sql — flag historical bot-dominated rounds.
--
-- The importer has flagged bot rounds (is_bot_round = TRUE, is_valid = FALSE)
-- since bot/community_stats_parser.is_bot_dominated_round landed, but rounds
-- imported before that carry no flags and leaked into every surface without
-- its own identity filter — on 2026-08-17 they accounted for most of the
-- data-plausibility audit's live findings (headshot_kills > kills, dpm
-- inconsistencies, times_revived > deaths: all OMNIBOT rows from test
-- sessions in Mar-Aug 2026).
--
-- Selection replicates is_bot_dominated_round exactly: a round is a bot round
-- when bots are the only players OR the strict majority. Bot identity =
-- '[BOT]' name prefix or 'OMNIBOT' guid prefix (the same defence-in-depth
-- pair every consumer gate uses). Verified on dev 2026-08-18: 113 rounds in
-- 13 sessions + one NULL-gsid group, all pure test sessions — the one mixed
-- evening (gsid 116, 2026-05-19) has exactly its 6 bot warm-up rounds
-- matched and its 20 human rounds untouched, and the human session 144
-- (2026-08-11) is correctly NOT matched (its box roster mixup made it LOOK
-- like a bot session, but its player rows are human).
--
-- Idempotent: re-running matches only rounds still missing a flag.
BEGIN;

WITH per_round AS (
    SELECT r.id,
           COUNT(*) FILTER (WHERE p.player_name LIKE '[BOT]%'
                               OR p.player_guid LIKE 'OMNIBOT%') AS bots,
           COUNT(*) FILTER (WHERE p.player_name NOT LIKE '[BOT]%'
                              AND (p.player_guid IS NULL
                                   OR p.player_guid NOT LIKE 'OMNIBOT%')) AS humans
    FROM rounds r
    JOIN player_comprehensive_stats p ON p.round_id = r.id
    WHERE r.round_number IN (1, 2)
    GROUP BY r.id
)
UPDATE rounds r
SET is_bot_round = TRUE,
    is_valid = FALSE
FROM per_round pr
WHERE r.id = pr.id
  AND pr.bots > 0
  AND (pr.humans = 0 OR pr.bots > pr.humans)
  AND (COALESCE(r.is_bot_round, FALSE) = FALSE OR r.is_valid IS DISTINCT FROM FALSE);

COMMIT;
