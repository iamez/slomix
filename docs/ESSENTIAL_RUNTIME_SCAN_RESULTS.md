# Essential Runtime Scan Results

Scope: strict runtime scan inside the allowlist only.

This file records what was confirmed from startup scripts, runtime entrypoints, direct imports, mounted routers, and worker startup. It is stricter than the broader architecture map.

## confirmed_essential_files

Confirmed full-runtime entrypoints:
- [scripts/prod_up.sh](/scripts/prod_up.sh)
- [start_bot.sh](/start_bot.sh)
- [bot/ultimate_bot.py](/bot/ultimate_bot.py)
- [website/backend/main.py](/website/backend/main.py)

Confirmed bot ingestion/runtime path:
- [bot/config.py](/bot/config.py)
- [bot/core/database_adapter.py](/bot/core/database_adapter.py)
- [bot/core/utils.py](/bot/core/utils.py)
- [bot/core/round_contract.py](/bot/core/round_contract.py)
- [bot/core/round_linker.py](/bot/core/round_linker.py)
- [bot/core/team_manager.py](/bot/core/team_manager.py)
- [bot/core/stats_cache.py](/bot/core/stats_cache.py)
- [bot/core/season_manager.py](/bot/core/season_manager.py)
- [bot/core/achievement_system.py](/bot/core/achievement_system.py)
- [bot/automation/ssh_handler.py](/bot/automation/ssh_handler.py)
- [bot/automation/file_tracker.py](/bot/automation/file_tracker.py)
- [bot/repositories/file_repository.py](/bot/repositories/file_repository.py)
- [postgresql_database_manager.py](/postgresql_database_manager.py)
- [bot/community_stats_parser.py](/bot/community_stats_parser.py)
- [bot/services/round_publisher_service.py](/bot/services/round_publisher_service.py)
- [bot/services/webhook_round_metadata_service.py](/bot/services/webhook_round_metadata_service.py)
- [bot/services/voice_session_service.py](/bot/services/voice_session_service.py)
- [bot/services/timing_debug_service.py](/bot/services/timing_debug_service.py)
- [bot/services/timing_comparison_service.py](/bot/services/timing_comparison_service.py)
- [bot/services/round_correlation_service.py](/bot/services/round_correlation_service.py)
- [bot/services/monitoring_service.py](/bot/services/monitoring_service.py)
- [bot/logging_config.py](/bot/logging_config.py)
- [vps_scripts/stats_discord_webhook.lua](/vps_scripts/stats_discord_webhook.lua)

Confirmed startup-loaded bot cogs:
- [bot/cogs/admin_cog.py](/bot/cogs/admin_cog.py)
- [bot/cogs/permission_management_cog.py](/bot/cogs/permission_management_cog.py)
- [bot/cogs/link_cog.py](/bot/cogs/link_cog.py)
- [bot/cogs/stats_cog.py](/bot/cogs/stats_cog.py)
- [bot/cogs/leaderboard_cog.py](/bot/cogs/leaderboard_cog.py)
- [bot/cogs/session_cog.py](/bot/cogs/session_cog.py)
- [bot/cogs/last_session_cog.py](/bot/cogs/last_session_cog.py)
- [bot/cogs/achievements_cog.py](/bot/cogs/achievements_cog.py)
- [bot/cogs/sync_cog.py](/bot/cogs/sync_cog.py)
- [bot/cogs/session_management_cog.py](/bot/cogs/session_management_cog.py)
- [bot/cogs/team_management_cog.py](/bot/cogs/team_management_cog.py)
- [bot/cogs/team_cog.py](/bot/cogs/team_cog.py)
- [bot/cogs/matchup_cog.py](/bot/cogs/matchup_cog.py)
- [bot/cogs/analytics_cog.py](/bot/cogs/analytics_cog.py)
- [bot/cogs/automation_commands.py](/bot/cogs/automation_commands.py)

