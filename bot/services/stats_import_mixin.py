"""UltimateETLegacyBot mixin: Stats file import to DB.

Extracted from ultimate_bot.py in P3e Sprint 7 / C.4a.

Handles R1/R2 differential persistence, team tracking, gaming_session_id
calculation, player stats insert, and alias updates.

All methods live on UltimateETLegacyBot via mixin inheritance. Runtime
attributes consumed here are set in the main class ``__init__``:
``self.db_adapter``, ``self.config``, ``self.file_tracker``,
``self.round_publisher``, ``self.correlation_service``.
"""
from __future__ import annotations

from datetime import datetime

from bot.core.round_contract import (
    derive_stopwatch_contract,
    score_confidence_state,
)
from bot.logging_config import get_logger

logger = get_logger("bot.core")


class _StatsImportMixin:
    """Stats file import to DB for UltimateETLegacyBot."""

    async def _import_stats_to_db(self, stats_data, filename):
        """Import parsed stats to database"""
        try:
            logger.info(
                f"📊 Importing {len(stats_data.get('players', []))} "
                f"players to database..."
            )

            # Cache player_comprehensive_stats columns for optional fields
            if not hasattr(self, "_player_stats_columns"):
                try:
                    cols = await self.db_adapter.fetch_all(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'player_comprehensive_stats'
                        """
                    )
                    self._player_stats_columns = {c[0] for c in cols}
                except Exception:
                    self._player_stats_columns = set()

            # Extract date from filename: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
            date_part = "-".join(filename.split("-")[:3])  # Date YYYY-MM-DD
            time_part = filename.split("-")[3] if len(filename.split("-")) > 3 else "000000"  # HHMMSS

            # Store time as HHMMSS (NO COLONS) to match postgresql_database_manager format
            if len(time_part) == 6:
                round_time = time_part  # Keep as HHMMSS: "221941"
            else:
                round_time = "000000"

            # Create match_id - for R2 files, use R1's timestamp so they share same match_id
            if stats_data.get('r1_filename'):
                # This is an R2 file with matched R1 - extract R1's timestamp
                r1_filename = stats_data['r1_filename']
                r1_parts = r1_filename.split("-")
                r1_date = "-".join(r1_parts[:3])  # YYYY-MM-DD
                r1_time = r1_parts[3] if len(r1_parts) > 3 else "000000"  # HHMMSS
                match_id = f"{r1_date}-{r1_time}"
                logger.info(f"🔗 R2 matched to R1: using R1 timestamp for match_id: {match_id}")
            else:
                # R1 file or orphan R2 - use own timestamp
                match_id = f"{date_part}-{time_part}"

            # Check if round already exists (FIXED: includes round_time to prevent false duplicates)
            check_query = """
                SELECT id FROM rounds
                WHERE round_date = ? AND round_time = ? AND map_name = ? AND round_number = ?
            """
            existing = await self.db_adapter.fetch_one(
                check_query,
                (
                    date_part,  # Use date_part not timestamp
                    round_time,  # FIXED: Add round_time to prevent duplicate detection when same map played twice
                    stats_data["map_name"],
                    stats_data["round_num"],
                ),
            )

            if existing:
                logger.info(
                    f"⚠️ Round already exists (ID: {existing[0]})"
                )
                return existing[0]

            # Calculate gaming_session_id (60-minute gap logic)
            gaming_session_id = await self._calculate_gaming_session_id(date_part, round_time)

            # Discover rounds table columns (cached, refreshed every 100 imports)
            import_count = getattr(self, "_rounds_col_import_count", 0) + 1
            self._rounds_col_import_count = import_count
            if not hasattr(self, "_rounds_columns") or import_count % 100 == 1:
                try:
                    cols = await self.db_adapter.fetch_all(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'rounds'
                        """
                    )
                    self._rounds_columns = {c[0] for c in cols}
                except Exception:
                    if not hasattr(self, "_rounds_columns"):
                        self._rounds_columns = set()

            defender_team = stats_data.get("defender_team", 0)
            winner_team = stats_data.get("winner_team", 0)
            round_outcome = stats_data.get("round_outcome", "")
            side_diag = stats_data.get("side_parse_diagnostics") or {}
            side_diag_reasons = list(side_diag.get("reasons") or [])

            def _add_side_reason(reason: str) -> None:
                if reason and reason not in side_diag_reasons:
                    side_diag_reasons.append(reason)

            # If R2 header data missing, inherit from latest R1 of same map/session
            if (
                stats_data.get("round_num") == 2
                and (defender_team == 0 or winner_team == 0)
                and ("defender_team" in self._rounds_columns or "winner_team" in self._rounds_columns)
            ):
                try:
                    fallback = await self.db_adapter.fetch_one(
                        """
                        SELECT defender_team, winner_team
                        FROM rounds
                        WHERE map_name = ?
                          AND round_number = 1
                          AND gaming_session_id = ?
                        ORDER BY round_date DESC,
                                 CAST(REPLACE(round_time, ':', '') AS INTEGER) DESC
                        LIMIT 1
                        """,
                        (stats_data["map_name"], gaming_session_id)
                    )
                    if fallback:
                        fallback_def, fallback_win = fallback
                        if defender_team == 0:
                            defender_team = fallback_def or 0
                            if defender_team:
                                _add_side_reason("defender_fallback_from_round1")
                        if winner_team == 0:
                            winner_team = fallback_win or 0
                            if winner_team:
                                _add_side_reason("winner_fallback_from_round1")
                except Exception as exc:
                    logger.warning(
                        "Round side fallback lookup failed for map=%s session=%s: %s",
                        stats_data.get("map_name"),
                        gaming_session_id,
                        exc,
                    )

            if defender_team == 0:
                _add_side_reason("defender_zero_final")
            if winner_team == 0:
                _add_side_reason("winner_zero_final")

            fallback_used = any("fallback_from_round1" in r for r in side_diag_reasons)
            score_confidence = score_confidence_state(
                defender_team,
                winner_team,
                reasons=side_diag_reasons,
                fallback_used=fallback_used,
            )
            stats_data["score_confidence"] = score_confidence

            # Keep stopwatch contract fields explicit when parser provided no value.
            if stats_data.get("round_stopwatch_state") is None:
                stopwatch_contract = derive_stopwatch_contract(
                    stats_data.get("round_num"),
                    stats_data.get("map_time", ""),
                    stats_data.get("actual_time", ""),
                    end_reason="NORMAL",
                )
                stats_data["round_stopwatch_state"] = stopwatch_contract["round_stopwatch_state"]
                stats_data["time_to_beat_seconds"] = stopwatch_contract["time_to_beat_seconds"]
                stats_data["next_timelimit_minutes"] = stopwatch_contract["next_timelimit_minutes"]

            if side_diag_reasons:
                if not hasattr(self, "_side_diag_reason_counts"):
                    self._side_diag_reason_counts = {}
                for reason in side_diag_reasons:
                    self._side_diag_reason_counts[reason] = (
                        self._side_diag_reason_counts.get(reason, 0) + 1
                    )

                logger.warning(
                    "[SIDE DIAG] file=%s map=%s round=%s defender=%s winner=%s "
                    "defender_raw=%s winner_raw=%s reasons=%s counts=%s",
                    filename,
                    stats_data.get("map_name"),
                    stats_data.get("round_num"),
                    defender_team,
                    winner_team,
                    side_diag.get("defender_team_raw"),
                    side_diag.get("winner_team_raw"),
                    ",".join(side_diag_reasons),
                    self._side_diag_reason_counts,
                )
            else:
                logger.info(
                    "[SIDE DIAG] file=%s map=%s round=%s defender=%s winner=%s score_confidence=%s",
                    filename,
                    stats_data.get("map_name"),
                    stats_data.get("round_num"),
                    defender_team,
                    winner_team,
                    score_confidence,
                )

            # Insert new round (include optional columns if present)
            insert_cols = [
                "round_date", "round_time", "match_id", "map_name", "round_number",
                "time_limit", "actual_time", "gaming_session_id"
            ]
            insert_vals = [
                date_part,
                round_time,
                match_id,
                stats_data["map_name"],
                stats_data["round_num"],
                stats_data.get("map_time", ""),
                stats_data.get("actual_time", ""),
                gaming_session_id,
            ]

            if "defender_team" in self._rounds_columns:
                insert_cols.append("defender_team")
                insert_vals.append(defender_team)
            if "winner_team" in self._rounds_columns:
                insert_cols.append("winner_team")
                insert_vals.append(winner_team)
            if "round_outcome" in self._rounds_columns:
                insert_cols.append("round_outcome")
                insert_vals.append(round_outcome)
            if "score_confidence" in self._rounds_columns:
                insert_cols.append("score_confidence")
                insert_vals.append(score_confidence)
            if "round_stopwatch_state" in self._rounds_columns:
                insert_cols.append("round_stopwatch_state")
                insert_vals.append(stats_data.get("round_stopwatch_state"))
            if "time_to_beat_seconds" in self._rounds_columns:
                insert_cols.append("time_to_beat_seconds")
                insert_vals.append(stats_data.get("time_to_beat_seconds"))
            if "next_timelimit_minutes" in self._rounds_columns:
                insert_cols.append("next_timelimit_minutes")
                insert_vals.append(stats_data.get("next_timelimit_minutes"))
            if "is_bot_round" in self._rounds_columns:
                insert_cols.append("is_bot_round")
                insert_vals.append(bool(stats_data.get("is_bot_round", False)))
            if "bot_player_count" in self._rounds_columns:
                insert_cols.append("bot_player_count")
                insert_vals.append(int(stats_data.get("bot_player_count", 0) or 0))
            if "human_player_count" in self._rounds_columns:
                insert_cols.append("human_player_count")
                insert_vals.append(int(stats_data.get("human_player_count", 0) or 0))

            placeholders = ", ".join(["?"] * len(insert_cols))
            insert_round_query = f"""
                INSERT INTO rounds (
                    {", ".join(insert_cols)}
                ) VALUES ({placeholders})
                RETURNING id
            """  # nosec B608 - cols from schema introspection + hardcoded constants; values parameterized via ?
            round_id = await self.db_adapter.fetch_val(
                insert_round_query,
                tuple(insert_vals),
            )

            # Insert player stats
            for player in stats_data.get("players", []):
                await self._insert_player_stats(
                    round_id, date_part, stats_data, player
                )

            # 🆕 If Round 2 file, also import match summary (cumulative stats)
            match_summary_id = None
            if stats_data.get('match_summary'):
                logger.info("📋 Importing match summary (cumulative R1+R2 stats)...")
                match_summary = stats_data['match_summary']

                # Check if match summary already exists
                check_summary_query = """
                    SELECT id FROM rounds
                    WHERE round_date = ? AND map_name = ? AND round_number = 0
                """
                existing_summary = await self.db_adapter.fetch_one(
                    check_summary_query,
                    (date_part, stats_data["map_name"]),
                )

                if not existing_summary:
                    # Insert match summary as round_number = 0 (use same gaming_session_id as the rounds)
                    summary_cols = [
                        "round_date", "round_time", "match_id", "map_name", "round_number",
                        "time_limit", "actual_time", "winner_team", "defender_team",
                        "round_outcome", "gaming_session_id"
                    ]
                    summary_vals = [
                        date_part,
                        round_time,
                        match_id,
                        match_summary["map_name"],
                        0,  # round_number = 0 for match summary
                        match_summary.get("map_time", ""),
                        match_summary.get("actual_time", ""),
                        match_summary.get("winner_team", 0),
                        match_summary.get("defender_team", 0),
                        match_summary.get("round_outcome", ""),
                        gaming_session_id,
                    ]
                    if "is_bot_round" in self._rounds_columns:
                        summary_cols.append("is_bot_round")
                        summary_vals.append(bool(match_summary.get("is_bot_round", False)))
                    if "bot_player_count" in self._rounds_columns:
                        summary_cols.append("bot_player_count")
                        summary_vals.append(int(match_summary.get("bot_player_count", 0) or 0))
                    if "human_player_count" in self._rounds_columns:
                        bot_count = match_summary.get("bot_player_count", 0) or 0
                        human_count = match_summary.get("human_player_count", 0) or max(
                            0, len(match_summary.get("players", [])) - bot_count
                        )
                        summary_cols.append("human_player_count")
                        summary_vals.append(int(human_count))

                    summary_placeholders = ", ".join(["?"] * len(summary_cols))
                    insert_summary_query = f"""
                        INSERT INTO rounds (
                            {", ".join(summary_cols)}
                        ) VALUES ({summary_placeholders})
                        RETURNING id
                    """  # nosec B608 - cols from schema introspection + hardcoded constants; values parameterized via ?
                    match_summary_id = await self.db_adapter.fetch_val(
                        insert_summary_query,
                        tuple(summary_vals),
                    )

                    # Insert match summary player stats
                    for player in match_summary.get("players", []):
                        await self._insert_player_stats(
                            match_summary_id, date_part, match_summary, player
                        )

                    logger.info(
                        f"✅ Imported match summary (ID: {match_summary_id}) with "
                        f"{len(match_summary.get('players', []))} players"
                    )
                else:
                    match_summary_id = existing_summary[0]
                    logger.info(f"⏭️  Match summary already exists (ID: {match_summary_id})")

            logger.info(
                f"✅ Imported round {round_id} with "
                f"{len(stats_data.get('players', []))} players"
            )

            # 🎯 TEAM TRACKING: Create/update teams on round import
            # This happens for every round, not just R2
            await self._handle_team_tracking(
                round_id=round_id,
                round_num=stats_data["round_num"],
                session_date=date_part,
                gaming_session_id=gaming_session_id
            )

            # 🔗 CORRELATION: notify correlation service of round import
            if hasattr(self, 'correlation_service') and self.correlation_service:
                try:
                    corr_match_id, corr_map_name, corr_round_num = (
                        await self._resolve_round_correlation_context(
                            round_id,
                            fallback_match_id=match_id,
                            fallback_map_name=stats_data.get("map_name", "unknown"),
                            fallback_round_number=int(stats_data.get("round_num", 0) or 0),
                        )
                    )
                    await self.correlation_service.on_round_imported(
                        match_id=corr_match_id,
                        round_number=corr_round_num,
                        round_id=round_id,
                        map_name=corr_map_name,
                    )
                except Exception as corr_err:
                    logger.warning(f"[CORRELATION] hook error (non-fatal): {corr_err}")

            return round_id

        except Exception as e:
            logger.error(f"❌ Database import failed: {e}")
            raise

    async def _handle_team_tracking(
        self,
        round_id: int,
        round_num: int,
        session_date: str,
        gaming_session_id: int
    ):
        """
        Handle team creation and updates after a round is imported.

        Strategy:
        - On R1: Check if this is a new session. If so, create initial teams.
        - On all rounds: Check for new players and add to appropriate team.

        This allows tracking as games grow from 3v3 → 4v4 → 6v6.

        Args:
            round_id: The round ID that was just imported
            round_num: Round number (1 or 2)
            session_date: Session date (YYYY-MM-DD)
            gaming_session_id: The gaming session ID
        """
        try:
            if not hasattr(self, 'team_manager') or self.team_manager is None:
                logger.debug("TeamManager not initialized, skipping team tracking")
                return

            # Check if teams exist for this session
            existing_teams = await self.team_manager.get_session_teams(
                session_date,
                auto_detect=False,
                gaming_session_id=gaming_session_id,
            )

            if not existing_teams:
                # No teams yet - this is likely the first round of a new session
                if round_num == 1:
                    logger.info("🎯 R1 of new session - creating initial teams...")
                    await self.team_manager.create_initial_teams_from_round(
                        round_id=round_id,
                        session_date=session_date,
                        gaming_session_id=gaming_session_id
                    )
                else:
                    # R2 came before R1 in import order - detect teams from all data
                    logger.info("🎯 R2 without R1 teams - running full detection...")
                    teams = await self.team_manager.detect_session_teams(
                        session_date,
                        gaming_session_id=gaming_session_id,
                    )
                    if teams:
                        await self.team_manager.store_session_teams(
                            session_date,
                            teams,
                            auto_assign_names=True,
                            gaming_session_id=gaming_session_id,
                        )
            else:
                # Teams exist - check for new players (subs/late joiners)
                new_players = await self.team_manager.update_teams_from_round(
                    round_id=round_id,
                    session_date=session_date,
                    gaming_session_id=gaming_session_id
                )

                if new_players.get('added'):
                    for team_name, players in new_players['added'].items():
                        logger.info(f"🆕 New players added to {team_name}: {', '.join(players)}")

                # If teams still have default names, assign random pool names.
                # Guard so sessions that cannot be auto-named do not retry on every round.
                team_names = list(existing_teams.keys())
                if set(team_names) == {'Team A', 'Team B'}:
                    session_key = (session_date, gaming_session_id)
                    if not hasattr(self, '_auto_name_attempted_sessions'):
                        self._auto_name_attempted_sessions = set()

                    if session_key not in self._auto_name_attempted_sessions:
                        self._auto_name_attempted_sessions.add(session_key)
                        try:
                            await self.team_manager.assign_random_team_names(
                                session_date, force=True, gaming_session_id=gaming_session_id
                            )
                        except Exception as e:
                            logger.warning(f"⚠️ Random team name assignment failed: {e}")

        except Exception as e:
            logger.warning(f"⚠️ Team tracking failed (non-fatal): {e}")

    async def _calculate_gaming_session_id(self, round_date: str, round_time: str) -> int:
        """
        Calculate gaming_session_id using 60-minute gap logic.

        FIXED: Now finds the chronologically PREVIOUS round (before current round),
        not the latest round in the database. This allows importing old rounds
        without breaking session grouping.

        Args:
            round_date: Date string like '2025-11-06'
            round_time: Time string like '234153' (HHMMSS) or '23:41:53' (HH:MM:SS)

        Returns:
            gaming_session_id (integer, starts at 1)
        """
        try:
            # datetime and timedelta already imported at module level

            # Parse current timestamp first
            try:
                current_dt = datetime.strptime(f"{round_date} {round_time}", '%Y-%m-%d %H%M%S')
            except ValueError:
                current_dt = datetime.strptime(f"{round_date} {round_time}", '%Y-%m-%d %H:%M:%S')

            # Get the chronologically PREVIOUS round (before current round)
            # This allows importing old rounds without messing up session IDs
            query = """
                SELECT gaming_session_id, round_date, round_time
                FROM rounds
                WHERE gaming_session_id IS NOT NULL
                  AND (round_date < ? OR (round_date = ? AND round_time < ?))
                ORDER BY round_date DESC, round_time DESC
                LIMIT 1
            """
            prev_round = await self.db_adapter.fetch_one(
                query,
                (round_date, round_date, round_time)
            )

            if not prev_round:
                # No previous round - this is first round OR earliest round being imported
                # Get max session_id and increment, or start at 1
                max_query = "SELECT MAX(gaming_session_id) FROM rounds WHERE gaming_session_id IS NOT NULL"
                max_session = await self.db_adapter.fetch_val(max_query, ())

                if max_session:
                    new_session_id = max_session + 1
                    logger.info(f"🎮 New gaming session #{new_session_id} (first round in chronological order)")
                    return new_session_id
                else:
                    logger.info("🎮 Starting first gaming session #1")
                    return 1

            prev_session_id = prev_round[0]
            prev_date = prev_round[1]
            prev_time = prev_round[2]

            # Parse previous timestamp
            try:
                prev_dt = datetime.strptime(f"{prev_date} {prev_time}", '%Y-%m-%d %H%M%S')
            except ValueError:
                prev_dt = datetime.strptime(f"{prev_date} {prev_time}", '%Y-%m-%d %H:%M:%S')

            # Calculate time gap (current - previous, should always be positive)
            gap = current_dt - prev_dt
            gap_minutes = gap.total_seconds() / 60

            # Determine effective session gap: if players are still in voice
            # channels, use the competitive gap (for BO6-BO13 halftime breaks).
            effective_gap = self.config.session_gap_minutes
            if gap_minutes > self.config.session_gap_minutes:
                voice_players = 0
                for channel_id in getattr(self, 'gaming_voice_channels', []):
                    channel = self.get_channel(channel_id)
                    if channel and hasattr(channel, "members"):
                        voice_players += sum(1 for m in channel.members if not m.bot)
                if voice_players >= 2:
                    effective_gap = self.config.competitive_session_gap_minutes
                    logger.info(
                        f"🎮 Voice-aware gap extension: {voice_players} players in voice, "
                        f"using {effective_gap}min gap (competitive mode)"
                    )

            # If gap > effective session gap, start new session
            if gap_minutes > effective_gap:
                # Get max session_id and increment
                max_query = "SELECT MAX(gaming_session_id) FROM rounds WHERE gaming_session_id IS NOT NULL"
                max_session = await self.db_adapter.fetch_val(max_query, ())
                new_session_id = (max_session or 0) + 1
                logger.info(f"🎮 New gaming session #{new_session_id} (gap: {gap_minutes:.1f} min from previous round)")
                return new_session_id
            else:
                logger.debug(f"🎮 Continuing session #{prev_session_id} (gap: {gap_minutes:.1f} min from previous round)")
                return prev_session_id

        except Exception as e:
            logger.warning(f"⚠️ Error calculating gaming_session_id: {e}. Using NULL.")
            return None

    async def _insert_player_stats(
        self, round_id, round_date, result, player
    ):
        """Insert player comprehensive stats"""
        obj_stats = player.get("objective_stats", {})

        # Time fields - seconds is primary
        time_seconds = player.get("time_played_seconds", 0)
        time_minutes = time_seconds / 60.0 if time_seconds > 0 else 0.0

        # DPM already calculated by parser
        dpm = player.get("dpm", 0.0)

        # K/D ratio
        kills = player.get("kills", 0)
        deaths = player.get("deaths", 0)
        kd_ratio = kills / deaths if deaths > 0 else float(kills)

        # Efficiency / accuracy
        # Use parser-provided accuracy (hits/shots) rather than an incorrect
        # calculation that used kills/bullets_fired. Also calculate a
        # simple efficiency metric for insertion.
        bullets_fired = obj_stats.get("bullets_fired", 0)
        efficiency = (
            (kills / (kills + deaths) * 100) if (kills + deaths) > 0 else 0.0
        )
        accuracy = player.get("accuracy", 0.0)

        # Time dead (use Lua-provided minutes when available)
        # time_dead_ratio from parser may be provided as either a fraction (0.75)
        # or a percentage (75). Normalize to percentage for storage.
        raw_td_ratio = obj_stats.get("time_dead_ratio", 0) or 0
        if raw_td_ratio <= 1 and raw_td_ratio > 0:
            td_percent = raw_td_ratio * 100.0
        else:
            td_percent = float(raw_td_ratio)

        # Prefer Lua's time_dead_minutes (R2-only field, already correct)
        raw_dead_minutes = obj_stats.get("time_dead_minutes", 0) or 0

        # Use Lua time_played_minutes if available for ratio fallback
        lua_time_minutes = obj_stats.get("time_played_minutes", 0) or 0
        time_minutes_for_ratio = lua_time_minutes if lua_time_minutes > 0 else time_minutes

        if (raw_dead_minutes <= 0) and td_percent > 0 and time_minutes_for_ratio > 0:
            raw_dead_minutes = time_minutes_for_ratio * (td_percent / 100.0)

        if (td_percent <= 0) and raw_dead_minutes > 0 and time_minutes_for_ratio > 0:
            td_percent = (raw_dead_minutes / time_minutes_for_ratio) * 100.0

        time_dead_minutes = raw_dead_minutes
        time_dead_mins = time_dead_minutes
        time_dead_ratio = td_percent
        time_played_pct = float(obj_stats.get("time_played_percent", 0) or 0)

        # ═══════════════════════════════════════════════════════════════════
        # TIME DEBUG: Validate time values before DB insert
        # ═══════════════════════════════════════════════════════════════════
        time_alive_calc = time_minutes - time_dead_minutes
        player_name = player.get("name", "Unknown")
        round_num = result.get("round_num", 0)

        # Validation checks
        if time_dead_minutes > time_minutes and time_minutes > 0:
            logger.warning(
                f"[TIME VALIDATION] ⚠️ {player_name} R{round_num}: "
                f"time_dead ({time_dead_minutes:.2f}) > time_played ({time_minutes:.2f})! "
                f"Ratio was {td_percent:.1f}%"
            )

        if time_dead_minutes < 0:
            logger.warning(
                f"[TIME VALIDATION] ⚠️ {player_name} R{round_num}: "
                f"Negative time_dead ({time_dead_minutes:.2f})!"
            )

        logger.debug(
            f"[TIME DB INSERT] {player_name} R{round_num}: "
            f"played={time_minutes:.2f}min, dead={time_dead_minutes:.2f}min, "
            f"alive={time_alive_calc:.2f}min, ratio={td_percent:.1f}%"
        )

        values = (
            round_id,
            round_date,
            result["map_name"],
            result["round_num"],
            player.get("guid", "UNKNOWN"),
            player.get("name", "Unknown"),
            player.get("name", "Unknown"),  # clean_name
            player.get("team", 0),
            kills,
            deaths,
            player.get("damage_given", 0),
            player.get("damage_received", 0),
            obj_stats.get("team_damage_given", 0),  # ✅ FIX: was player.get()
            obj_stats.get("team_damage_received", 0),  # ✅ FIX: was player.get()
            obj_stats.get("gibs", 0),
            obj_stats.get("self_kills", 0),
            obj_stats.get("team_kills", 0),
            obj_stats.get("team_gibs", 0),
            obj_stats.get("headshot_kills", 0),  # ✅ TAB field 14 - actual headshot kills
            player.get("headshots", 0),  # ✅ Sum of weapon headshot hits (what we display!)
            time_seconds,
            time_minutes,
            time_dead_mins,
            time_dead_ratio,
            time_played_pct,
            obj_stats.get("xp", 0),
            kd_ratio,
            dpm,
            efficiency,
            bullets_fired,
            accuracy,
            obj_stats.get("kill_assists", 0),
            0,
            0,  # objectives_completed, objectives_destroyed
            obj_stats.get("objectives_stolen", 0),
            obj_stats.get("objectives_returned", 0),
            obj_stats.get("dynamites_planted", 0),
            obj_stats.get("dynamites_defused", 0),
            obj_stats.get("times_revived", 0),
            obj_stats.get("revives_given", 0),
            obj_stats.get("useful_kills", 0),  # ✅ FIX: was "most_useful_kills"
            obj_stats.get("useless_kills", 0),
            obj_stats.get("kill_steals", 0),
            obj_stats.get("denied_playtime", 0),
            obj_stats.get("repairs_constructions", 0),  # ✅ FIX: was hardcoded 0
            obj_stats.get("tank_meatshield", 0),
            obj_stats.get("multikill_2x", 0),  # ✅ FIX: was "double_kills"
            obj_stats.get("multikill_3x", 0),  # ✅ FIX: was "triple_kills"
            obj_stats.get("multikill_4x", 0),  # ✅ FIX: was "quad_kills"
            obj_stats.get("multikill_5x", 0),  # ✅ FIX: was "multi_kills"
            obj_stats.get("multikill_6x", 0),  # ✅ FIX: was "mega_kills"
            obj_stats.get("killing_spree", 0),
            obj_stats.get("death_spree", 0),
        )

        query = """
            INSERT INTO player_comprehensive_stats (
                round_id, round_date, map_name, round_number,
                player_guid, player_name, clean_name, team,
                kills, deaths, damage_given, damage_received,
                team_damage_given, team_damage_received,
                gibs, self_kills, team_kills, team_gibs, headshot_kills, headshots,
                time_played_seconds, time_played_minutes,
                time_dead_minutes, time_dead_ratio, time_played_percent,
                xp, kd_ratio, dpm, efficiency,
                bullets_fired, accuracy,
                kill_assists,
                objectives_completed, objectives_destroyed,
                objectives_stolen, objectives_returned,
                dynamites_planted, dynamites_defused,
                times_revived, revives_given,
                most_useful_kills, useless_kills, kill_steals,
                denied_playtime, constructions, tank_meatshield,
                double_kills, triple_kills, quad_kills,
                multi_kills, mega_kills,
                killing_spree_best, death_spree_worst
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """
        player_stats_id = await self.db_adapter.execute(query, values)

        # Optional: store full_selfkills if column exists
        if "full_selfkills" in getattr(self, "_player_stats_columns", set()):
            try:
                await self.db_adapter.execute(
                    "UPDATE player_comprehensive_stats SET full_selfkills = ? WHERE round_id = ? AND player_guid = ?",
                    (obj_stats.get("full_selfkills", 0), round_id, player.get("guid", "UNKNOWN"))
                )
            except Exception as e:
                logger.debug(f"Failed to update full_selfkills: {e}")

        # Insert weapon stats into weapon_comprehensive_stats if available
        try:
            weapon_stats = player.get("weapon_stats", {}) or {}
            if weapon_stats:
                # Get table column info (PostgreSQL)
                col_query = """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'weapon_comprehensive_stats'
                    ORDER BY ordinal_position
                """
                pragma_rows = await self.db_adapter.fetch_all(col_query)
                cols = [r[0] for r in pragma_rows]

                # Include session metadata columns if present (they're NOT NULL in some schemas)
                insert_cols = ["round_id"]
                if "round_date" in cols:
                    insert_cols.append("round_date")
                if "map_name" in cols:
                    insert_cols.append("map_name")
                if "round_number" in cols:
                    insert_cols.append("round_number")

                if "player_comprehensive_stat_id" in cols:
                    insert_cols.append("player_comprehensive_stat_id")
                # If DB has both GUID and player_name columns, include both.
                # Some schemas require player_name NOT NULL even when GUID exists.
                if "player_guid" in cols:
                    insert_cols.append("player_guid")
                if "player_name" in cols:
                    insert_cols.append("player_name")

                insert_cols += ["weapon_name", "kills", "deaths", "headshots", "hits", "shots", "accuracy"]
                placeholders = ",".join(["?"] * len(insert_cols))
                insert_sql = f"INSERT INTO weapon_comprehensive_stats ({', '.join(insert_cols)}) VALUES ({placeholders})"  # nosec B608 - cols are hardcoded constants + schema-introspected names; values parameterized

                logger.debug(
                    f"Preparing to insert {len(weapon_stats)} weapon rows for {player.get('name')} (session {round_id})"
                )
                for weapon_name, w in weapon_stats.items():
                    w_hits = int(w.get("hits", 0) or 0)
                    w_shots = int(w.get("shots", 0) or 0)
                    w_kills = int(w.get("kills", 0) or 0)
                    w_deaths = int(w.get("deaths", 0) or 0)
                    w_headshots = int(w.get("headshots", 0) or 0)
                    w_acc = (w_hits / w_shots * 100) if w_shots > 0 else 0.0

                    # Build row values in the same order as insert_cols
                    row_vals = [round_id]
                    if "round_date" in cols:
                        row_vals.append(round_date)
                    if "map_name" in cols:
                        row_vals.append(result.get("map_name"))
                    if "round_number" in cols:
                        row_vals.append(result.get("round_num"))

                    if "player_comprehensive_stat_id" in cols:
                        row_vals.append(player_stats_id)
                    # Append GUID then player_name if present, matching insert_cols order above
                    if "player_guid" in cols:
                        row_vals.append(player.get("guid", "UNKNOWN"))
                    if "player_name" in cols:
                        row_vals.append(player.get("name", "Unknown"))

                    row_vals += [weapon_name, w_kills, w_deaths, w_headshots, w_hits, w_shots, w_acc]

                    await self.db_adapter.execute(insert_sql, tuple(row_vals))
        except Exception as e:
            # Weapon insert failures should be visible — escalate to error and include traceback
            logger.error(
                f"Failed to insert weapon stats for {player.get('name')} (session {round_id}): {e}",
                exc_info=True,
            )

        # 🔗 CRITICAL: Update player aliases for !stats and !link commands
        await self._update_player_alias(
            player.get("guid", "UNKNOWN"),
            player.get("name", "Unknown"),
            round_date,
        )

    async def _update_player_alias(self, guid, alias, last_seen_date):
        """
        Track player aliases for !stats and !link commands

        This is CRITICAL for !stats and !link to work properly!
        Updates the player_aliases table every time we see a player.
        """
        try:
            # Convert string date to datetime for PostgreSQL compatibility
            # datetime already imported at module level
            if isinstance(last_seen_date, str):
                last_seen_datetime = datetime.strptime(last_seen_date, '%Y-%m-%d')
            else:
                last_seen_datetime = last_seen_date

            # Check if this GUID+alias combination exists
            check_query = 'SELECT times_seen FROM player_aliases WHERE guid = ? AND alias = ?'
            existing = await self.db_adapter.fetch_one(check_query, (guid, alias))

            if existing:
                # Update existing alias: increment times_seen and update last_seen
                update_query = '''UPDATE player_aliases
                       SET times_seen = times_seen + 1, last_seen = ?
                       WHERE guid = ? AND alias = ?'''
                await self.db_adapter.execute(update_query, (last_seen_datetime, guid, alias))
            else:
                # Insert new alias
                insert_query = '''INSERT INTO player_aliases (guid, alias, first_seen, last_seen, times_seen)
                       VALUES (?, ?, ?, ?, 1)'''
                await self.db_adapter.execute(insert_query, (guid, alias, last_seen_datetime, last_seen_datetime))

            logger.debug(f"✅ Updated alias: {alias} for GUID {guid}")

        except Exception as e:
            logger.error(f"❌ Failed to update alias for {guid}/{alias}: {e}")
