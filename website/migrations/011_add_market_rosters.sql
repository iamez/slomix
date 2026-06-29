-- Bind a parimutuel market to the actual team rosters.
--
-- Before this, settle_market auto-resolved the winner positionally
-- (session_results.winning_team 1 -> team_a, 2 -> team_b), which pays the WRONG
-- side whenever the market's team_a/team_b labels don't line up with the
-- session's team_1/team_2 ordering. Storing the rosters lets settle resolve the
-- winning side by roster overlap instead of a positional assumption.
--
-- Columns hold a JSON array (or comma list) of player GUIDs, matching how the
-- code serializes them. Backward compatible: NULL means "no roster bound" and
-- settle falls back to the legacy positional mapping.
ALTER TABLE parimutuel_markets ADD COLUMN IF NOT EXISTS team_a_guids text;
ALTER TABLE parimutuel_markets ADD COLUMN IF NOT EXISTS team_b_guids text;
