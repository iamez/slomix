-- Seed the first sick-leave (bolniška) link: ownator's post-injury cl_guid.
--
-- The person plays in-game as "ownator" (gathering nick: carniee). After
-- crushing both heels he plays from bed on a laptop, which brought a fresh
-- cl_guid (EF561EAA, first seen 2026-08-11). His pre-injury record lives under
-- FB0EC840. Marking EF561EAA as a 'sick_leave' alt of FB0EC840 attributes the
-- new guid to him (profile / movers badge) WITHOUT merging the off-form stats
-- into his main record — exactly the point of the feature.
--
-- Idempotent (ON CONFLICT on the UNIQUE alt_guid): safe to re-run / replay on
-- any environment. Both guids are shared game data, so this is prod-valid.
-- Owner-requested 2026-08-13 (TOK F). Self-service !bolniska (Phase 2) will let
-- players open their own; this one is seeded because carniee is not Discord-linked.

BEGIN;

INSERT INTO player_identity_links
    (primary_guid, alt_guid, link_type, reason, period_start, notes)
VALUES
    ('FB0EC840', 'EF561EAA', 'sick_leave', 'injury', DATE '2026-08-11',
     'carniee — both heels injured, playing from bed on laptop')
ON CONFLICT (alt_guid) DO NOTHING;

COMMIT;
