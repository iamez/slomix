"""
Match Prediction Engine
=======================
Predicts match outcomes based on:
- Head-to-head history (45% weight)
- Recent form (30% weight)
- Map performance (25% weight)
- Substitution impact (0% — not yet implemented; weight redistributed)

Phase 3: Competitive Analytics
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Bumped whenever the formula or its data gates change — calibration reports
# must never mix versions. v1.1: valid/human round gates + as-of cutoff +
# factor availability metadata (shadow program, audit AUD-006).
MODEL_VERSION = "heuristic-v1.1"


def compute_event_key(
    session_date: str,
    match_format: str,
    team_a_guids: list[str],
    team_b_guids: list[str],
    map_name: str | None = None,
    occurrence: str | None = None,
) -> str:
    """Deterministic dedup key for one prediction event.

    Order-invariant in two ways: guids are sorted within each team, and the
    two teams are sorted against each other — so a repeated voice split (or
    A/B channels swapping) maps to the same key and cannot create a
    duplicate row (unique index idx_predictions_event_key).

    `occurrence` separates legitimate same-evening REMATCHES of the same
    roster/map/format from true repeated detections of one event (Codex review
    on #511). The caller passes an episode-window token (the split time bucketed
    to the prediction cooldown): predictions can only fire once per cooldown
    window per split, so two rematches the cooldown allowed land in different
    windows (distinct keys, both stored), while a re-detection inside the same
    window keeps the same key (deduped). Omitting it preserves the old key.
    """
    team_1 = ",".join(sorted(str(g).upper() for g in team_a_guids))
    team_2 = ",".join(sorted(str(g).upper() for g in team_b_guids))
    rosters = "|".join(sorted([team_1, team_2]))
    raw = f"{session_date}|{match_format}|{map_name or ''}|{rosters}|{occurrence or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()


# Shared factor-query gates (audit AUD-006): only valid, human rounds that
# COMPLETED before the prediction moment may influence a factor. round_date
# is date-only, so the intra-evening cutoff uses the rounds unix timestamps;
# rows without either timestamp fall back to strictly-earlier calendar days.
_VALID_HUMAN_GATE = "r.is_valid = TRUE AND COALESCE(r.is_bot_round, FALSE) = FALSE"


def _completed_before(unix_ph: str, date_ph: str) -> str:
    # Only a real ROUND-END timestamp proves a round finished before the
    # prediction moment. The old fallback to round_start_unix let a round that
    # had merely STARTED before `as_of` (but finished after) leak into the
    # factor snapshot, contaminating historical calibration (Codex #511). A row
    # with no trustworthy end uses a strictly-earlier calendar day instead —
    # conservatively excluding same-day rounds of uncertain completion.
    end = "NULLIF(r.round_end_unix, 0)"
    return (
        f"({end} < {unix_ph} OR ({end} IS NULL AND pcs.round_date < {date_ph}))"
    )


class PredictionEngine:
    """
    Weighted prediction engine for ET:Legacy matches.

    Weights (configurable; Subs redistributed into the other three until
    substitution impact is implemented — see class constants below):
    - H2H_WEIGHT: 0.45 (head-to-head history)
    - FORM_WEIGHT: 0.30 (recent performance)
    - MAP_WEIGHT: 0.25 (map-specific performance)
    - SUB_WEIGHT: 0.00 (substitution impact — not yet implemented)
    """

    # Configurable weights — Subs redistributed until implemented
    H2H_WEIGHT = 0.45
    FORM_WEIGHT = 0.30
    MAP_WEIGHT = 0.25
    SUB_WEIGHT = 0.00

    # Minimum data thresholds
    MIN_H2H_MATCHES = 3  # Need 3+ matches for H2H to count
    MIN_FORM_MATCHES = 5  # Need 5+ recent matches for form

    def __init__(self, db_adapter):
        """
        Initialize prediction engine.

        Args:
            db_adapter: DatabaseAdapter instance for async database queries
        """
        self.db = db_adapter
        logger.info("✅ PredictionEngine initialized")

    async def predict_match(
        self,
        team_a_guids: list[str],
        team_b_guids: list[str],
        map_name: str | None = None,
        as_of: datetime | None = None,
    ) -> dict:
        """
        Generate match prediction with confidence scoring.

        Args:
            team_a_guids: List of player GUIDs for Team A
            team_b_guids: List of player GUIDs for Team B
            map_name: Optional map name for map-specific analysis

        Returns:
            {
                'team_a_win_probability': 0.65,
                'team_b_win_probability': 0.35,
                'confidence': 'high',  # high/medium/low
                'confidence_score': 0.85,
                'factors': {
                    'h2h': {'score': 0.7, 'details': '...', 'matches': 5},
                    'form': {'score': 0.6, 'details': '...'},
                    'map': {'score': 0.5, 'details': '...'},
                    'subs': {'score': 0.5, 'details': '...'}
                },
                'key_insight': 'Team A has won 4 of last 5 head-to-head matches'
            }
        """
        logger.info(f"🔮 Generating prediction: {len(team_a_guids)}v{len(team_b_guids)}")

        # Temporal cutoff: every factor query sees only rounds completed
        # BEFORE this moment, so a later result can never leak into the
        # snapshot (shadow-program requirement).
        as_of = as_of or datetime.now()  # noqa: DTZ005 naive datetime intentional — project convention

        # Analyze each factor
        h2h = await self._analyze_head_to_head(team_a_guids, team_b_guids, as_of)
        form = await self._analyze_recent_form(team_a_guids, team_b_guids, as_of)
        map_perf = await self._analyze_map_performance(team_a_guids, team_b_guids, map_name, as_of)
        subs = await self._analyze_substitution_impact(team_a_guids, team_b_guids)

        # Calculate weighted score
        # Score > 0.5 means Team A favored, < 0.5 means Team B favored
        weighted_score = (
            h2h['score'] * self.H2H_WEIGHT +
            form['score'] * self.FORM_WEIGHT +
            map_perf['score'] * self.MAP_WEIGHT +
            subs['score'] * self.SUB_WEIGHT
        )

        # Convert to win probabilities
        # Apply sigmoid-like scaling to keep probabilities reasonable (30-70% range)
        team_a_prob = 0.3 + (weighted_score * 0.4)  # Maps 0-1 to 0.3-0.7
        team_b_prob = 1.0 - team_a_prob

        # Calculate confidence based on data availability
        confidence_score = self._calculate_confidence(h2h, form, map_perf, subs)
        confidence = self._score_to_confidence_label(confidence_score)

        # Generate key insight
        key_insight = self._generate_key_insight(h2h, form, map_perf, subs)

        logger.info(
            f"📊 Prediction complete: Team A {team_a_prob:.0%} vs Team B {team_b_prob:.0%} "
            f"(Confidence: {confidence})"
        )

        factors = {'h2h': h2h, 'form': form, 'map': map_perf, 'subs': subs}

        # Per-factor coverage: a factor that had no data is recorded as
        # unavailable (its neutral 0.5 is a placeholder, not evidence) so the
        # calibration report can slice eligible vs non-eligible predictions.
        coverage = {
            name: {
                'available': bool(f.get('available', False)),
                'sample_size': int(f.get('sample_size', 0)),
                'window_start': f.get('window_start'),
                'window_end': f.get('window_end'),
            }
            for name, f in factors.items()
        }
        # Eligibility reasons must reflect GENUINE data gaps, not structural
        # ones (Codex P1 #511): a zero-weight factor (subs — unimplemented, so
        # ALWAYS unavailable) and a factor that is not applicable to this
        # prediction (map when no map_name was supplied) would otherwise land in
        # every row, making a "resolved eligible" count meaningless.
        factor_weights = {
            'h2h': self.H2H_WEIGHT, 'form': self.FORM_WEIGHT,
            'map': self.MAP_WEIGHT, 'subs': self.SUB_WEIGHT,
        }
        eligibility_reasons = []
        for name, f in factors.items():
            if factor_weights.get(name, 0) <= 0:
                continue  # unweighted/unimplemented — not an eligibility signal
            if name == 'map' and not map_name:
                continue  # map factor is N/A when no map was specified
            if not f.get('available', False):
                eligibility_reasons.append(f"{name}_unavailable")

        return {
            'team_a_win_probability': round(team_a_prob, 2),
            'team_b_win_probability': round(team_b_prob, 2),
            'confidence': confidence,
            'confidence_score': round(confidence_score, 2),
            'factors': factors,
            'coverage': coverage,
            'eligibility_reasons': eligibility_reasons,
            'model_version': MODEL_VERSION,
            'as_of': as_of.isoformat(),
            'key_insight': key_insight,
            'weighted_score': round(weighted_score, 3)
        }

    async def store_prediction(
        self,
        prediction: dict,
        split_data: dict,
        session_date: str,
        discord_channel_id: int | None = None,
        discord_message_id: int | None = None,
        publish_state: str = "shadow",
        occurrence: str | None = None,
    ) -> int:
        """
        Store prediction in database for accuracy tracking.

        Args:
            prediction: Result from predict_match()
            split_data: Team split data from voice service
            session_date: Date of gaming session (YYYY-MM-DD)
            discord_channel_id: Optional Discord channel where prediction was posted
            discord_message_id: Optional Discord message ID for editing
            publish_state: 'shadow' (stored for calibration only, default) or
                'published' (was actually shown to users)

        Returns:
            prediction_id: Database ID of stored prediction. Idempotent: a
            repeated voice split with the same rosters hits the same
            prediction_event_key and returns the existing row's id.
        """
        try:
            # Extract factor details
            h2h = prediction['factors']['h2h']
            form = prediction['factors']['form']
            map_perf = prediction['factors']['map']
            subs = prediction['factors']['subs']

            # Prepare JSON fields
            team_a_guids_json = json.dumps(split_data['team_a_guids'])
            team_b_guids_json = json.dumps(split_data['team_b_guids'])
            team_a_discord_ids_json = json.dumps([int(id) for id in split_data['team_a_discord_ids']])
            team_b_discord_ids_json = json.dumps([int(id) for id in split_data['team_b_discord_ids']])

            # Prepare details JSON
            h2h_details_json = json.dumps({
                'matches': h2h.get('matches', 0),
                'team_a_wins': h2h.get('team_a_wins', 0),
                'team_b_wins': h2h.get('team_b_wins', 0),
                'details': h2h.get('details', '')
            })

            form_details_json = json.dumps({
                'team_a_form': form.get('team_a_form', '?-?'),
                'team_b_form': form.get('team_b_form', '?-?'),
                'details': form.get('details', '')
            })

            map_details_json = json.dumps({
                'details': map_perf.get('details', '')
            })

            subs_details_json = json.dumps({
                'team_a_subs': subs.get('team_a_subs', 0),
                'team_b_subs': subs.get('team_b_subs', 0),
                'details': subs.get('details', '')
            })

            event_key = compute_event_key(
                session_date,
                split_data['format'],
                split_data['team_a_guids'],
                split_data['team_b_guids'],
                split_data.get('map_name'),
                occurrence,
            )
            feature_snapshot_json = json.dumps(prediction.get('factors', {}), default=str)
            feature_coverage_json = json.dumps(prediction.get('coverage', {}), default=str)
            eligibility_reasons = ",".join(prediction.get('eligibility_reasons', [])) or None

            query = """
                INSERT INTO match_predictions (
                    session_date,
                    map_name,
                    format,
                    team_a_channel_id,
                    team_b_channel_id,
                    team_a_guids,
                    team_b_guids,
                    team_a_discord_ids,
                    team_b_discord_ids,
                    team_a_win_probability,
                    team_b_win_probability,
                    confidence,
                    confidence_score,
                    h2h_score,
                    form_score,
                    map_score,
                    subs_score,
                    weighted_score,
                    key_insight,
                    h2h_details,
                    form_details,
                    map_details,
                    subs_details,
                    discord_channel_id,
                    discord_message_id,
                    guid_coverage,
                    model_version,
                    publish_state,
                    prediction_event_key,
                    feature_snapshot,
                    feature_coverage,
                    eligibility_reasons
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
                    $21, $22, $23, $24, $25, $26, $27, $28, $29, $30::jsonb,
                    $31::jsonb, $32
                )
                ON CONFLICT (prediction_event_key) WHERE prediction_event_key IS NOT NULL
                DO UPDATE SET
                    -- Promote an existing shadow row to published when this
                    -- write publishes it, but never downgrade a published row
                    -- back to shadow (Codex review on #511).
                    publish_state = CASE
                        WHEN EXCLUDED.publish_state = 'published' THEN 'published'
                        ELSE match_predictions.publish_state
                    END,
                    discord_channel_id = COALESCE(EXCLUDED.discord_channel_id, match_predictions.discord_channel_id),
                    discord_message_id = COALESCE(EXCLUDED.discord_message_id, match_predictions.discord_message_id)
                RETURNING id
            """

            params = (
                session_date,
                split_data.get('map_name'),
                split_data['format'],
                split_data['team_a_channel_id'],
                split_data['team_b_channel_id'],
                team_a_guids_json,
                team_b_guids_json,
                team_a_discord_ids_json,
                team_b_discord_ids_json,
                prediction['team_a_win_probability'],
                prediction['team_b_win_probability'],
                prediction['confidence'],
                prediction['confidence_score'],
                h2h['score'],
                form['score'],
                map_perf['score'],
                subs['score'],
                prediction['weighted_score'],
                prediction['key_insight'],
                h2h_details_json,
                form_details_json,
                map_details_json,
                subs_details_json,
                discord_channel_id,
                discord_message_id,
                split_data['guid_coverage'],
                prediction.get('model_version', MODEL_VERSION),
                publish_state,
                event_key,
                feature_snapshot_json,
                feature_coverage_json,
                eligibility_reasons,
            )

            result = await self.db.fetch_one(query, params)
            if result is None:
                # With ON CONFLICT DO UPDATE the row is always returned, so this
                # is only reachable if the write had no event_key (event_key
                # NULL → the partial unique index doesn't apply → plain insert,
                # which still RETURNs) or an adapter quirk. Fall back to a
                # lookup, but guard against a missing row instead of crashing on
                # existing[0] (Copilot review on #511).
                existing = await self.db.fetch_one(
                    "SELECT id FROM match_predictions WHERE prediction_event_key = $1",
                    (event_key,),
                )
                if not existing:
                    raise RuntimeError(
                        "store_prediction: INSERT returned no row and no row "
                        f"matched event_key={event_key!r} — prediction not stored"
                    )
                prediction_id = existing[0]
                logger.info(f"💾 Prediction dedup: event already stored (ID={prediction_id})")
                return prediction_id

            prediction_id = result[0]
            logger.info(f"💾 Prediction stored: ID={prediction_id} ({publish_state})")
            return prediction_id

        except Exception as e:
            logger.error(f"❌ Failed to store prediction: {e}", exc_info=True)
            raise

    async def update_prediction_outcome(
        self,
        prediction_id: int,
        actual_winner: int,
        team_a_score: int,
        team_b_score: int
    ) -> None:
        """
        Update prediction with actual match outcome.

        Args:
            prediction_id: Database ID of prediction
            actual_winner: 1 = Team A won, 2 = Team B won, 0 = draw
            team_a_score: Rounds won by Team A
            team_b_score: Rounds won by Team B
        """
        try:
            # Get original prediction
            query_get = """
                SELECT team_a_win_probability, team_b_win_probability
                FROM match_predictions
                WHERE id = $1
            """
            result = await self.db.fetch_one(query_get, (prediction_id,))

            if not result:
                logger.warning(f"⚠️ Prediction {prediction_id} not found")
                return

            team_a_prob, team_b_prob = result

            # Determine if prediction was correct
            predicted_winner = 1 if team_a_prob > team_b_prob else 2
            if team_a_prob == team_b_prob:
                predicted_winner = 0  # Toss-up

            prediction_correct = (predicted_winner == actual_winner)

            # Raw Brier score = (p - outcome)^2, lower is better. Draws are
            # excluded from binary calibration: brier_score stays NULL and
            # only the legacy accuracy field gets the 0.5 placeholder.
            if actual_winner == 1:
                brier_score = (1.0 - team_a_prob) ** 2
            elif actual_winner == 2:
                brier_score = (1.0 - team_b_prob) ** 2
            else:
                brier_score = None  # Draw/cancelled

            # Legacy display metric (higher is better, 1 = perfect)
            prediction_accuracy = 1.0 - (brier_score if brier_score is not None else 0.5)

            # Update database
            query_update = """
                UPDATE match_predictions
                SET actual_winner = $1,
                    team_a_actual_score = $2,
                    team_b_actual_score = $3,
                    prediction_correct = $4,
                    prediction_accuracy = $5,
                    brier_score = $6,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $7
            """

            await self.db.execute(query_update, (
                actual_winner,
                team_a_score,
                team_b_score,
                prediction_correct,
                prediction_accuracy,
                brier_score,
                prediction_id
            ))

            logger.info(
                f"✅ Prediction {prediction_id} updated: "
                f"{'CORRECT' if prediction_correct else 'WRONG'} "
                f"(Accuracy: {prediction_accuracy:.2%})"
            )

        except Exception as e:
            logger.error(f"❌ Failed to update prediction outcome: {e}", exc_info=True)
            raise

    async def auto_resolve_predictions(self, session_date: str) -> int:
        """Resolve every unresolved prediction of a date against session_results.

        Owner answer B4 phase 2 groundwork: outcomes must accrue WITHOUT the
        manual !update_prediction_outcome step, or calibration data never
        materializes. Roster matching is guid8-overlap based with orientation
        detection (prediction team A may be session_results team 2); the
        session winner follows the BOX canon — MAP wins tallied over the
        date's session_results rows (owner: 2 points per map, draws split).

        Returns the number of predictions resolved.
        """
        try:
            pending = await self.db.fetch_all(
                """SELECT id, team_a_guids, team_b_guids
                   FROM match_predictions
                   WHERE session_date = $1 AND actual_winner IS NULL""",
                (session_date,),
            )
            if not pending:
                return 0

            # Per-session correctness (Codex #511): this resolver aggregates every
            # roster-matching result across the WHOLE date. When the same rosters
            # play multiple gaming sessions that day (a rematch → multiple
            # prediction rows via the episode occurrence key), the combined tally
            # would be assigned to EACH prediction, corrupting calibration. Only
            # auto-resolve dates that map to exactly one gaming session; defer the
            # rest to manual resolution rather than record a wrong outcome.
            session_ids = await self.db.fetch_all(
                "SELECT DISTINCT gaming_session_id FROM rounds "
                "WHERE round_date = $1 AND gaming_session_id IS NOT NULL",
                (session_date,),
            )
            if len(session_ids) > 1:
                logger.warning(
                    "auto_resolve: %s spans %d gaming sessions — deferring to manual "
                    "resolution (whole-date aggregation would mis-resolve rematches)",
                    session_date, len(session_ids),
                )
                return 0

            results = await self.db.fetch_all(
                """SELECT team_1_guids, team_2_guids, winning_team
                   FROM session_results
                   WHERE session_date = $1 AND winning_team IS NOT NULL""",
                (session_date,),
            )
            if not results:
                logger.debug("auto_resolve: no session_results yet for %s", session_date)
                return 0

            def g8set(raw) -> set:
                vals = json.loads(raw) if isinstance(raw, str) else (raw or [])
                return {str(g)[:8].upper() for g in vals if g}

            resolved = 0
            for pred in pending:
                pred_id, a_set, b_set = pred[0], g8set(pred[1]), g8set(pred[2])
                if not a_set or not b_set:
                    continue
                a_wins = b_wins = matched = 0
                for row in results:
                    t1, t2, winner = g8set(row[0]), g8set(row[1]), int(row[2])
                    straight = len(a_set & t1) + len(b_set & t2)
                    flipped = len(a_set & t2) + len(b_set & t1)
                    best = max(straight, flipped)
                    # require a real roster match, not coincidence: at least
                    # half of the prediction's players must be accounted for
                    if best * 2 < len(a_set) + len(b_set):
                        continue
                    matched += 1
                    if winner == 0:
                        a_wins += 0  # draw: no map point either way here;
                        b_wins += 0  # BOX splits 1-1, net zero for A-vs-B
                    elif (winner == 1) == (straight >= flipped):
                        a_wins += 1
                    else:
                        b_wins += 1
                if matched == 0:
                    logger.debug("auto_resolve: prediction %s matched no maps", pred_id)
                    continue
                actual = 1 if a_wins > b_wins else 2 if b_wins > a_wins else 0
                await self.update_prediction_outcome(
                    pred_id, actual, a_wins, b_wins
                )
                resolved += 1

            if resolved and len(session_ids) == 1:
                # Record which gaming session resolved these predictions. Safe:
                # we only get here when the date maps to exactly one session
                # (the >1 case returned early above).
                try:
                    await self.db.execute(
                        "UPDATE match_predictions SET gaming_session_id = $1 "
                        "WHERE session_date = $2 AND actual_winner IS NOT NULL "
                        "AND gaming_session_id IS NULL",
                        (session_ids[0][0], session_date),
                    )
                except Exception as e:
                    logger.debug("gaming_session_id backlink skipped: %s", e)

            if resolved:
                logger.info("✅ auto-resolved %d prediction(s) for %s",
                            resolved, session_date)
            return resolved
        except Exception as e:
            logger.error(f"❌ auto_resolve_predictions failed: {e}", exc_info=True)
            return 0

    async def _analyze_head_to_head(
        self,
        team_a_guids: list[str],
        team_b_guids: list[str],
        as_of: datetime,
    ) -> dict:
        """
        Analyze historical head-to-head matchups between these lineups.

        Returns score: >0.5 = Team A favored, <0.5 = Team B favored.
        Only valid, human rounds completed before `as_of` are visible
        (rounds.is_valid + bot gate + temporal cutoff — audit AUD-006).
        """
        # Find sessions where these teams (or similar) played each other
        # Use overlap percentage to find matches

        query = f"""
            WITH team_sessions AS (
                SELECT DISTINCT
                    DATE(pcs.round_date) as session_date,
                    pcs.player_guid,
                    pcs.team
                FROM player_comprehensive_stats pcs
                JOIN rounds r ON r.id = pcs.round_id
                WHERE pcs.round_number IN (1, 2)
                  AND pcs.round_date > $1
                  AND {_VALID_HUMAN_GATE}
                  AND {_completed_before('$2', '$3')}
            )
            SELECT session_date, team, array_agg(DISTINCT player_guid) as guids
            FROM team_sessions
            GROUP BY session_date, team
            ORDER BY session_date DESC
        """

        # Look back 90 days before the prediction moment
        cutoff = (as_of - timedelta(days=90)).strftime('%Y-%m-%d')
        as_of_unix = int(as_of.timestamp())
        as_of_date = as_of.strftime('%Y-%m-%d')
        window = {'window_start': cutoff, 'window_end': as_of.isoformat()}

        try:
            rows = await self.db.fetch_all(query, (cutoff, as_of_unix, as_of_date))

            use_results_lookup = os.getenv(
                "ENABLE_H2H_RESULTS_LOOKUP", "false"
            ).lower() == "true"
            results_cache: dict[str, dict | None] = {}

            # Find sessions with significant overlap
            # Group by session_date to match teams
            sessions_by_date = {}
            for session_date, team, guids in rows:
                if session_date not in sessions_by_date:
                    sessions_by_date[session_date] = []
                sessions_by_date[session_date].append((team, guids))

            # Calculate overlap for each historical session
            team_a_wins = 0
            team_b_wins = 0
            total_matches = 0

            team_a_set = set(team_a_guids)
            team_b_set = set(team_b_guids)

            for session_date, teams in sessions_by_date.items():
                if len(teams) != 2:
                    continue  # Skip sessions without 2 teams

                team_1_guids, team_2_guids = set(teams[0][1]), set(teams[1][1])

                # Calculate overlap with current teams
                overlap_1a = len(team_1_guids & team_a_set) / max(len(team_a_set), 1)
                overlap_1b = len(team_1_guids & team_b_set) / max(len(team_b_set), 1)
                overlap_2a = len(team_2_guids & team_a_set) / max(len(team_a_set), 1)
                overlap_2b = len(team_2_guids & team_b_set) / max(len(team_b_set), 1)

                # Need >50% overlap to count as same team
                if overlap_1a > 0.5 and overlap_2b > 0.5:
                    # Team 1 = Team A, Team 2 = Team B
                    total_matches += 1
                    if use_results_lookup:
                        winner = await self._get_session_winner_from_results(
                            session_date, team_a_set, team_b_set, results_cache, as_of
                        )
                        if winner == "A":
                            team_a_wins += 1
                        elif winner == "B":
                            team_b_wins += 1
                elif overlap_1b > 0.5 and overlap_2a > 0.5:
                    # Team 1 = Team B, Team 2 = Team A
                    total_matches += 1
                    if use_results_lookup:
                        winner = await self._get_session_winner_from_results(
                            session_date, team_b_set, team_a_set, results_cache, as_of
                        )
                        if winner == "A":
                            team_b_wins += 1
                        elif winner == "B":
                            team_a_wins += 1

            # Not enough H2H data
            if total_matches < self.MIN_H2H_MATCHES:
                return {
                    'score': 0.5,
                    'details': f'Insufficient H2H data ({total_matches} matches)',
                    'matches': total_matches,
                    'team_a_wins': 0,
                    'team_b_wins': 0,
                    'confidence': 'low',
                    'available': False,
                    'sample_size': total_matches,
                    **window,
                }

            # Calculate score
            # If results lookup is disabled or unavailable, remain neutral —
            # and a neutral placeholder is NOT evidence, so available=False.
            if not use_results_lookup or (team_a_wins + team_b_wins) == 0:
                score = 0.5
                has_evidence = False
            else:
                score = team_a_wins / max(team_a_wins + team_b_wins, 1)
                has_evidence = True

            return {
                'score': score,
                'details': f'Found {total_matches} H2H matches',
                'matches': total_matches,
                'team_a_wins': team_a_wins,
                'team_b_wins': team_b_wins,
                'confidence': 'medium' if total_matches >= 5 else 'low',
                'available': has_evidence,
                'sample_size': total_matches,
                **window,
            }

        except Exception as e:
            logger.error(f"❌ H2H analysis failed: {e}", exc_info=True)
            return {
                'score': 0.5,
                'details': 'H2H analysis unavailable',
                'matches': 0,
                'confidence': 'low',
                'available': False,
                'sample_size': 0,
            }

    async def _get_session_winner_from_results(
        self,
        session_date: str,
        team_a_set: set,
        team_b_set: set,
        cache: dict[str, str | None],
        as_of: datetime,
    ) -> str | None:
        """
        Resolve winner for a session_date using session_results (if available).

        Returns:
            "A" if Team A won, "B" if Team B won, None if tie/unknown.

        Only results finalized on/before `as_of` are visible: without this
        cutoff a same-day session whose result was written AFTER the prediction
        moment would leak future information into the replayed H2H factor
        (Codex #511). Rows without an `updated_at` are treated as pre-existing.
        """
        if session_date in cache:
            return cache[session_date]

        try:
            row = await self.db.fetch_one(
                """
                SELECT team_1_guids, team_2_guids, winning_team
                FROM session_results
                WHERE session_date LIKE $1
                  AND map_name = 'ALL'
                  AND (updated_at IS NULL OR updated_at <= $2)
                ORDER BY updated_at DESC NULLS LAST
                LIMIT 1
                """,
                (f"{session_date}%", as_of),
            )
        except Exception as e:
            logger.debug(f"Session results lookup failed for {session_date}: {e}")
            cache[session_date] = None
            return None

        if not row:
            cache[session_date] = None
            return None

        team_1_guids_json, team_2_guids_json, winning_team = row
        try:
            team_1_guids = set(json.loads(team_1_guids_json or "[]"))
            _ = set(json.loads(team_2_guids_json or "[]"))  # validate JSON
        except Exception:
            cache[session_date] = None
            return None

        # Determine which stored team corresponds to current Team A/B
        overlap_1a = len(team_1_guids & team_a_set) / max(len(team_a_set), 1)
        overlap_1b = len(team_1_guids & team_b_set) / max(len(team_b_set), 1)

        if overlap_1a >= overlap_1b:
            team1_label = "A"
            team2_label = "B"
        else:
            team1_label = "B"
            team2_label = "A"

        if winning_team == 1:
            cache[session_date] = team1_label
        elif winning_team == 2:
            cache[session_date] = team2_label
        else:
            cache[session_date] = None

        return cache[session_date]

    async def _analyze_recent_form(
        self,
        team_a_guids: list[str],
        team_b_guids: list[str],
        as_of: datetime,
    ) -> dict:
        """
        Analyze recent form using average DPM over the 30 days before `as_of`.

        Returns score: >0.5 = Team A has better recent form.
        Only valid, human rounds completed before `as_of` count.
        """
        window_start = (as_of - timedelta(days=30)).strftime('%Y-%m-%d')
        window = {'window_start': window_start, 'window_end': as_of.isoformat()}
        as_of_unix = int(as_of.timestamp())
        as_of_date = as_of.strftime('%Y-%m-%d')

        try:
            async def _team_avg_dpm(guids: list[str]) -> tuple[float, int]:
                if not guids:
                    return 0.0, 0
                placeholders = ','.join([f'${i+1}' for i in range(len(guids))])
                n = len(guids)
                query = f"""
                    SELECT AVG(dpm), COALESCE(SUM(rounds_n), 0) FROM (
                        SELECT pcs.player_guid, AVG(pcs.dpm) as dpm, COUNT(*) as rounds_n
                        FROM player_comprehensive_stats pcs
                        JOIN rounds r ON r.id = pcs.round_id
                        WHERE pcs.player_guid IN ({placeholders})
                          AND pcs.round_date >= ${n+1}
                          AND pcs.round_number IN (1, 2)
                          AND pcs.time_played_seconds > 60
                          AND {_VALID_HUMAN_GATE}
                          AND {_completed_before(f'${n+2}', f'${n+3}')}
                        GROUP BY pcs.player_guid
                    ) sub
                """
                result = await self.db.fetch_one(
                    query, tuple(guids) + (window_start, as_of_unix, as_of_date)
                )
                if not result or result[0] is None:
                    return 0.0, 0
                return float(result[0]), int(result[1] or 0)

            team_a_dpm, a_rounds = await _team_avg_dpm(team_a_guids)
            team_b_dpm, b_rounds = await _team_avg_dpm(team_b_guids)
            total = team_a_dpm + team_b_dpm
            sample_size = a_rounds + b_rounds

            # A one-sided comparison (only one team has prior rounds) yields an
            # extreme score (e.g. 1.0) that is NOT evidence — mark it
            # unavailable so calibration coverage never counts a half-missing
            # factor as eligible (Codex review on #511). Also enforce the
            # documented MIN_FORM_MATCHES threshold: a couple of rounds is below
            # the model's own minimum and must not be counted as evidence.
            if (total < 1 or a_rounds == 0 or b_rounds == 0
                    or sample_size < self.MIN_FORM_MATCHES):
                return {
                    'score': 0.5,
                    'details': f'Insufficient two-sided recent data '
                               f'(< {self.MIN_FORM_MATCHES} matches) for form analysis',
                    'team_a_form': f'{team_a_dpm:.0f}',
                    'team_b_form': f'{team_b_dpm:.0f}',
                    'confidence': 'low',
                    'available': False,
                    'sample_size': sample_size,
                    **window,
                }

            score = team_a_dpm / total
            diff = abs(team_a_dpm - team_b_dpm)
            confidence = 'high' if diff > 50 else ('medium' if diff > 20 else 'low')

            return {
                'score': score,
                'details': f'Team A avg DPM: {team_a_dpm:.0f}, Team B: {team_b_dpm:.0f} (30d)',
                'team_a_form': f'{team_a_dpm:.0f}',
                'team_b_form': f'{team_b_dpm:.0f}',
                'confidence': confidence,
                'available': True,
                'sample_size': sample_size,
                **window,
            }
        except Exception as e:
            logger.error(f"Form analysis failed: {e}", exc_info=True)
            return {
                'score': 0.5,
                'details': f'Form analysis error: {e}',
                'team_a_form': '?',
                'team_b_form': '?',
                'confidence': 'low',
                'available': False,
                'sample_size': 0,
            }

    async def _analyze_map_performance(
        self,
        team_a_guids: list[str],
        team_b_guids: list[str],
        map_name: str | None,
        as_of: datetime,
    ) -> dict:
        """
        Analyze map-specific DPM performance (valid human rounds before `as_of`).

        Returns score: >0.5 = Team A better on this map
        """
        if not map_name:
            return {
                'score': 0.5,
                'details': 'Map not specified',
                'confidence': 'low',
                'available': False,
                'sample_size': 0,
            }

        as_of_unix = int(as_of.timestamp())
        as_of_date = as_of.strftime('%Y-%m-%d')
        window = {'window_start': None, 'window_end': as_of.isoformat()}

        try:
            async def _team_map_dpm(guids: list[str]) -> tuple[float, int]:
                if not guids:
                    return 0.0, 0
                placeholders = ','.join([f'${i+1}' for i in range(len(guids))])
                n = len(guids)
                query = f"""
                    SELECT AVG(dpm), COALESCE(SUM(rounds_n), 0) FROM (
                        SELECT pcs.player_guid, AVG(pcs.dpm) as dpm, COUNT(*) as rounds_n
                        FROM player_comprehensive_stats pcs
                        JOIN rounds r ON r.id = pcs.round_id
                        WHERE pcs.player_guid IN ({placeholders})
                          AND pcs.map_name = ${n+1}
                          AND pcs.round_number IN (1, 2)
                          AND pcs.time_played_seconds > 60
                          AND {_VALID_HUMAN_GATE}
                          AND {_completed_before(f'${n+2}', f'${n+3}')}
                        GROUP BY pcs.player_guid
                    ) sub
                """
                result = await self.db.fetch_one(
                    query, tuple(guids) + (map_name, as_of_unix, as_of_date)
                )
                if not result or result[0] is None:
                    return 0.0, 0
                return float(result[0]), int(result[1] or 0)

            team_a_dpm, a_rounds = await _team_map_dpm(team_a_guids)
            team_b_dpm, b_rounds = await _team_map_dpm(team_b_guids)
            total = team_a_dpm + team_b_dpm
            sample_size = a_rounds + b_rounds

            # One-sided map data is not evidence (see form analysis) — require
            # both teams to have rounds on this map (Codex review on #511).
            if total < 1 or a_rounds == 0 or b_rounds == 0:
                return {
                    'score': 0.5,
                    'details': f'Insufficient two-sided data for {map_name}',
                    'confidence': 'low',
                    'available': False,
                    'sample_size': sample_size,
                    **window,
                }

            score = team_a_dpm / total
            diff = abs(team_a_dpm - team_b_dpm)
            confidence = 'high' if diff > 50 else ('medium' if diff > 20 else 'low')

            return {
                'score': score,
                'details': f'{map_name}: Team A {team_a_dpm:.0f} DPM vs Team B {team_b_dpm:.0f} DPM',
                'confidence': confidence,
                'available': True,
                'sample_size': sample_size,
                **window,
            }
        except Exception as e:
            logger.error(f"Map analysis failed: {e}", exc_info=True)
            return {
                'score': 0.5,
                'details': f'Map analysis error: {e}',
                'confidence': 'low',
                'available': False,
                'sample_size': 0,
            }

    async def _analyze_substitution_impact(
        self,
        team_a_guids: list[str],
        team_b_guids: list[str]
    ) -> dict:
        """
        Analyze impact of roster changes compared to typical lineups.

        Returns score: >0.5 = Team A has more consistent lineup
        """
        # Placeholder - check if teams have their regular players
        logger.debug("Substitution analysis not yet implemented")
        return {
            'score': 0.5,
            'details': 'Substitution analysis not yet implemented',
            'team_a_subs': 0,
            'team_b_subs': 0,
            'confidence': 'low',
            'available': False,
            'sample_size': 0,
        }

    def _calculate_confidence(
        self,
        h2h: dict,
        form: dict,
        map_perf: dict,
        subs: dict
    ) -> float:
        """
        Calculate overall prediction confidence (0-1).

        Weights each factor's confidence by its importance.
        """
        # Weight confidence by factor importance
        conf_scores = [
            (h2h.get('confidence', 'low'), self.H2H_WEIGHT),
            (form.get('confidence', 'low'), self.FORM_WEIGHT),
            (map_perf.get('confidence', 'low'), self.MAP_WEIGHT),
            (subs.get('confidence', 'low'), self.SUB_WEIGHT)
        ]

        conf_map = {'high': 1.0, 'medium': 0.6, 'low': 0.3}

        total = sum(conf_map.get(c, 0.3) * w for c, w in conf_scores)
        return total

    def _score_to_confidence_label(self, score: float) -> str:
        """Convert confidence score to human-readable label."""
        if score >= 0.7:
            return 'high'
        elif score >= 0.5:
            return 'medium'
        else:
            return 'low'

    def _generate_key_insight(
        self,
        h2h: dict,
        form: dict,
        map_perf: dict,
        subs: dict
    ) -> str:
        """Generate the most important insight for display."""
        insights = []

        # Prioritize H2H if we have data
        if h2h.get('matches', 0) >= 3:
            insights.append(h2h.get('details', ''))

        # Then form
        if form.get('confidence') == 'high':
            insights.append(form.get('details', ''))

        # Default message
        if not insights:
            return "Limited historical data - prediction may be less accurate"

        return insights[0]