Confirmed website/API runtime path:
- [website/backend/dependencies.py](/website/backend/dependencies.py)
- [website/backend/logging_config.py](/website/backend/logging_config.py)
- [website/backend/env_utils.py](/website/backend/env_utils.py)
- [website/backend/metrics.py](/website/backend/metrics.py)
- [website/backend/middleware/__init__.py](/website/backend/middleware/__init__.py)
- [website/backend/middleware/logging_middleware.py](/website/backend/middleware/logging_middleware.py)
- [website/backend/middleware/http_cache_middleware.py](/website/backend/middleware/http_cache_middleware.py)
- [website/backend/middleware/rate_limit_middleware.py](/website/backend/middleware/rate_limit_middleware.py)
- [website/backend/routers/api.py](/website/backend/routers/api.py)
- [website/backend/routers/auth.py](/website/backend/routers/auth.py)
- [website/backend/routers/predictions.py](/website/backend/routers/predictions.py)
- [website/backend/routers/greatshot.py](/website/backend/routers/greatshot.py)
- [website/backend/routers/greatshot_topshots.py](/website/backend/routers/greatshot_topshots.py)
- [website/backend/routers/uploads.py](/website/backend/routers/uploads.py)
- [website/backend/routers/availability.py](/website/backend/routers/availability.py)
- [website/backend/routers/planning.py](/website/backend/routers/planning.py)
- [website/backend/services/http_cache_backend.py](/website/backend/services/http_cache_backend.py)
- [website/backend/services/website_session_data_service.py](/website/backend/services/website_session_data_service.py)
- [website/backend/services/game_server_query.py](/website/backend/services/game_server_query.py)
- [website/backend/services/voice_channel_tracker.py](/website/backend/services/voice_channel_tracker.py)
- [website/backend/services/planning_discord_bridge.py](/website/backend/services/planning_discord_bridge.py)
- [website/backend/services/contact_handle_crypto.py](/website/backend/services/contact_handle_crypto.py)
- [website/backend/services/upload_store.py](/website/backend/services/upload_store.py)
- [website/backend/services/upload_validators.py](/website/backend/services/upload_validators.py)
- [website/index.html](/website/index.html)
- [website/js/app.js](/website/js/app.js)
- [website/js/utils.js](/website/js/utils.js)
- [website/js/auth.js](/website/js/auth.js)
- [website/js/live-status.js](/website/js/live-status.js)
- [website/js/greatshot.js](/website/js/greatshot.js)
- [website/js/proximity.js](/website/js/proximity.js)
- [website/js/admin-panel.js](/website/js/admin-panel.js)
- [website/slomix-web.service](/website/slomix-web.service)

Confirmed app.js import-graph frontend files:
- [website/js/player-profile.js](/website/js/player-profile.js)
- [website/js/leaderboard.js](/website/js/leaderboard.js)
- [website/js/sessions.js](/website/js/sessions.js)
- [website/js/matches.js](/website/js/matches.js)
- [website/js/community.js](/website/js/community.js)
- [website/js/records.js](/website/js/records.js)
- [website/js/awards.js](/website/js/awards.js)
- [website/js/uploads.js](/website/js/uploads.js)
- [website/js/availability.js](/website/js/availability.js)
- [website/js/compare.js](/website/js/compare.js)
- [website/js/badges.js](/website/js/badges.js)
- [website/js/season-stats.js](/website/js/season-stats.js)
- [website/js/hall-of-fame.js](/website/js/hall-of-fame.js)
- [website/js/retro-viz.js](/website/js/retro-viz.js)
- [website/js/sessions2.js](/website/js/sessions2.js)
- [website/js/session-detail.js](/website/js/session-detail.js)

Confirmed Greatshot runtime path:
- [greatshot/config.py](/greatshot/config.py)
- [greatshot/worker/runner.py](/greatshot/worker/runner.py)
- [greatshot/scanner/api.py](/greatshot/scanner/api.py)
- [greatshot/scanner/adapters.py](/greatshot/scanner/adapters.py)
- [greatshot/highlights/detectors.py](/greatshot/highlights/detectors.py)
- [greatshot/cutter/api.py](/greatshot/cutter/api.py)
- [greatshot/renderer/api.py](/greatshot/renderer/api.py)
- [website/backend/services/greatshot_store.py](/website/backend/services/greatshot_store.py)
- [website/backend/services/greatshot_jobs.py](/website/backend/services/greatshot_jobs.py)
- [website/backend/services/greatshot_crossref.py](/website/backend/services/greatshot_crossref.py)

Confirmed infra/runtime files:
- [docker-compose.yml](/docker-compose.yml)
- [docker/Dockerfile.api](/docker/Dockerfile.api)
- [docker/Dockerfile.website](/docker/Dockerfile.website)
- [docker/nginx/default.conf](/docker/nginx/default.conf)
- [website/requirements.txt](/website/requirements.txt)
- [requirements.txt](requirements.txt)
- [migrations](migrations)

## optional_or_feature_gated_files

- [vps_scripts/stats_webhook_notify.py](/vps_scripts/stats_webhook_notify.py) is supported, but repo comments point to Lua `STATS_READY` as the canonical path.
- [bot/cogs/proximity_cog.py](/bot/cogs/proximity_cog.py) is startup-loadable but explicitly optional and isolated.
- [bot/cogs/server_control.py](/bot/cogs/server_control.py) is optional admin/runtime surface.
- [bot/cogs/predictions_cog.py](/bot/cogs/predictions_cog.py) is feature-gated by predictions config.
- [bot/cogs/admin_predictions_cog.py](/bot/cogs/admin_predictions_cog.py) is feature-gated by predictions config.
- [bot/cogs/availability_poll_cog.py](/bot/cogs/availability_poll_cog.py) starts conditionally from availability config.
- [bot/services/automation](/bot/services/automation) exists, but `SSHMonitor` is explicitly not auto-started because `endstats_monitor` is the canonical poller.
- [bot/services/automation/ws_client.py](/bot/services/automation/ws_client.py) is only used when `WS_ENABLED=true`.
- [proximity](proximity) is a real subsystem, but still optional relative to core startup.
- [monitoring/prometheus.yml](/monitoring/prometheus.yml) is only relevant for the optional observability profile.
- [website/backend/routers/planning.py](/website/backend/routers/planning.py) contains Discord-thread creation behavior that is config-gated.
- [greatshot/cutter/api.py](/greatshot/cutter/api.py) depends on external `UDT_cutter`.
- [greatshot/renderer/api.py](/greatshot/renderer/api.py) depends on external render command and/or `ffmpeg`.

## allowed_but_not_confirmed_runtime_files

- [Makefile](/Makefile) is a useful operator entrypoint, but not itself a runtime-loaded file.
- [README.md](/README.md) explains the system but is not runtime-loaded.
- [tools/check_production_health.py](/tools/check_production_health.py) is an ops check, not part of normal startup.
- [pyproject.toml](pyproject.toml) defines tooling/runtime bounds but is not loaded by the app at startup.
- [bot/cogs/leaderboard_cog.py](/bot/cogs/leaderboard_cog.py) and the other startup-loaded cogs are confirmed as loaded, but not all are confirmed as required for minimum successful production beyond command/UI surface.
- [website/backend/routers/predictions.py](/website/backend/routers/predictions.py) is mounted, but whether it is required for minimum successful production is still a product decision.
- [website/backend/routers/uploads.py](/website/backend/routers/uploads.py) is mounted, but not required for base stats/website availability if upload library is considered optional.
- [website/backend/services/planning_discord_bridge.py](/website/backend/services/planning_discord_bridge.py) is present in the mounted planning stack, but some behavior is config-gated.
- [website/slomix-web.service](/website/slomix-web.service) is a repo-local deployment surface, but not proof of live production deployment.
- [bot/core/checks.py](/bot/core/checks.py) is imported later from bot runtime paths, but it was not confirmed as a primary startup dependency in this pass.
- [greatshot/contracts](/greatshot/contracts) is referenced by scanner/highlight code, but the full package was not enumerated file-by-file in this pass.

## unknowns

- How the Discord bot is actually deployed in live production outside repo scripts. The repo shows [scripts/prod_up.sh](/scripts/prod_up.sh) and [start_bot.sh](/start_bot.sh), but not a bot systemd unit in the scanned allowlist.
- Whether [vps_scripts/stats_webhook_notify.py](/vps_scripts/stats_webhook_notify.py) is still used anywhere live, or whether Lua `STATS_READY` has fully replaced it.
- Exact minimum-required subset of startup-loaded bot cogs for your definition of “successful production”.
- Whether [proximity](proximity) is enabled live or only integrated/ready-to-run.
- Exact external binary provisioning for Greatshot:
  - `UDT_json`
  - `UDT_cutter`
  - `ffmpeg`
  - render command
- Database-state unknowns that code cannot prove by inspection alone:
  - migrations applied
  - Greatshot tables present
  - Lua webhook tables present
  - proximity schema present when enabled
