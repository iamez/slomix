# Essential Runtime Scan Results

Scope: strict runtime scan inside the allowlist only.

This file records what was confirmed from startup scripts, runtime entrypoints, direct imports, mounted routers, and worker startup. It is stricter than the broader architecture map.

## confirmed_essential_files

Confirmed full-runtime entrypoints:
- [scripts/prod_up.sh](/home/samba/share/slomix_discord/scripts/prod_up.sh)
- [start_bot.sh](/home/samba/share/slomix_discord/start_bot.sh)
- [bot/ultimate_bot.py](/home/samba/share/slomix_discord/bot/ultimate_bot.py)
- [website/backend/main.py](/home/samba/share/slomix_discord/website/backend/main.py)

Confirmed bot ingestion/runtime path:
- [bot/config.py](/home/samba/share/slomix_discord/bot/config.py)
- [bot/core/database_adapter.py](/home/samba/share/slomix_discord/bot/core/database_adapter.py)
- [bot/core/utils.py](/home/samba/share/slomix_discord/bot/core/utils.py)
- [bot/core/round_contract.py](/home/samba/share/slomix_discord/bot/core/round_contract.py)
- [bot/core/round_linker.py](/home/samba/share/slomix_discord/bot/core/round_linker.py)
- [bot/core/team_manager.py](/home/samba/share/slomix_discord/bot/core/team_manager.py)
- [bot/core/stats_cache.py](/home/samba/share/slomix_discord/bot/core/stats_cache.py)
- [bot/core/season_manager.py](/home/samba/share/slomix_discord/bot/core/season_manager.py)
- [bot/core/achievement_system.py](/home/samba/share/slomix_discord/bot/core/achievement_system.py)
- [bot/automation/ssh_handler.py](/home/samba/share/slomix_discord/bot/automation/ssh_handler.py)
- [bot/automation/file_tracker.py](/home/samba/share/slomix_discord/bot/automation/file_tracker.py)
- [bot/repositories/file_repository.py](/home/samba/share/slomix_discord/bot/repositories/file_repository.py)
- [postgresql_database_manager.py](/home/samba/share/slomix_discord/postgresql_database_manager.py)
- [bot/community_stats_parser.py](/home/samba/share/slomix_discord/bot/community_stats_parser.py)
- [bot/services/round_publisher_service.py](/home/samba/share/slomix_discord/bot/services/round_publisher_service.py)
- [bot/services/webhook_round_metadata_service.py](/home/samba/share/slomix_discord/bot/services/webhook_round_metadata_service.py)
- [bot/services/voice_session_service.py](/home/samba/share/slomix_discord/bot/services/voice_session_service.py)
- [bot/services/timing_debug_service.py](/home/samba/share/slomix_discord/bot/services/timing_debug_service.py)
- [bot/services/timing_comparison_service.py](/home/samba/share/slomix_discord/bot/services/timing_comparison_service.py)
- [bot/services/round_correlation_service.py](/home/samba/share/slomix_discord/bot/services/round_correlation_service.py)
- [bot/services/monitoring_service.py](/home/samba/share/slomix_discord/bot/services/monitoring_service.py)
- [bot/logging_config.py](/home/samba/share/slomix_discord/bot/logging_config.py)
- [vps_scripts/stats_discord_webhook.lua](/home/samba/share/slomix_discord/vps_scripts/stats_discord_webhook.lua)

Confirmed startup-loaded bot cogs:
- [bot/cogs/admin_cog.py](/home/samba/share/slomix_discord/bot/cogs/admin_cog.py)
- [bot/cogs/permission_management_cog.py](/home/samba/share/slomix_discord/bot/cogs/permission_management_cog.py)
- [bot/cogs/link_cog.py](/home/samba/share/slomix_discord/bot/cogs/link_cog.py)
- [bot/cogs/stats_cog.py](/home/samba/share/slomix_discord/bot/cogs/stats_cog.py)
- [bot/cogs/leaderboard_cog.py](/home/samba/share/slomix_discord/bot/cogs/leaderboard_cog.py)
- [bot/cogs/session_cog.py](/home/samba/share/slomix_discord/bot/cogs/session_cog.py)
- [bot/cogs/last_session_cog.py](/home/samba/share/slomix_discord/bot/cogs/last_session_cog.py)
- [bot/cogs/achievements_cog.py](/home/samba/share/slomix_discord/bot/cogs/achievements_cog.py)
- [bot/cogs/sync_cog.py](/home/samba/share/slomix_discord/bot/cogs/sync_cog.py)
- [bot/cogs/session_management_cog.py](/home/samba/share/slomix_discord/bot/cogs/session_management_cog.py)
- [bot/cogs/team_management_cog.py](/home/samba/share/slomix_discord/bot/cogs/team_management_cog.py)
- [bot/cogs/team_cog.py](/home/samba/share/slomix_discord/bot/cogs/team_cog.py)
- [bot/cogs/matchup_cog.py](/home/samba/share/slomix_discord/bot/cogs/matchup_cog.py)
- [bot/cogs/analytics_cog.py](/home/samba/share/slomix_discord/bot/cogs/analytics_cog.py)
- [bot/cogs/automation_commands.py](/home/samba/share/slomix_discord/bot/cogs/automation_commands.py)

Confirmed website/API runtime path:
- [website/backend/dependencies.py](/home/samba/share/slomix_discord/website/backend/dependencies.py)
- [website/backend/logging_config.py](/home/samba/share/slomix_discord/website/backend/logging_config.py)
- [website/backend/env_utils.py](/home/samba/share/slomix_discord/website/backend/env_utils.py)
- [website/backend/metrics.py](/home/samba/share/slomix_discord/website/backend/metrics.py)
- [website/backend/middleware/__init__.py](/home/samba/share/slomix_discord/website/backend/middleware/__init__.py)
- [website/backend/middleware/logging_middleware.py](/home/samba/share/slomix_discord/website/backend/middleware/logging_middleware.py)
- [website/backend/middleware/http_cache_middleware.py](/home/samba/share/slomix_discord/website/backend/middleware/http_cache_middleware.py)
- [website/backend/middleware/rate_limit_middleware.py](/home/samba/share/slomix_discord/website/backend/middleware/rate_limit_middleware.py)
- [website/backend/routers/api.py](/home/samba/share/slomix_discord/website/backend/routers/api.py)
- [website/backend/routers/auth.py](/home/samba/share/slomix_discord/website/backend/routers/auth.py)
- [website/backend/routers/predictions.py](/home/samba/share/slomix_discord/website/backend/routers/predictions.py)
- [website/backend/routers/greatshot.py](/home/samba/share/slomix_discord/website/backend/routers/greatshot.py)
- [website/backend/routers/greatshot_topshots.py](/home/samba/share/slomix_discord/website/backend/routers/greatshot_topshots.py)
- [website/backend/routers/uploads.py](/home/samba/share/slomix_discord/website/backend/routers/uploads.py)
- [website/backend/routers/availability.py](/home/samba/share/slomix_discord/website/backend/routers/availability.py)
- [website/backend/routers/planning.py](/home/samba/share/slomix_discord/website/backend/routers/planning.py)
- [website/backend/services/http_cache_backend.py](/home/samba/share/slomix_discord/website/backend/services/http_cache_backend.py)
- [website/backend/services/website_session_data_service.py](/home/samba/share/slomix_discord/website/backend/services/website_session_data_service.py)
- [website/backend/services/game_server_query.py](/home/samba/share/slomix_discord/website/backend/services/game_server_query.py)
- [website/backend/services/voice_channel_tracker.py](/home/samba/share/slomix_discord/website/backend/services/voice_channel_tracker.py)
- [website/backend/services/planning_discord_bridge.py](/home/samba/share/slomix_discord/website/backend/services/planning_discord_bridge.py)
- [website/backend/services/contact_handle_crypto.py](/home/samba/share/slomix_discord/website/backend/services/contact_handle_crypto.py)
- [website/backend/services/upload_store.py](/home/samba/share/slomix_discord/website/backend/services/upload_store.py)
- [website/backend/services/upload_validators.py](/home/samba/share/slomix_discord/website/backend/services/upload_validators.py)
- [website/index.html](/home/samba/share/slomix_discord/website/index.html)
- [website/js/app.js](/home/samba/share/slomix_discord/website/js/app.js)
- [website/js/utils.js](/home/samba/share/slomix_discord/website/js/utils.js)
- [website/js/auth.js](/home/samba/share/slomix_discord/website/js/auth.js)
- [website/js/live-status.js](/home/samba/share/slomix_discord/website/js/live-status.js)
- [website/js/greatshot.js](/home/samba/share/slomix_discord/website/js/greatshot.js)
- [website/js/proximity.js](/home/samba/share/slomix_discord/website/js/proximity.js)
- [website/js/admin-panel.js](/home/samba/share/slomix_discord/website/js/admin-panel.js)
- [website/etlegacy-website.service](/home/samba/share/slomix_discord/website/etlegacy-website.service)

Confirmed app.js import-graph frontend files:
- [website/js/player-profile.js](/home/samba/share/slomix_discord/website/js/player-profile.js)
- [website/js/leaderboard.js](/home/samba/share/slomix_discord/website/js/leaderboard.js)
- [website/js/sessions.js](/home/samba/share/slomix_discord/website/js/sessions.js)
- [website/js/matches.js](/home/samba/share/slomix_discord/website/js/matches.js)
- [website/js/community.js](/home/samba/share/slomix_discord/website/js/community.js)
- [website/js/records.js](/home/samba/share/slomix_discord/website/js/records.js)
- [website/js/awards.js](/home/samba/share/slomix_discord/website/js/awards.js)
- [website/js/uploads.js](/home/samba/share/slomix_discord/website/js/uploads.js)
- [website/js/availability.js](/home/samba/share/slomix_discord/website/js/availability.js)
- [website/js/compare.js](/home/samba/share/slomix_discord/website/js/compare.js)
- [website/js/badges.js](/home/samba/share/slomix_discord/website/js/badges.js)
- [website/js/season-stats.js](/home/samba/share/slomix_discord/website/js/season-stats.js)
- [website/js/hall-of-fame.js](/home/samba/share/slomix_discord/website/js/hall-of-fame.js)
- [website/js/retro-viz.js](/home/samba/share/slomix_discord/website/js/retro-viz.js)
- [website/js/sessions2.js](/home/samba/share/slomix_discord/website/js/sessions2.js)
- [website/js/session-detail.js](/home/samba/share/slomix_discord/website/js/session-detail.js)

Confirmed Greatshot runtime path:
- [greatshot/config.py](/home/samba/share/slomix_discord/greatshot/config.py)
- [greatshot/worker/runner.py](/home/samba/share/slomix_discord/greatshot/worker/runner.py)
- [greatshot/scanner/api.py](/home/samba/share/slomix_discord/greatshot/scanner/api.py)
- [greatshot/scanner/adapters.py](/home/samba/share/slomix_discord/greatshot/scanner/adapters.py)
- [greatshot/highlights/detectors.py](/home/samba/share/slomix_discord/greatshot/highlights/detectors.py)
- [greatshot/cutter/api.py](/home/samba/share/slomix_discord/greatshot/cutter/api.py)
- [greatshot/renderer/api.py](/home/samba/share/slomix_discord/greatshot/renderer/api.py)
- [website/backend/services/greatshot_store.py](/home/samba/share/slomix_discord/website/backend/services/greatshot_store.py)
- [website/backend/services/greatshot_jobs.py](/home/samba/share/slomix_discord/website/backend/services/greatshot_jobs.py)
- [website/backend/services/greatshot_crossref.py](/home/samba/share/slomix_discord/website/backend/services/greatshot_crossref.py)

Confirmed infra/runtime files:
- [docker-compose.yml](/home/samba/share/slomix_discord/docker-compose.yml)
- [docker/Dockerfile.api](/home/samba/share/slomix_discord/docker/Dockerfile.api)
- [docker/Dockerfile.website](/home/samba/share/slomix_discord/docker/Dockerfile.website)
- [docker/nginx/default.conf](/home/samba/share/slomix_discord/docker/nginx/default.conf)
- [website/requirements.txt](/home/samba/share/slomix_discord/website/requirements.txt)
- [requirements.txt](/home/samba/share/slomix_discord/requirements.txt)
- [migrations](/home/samba/share/slomix_discord/migrations)

## optional_or_feature_gated_files

- [vps_scripts/stats_webhook_notify.py](/home/samba/share/slomix_discord/vps_scripts/stats_webhook_notify.py) is supported, but repo comments point to Lua `STATS_READY` as the canonical path.
- [bot/cogs/proximity_cog.py](/home/samba/share/slomix_discord/bot/cogs/proximity_cog.py) is startup-loadable but explicitly optional and isolated.
- [bot/cogs/synergy_analytics.py](/home/samba/share/slomix_discord/bot/cogs/synergy_analytics.py) is loaded as safe/disabled-by-default.
- [bot/cogs/server_control.py](/home/samba/share/slomix_discord/bot/cogs/server_control.py) is optional admin/runtime surface.
- [bot/cogs/predictions_cog.py](/home/samba/share/slomix_discord/bot/cogs/predictions_cog.py) is feature-gated by predictions config.
- [bot/cogs/admin_predictions_cog.py](/home/samba/share/slomix_discord/bot/cogs/admin_predictions_cog.py) is feature-gated by predictions config.
- [bot/cogs/availability_poll_cog.py](/home/samba/share/slomix_discord/bot/cogs/availability_poll_cog.py) starts conditionally from availability config.
- [bot/services/automation](/home/samba/share/slomix_discord/bot/services/automation) exists, but `SSHMonitor` is explicitly not auto-started because `endstats_monitor` is the canonical poller.
- [bot/services/automation/ws_client.py](/home/samba/share/slomix_discord/bot/services/automation/ws_client.py) is only used when `WS_ENABLED=true`.
- [proximity](/home/samba/share/slomix_discord/proximity) is a real subsystem, but still optional relative to core startup.
- [monitoring/prometheus.yml](/home/samba/share/slomix_discord/monitoring/prometheus.yml) is only relevant for the optional observability profile.
- [website/backend/routers/planning.py](/home/samba/share/slomix_discord/website/backend/routers/planning.py) contains Discord-thread creation behavior that is config-gated.
- [greatshot/cutter/api.py](/home/samba/share/slomix_discord/greatshot/cutter/api.py) depends on external `UDT_cutter`.
- [greatshot/renderer/api.py](/home/samba/share/slomix_discord/greatshot/renderer/api.py) depends on external render command and/or `ffmpeg`.

## allowed_but_not_confirmed_runtime_files

- [Makefile](/home/samba/share/slomix_discord/Makefile) is a useful operator entrypoint, but not itself a runtime-loaded file.
- [README.md](/home/samba/share/slomix_discord/README.md) explains the system but is not runtime-loaded.
- [tools/check_production_health.py](/home/samba/share/slomix_discord/tools/check_production_health.py) is an ops check, not part of normal startup.
- [pyproject.toml](/home/samba/share/slomix_discord/pyproject.toml) defines tooling/runtime bounds but is not loaded by the app at startup.
- [bot/cogs/leaderboard_cog.py](/home/samba/share/slomix_discord/bot/cogs/leaderboard_cog.py) and the other startup-loaded cogs are confirmed as loaded, but not all are confirmed as required for minimum successful production beyond command/UI surface.
- [website/backend/routers/predictions.py](/home/samba/share/slomix_discord/website/backend/routers/predictions.py) is mounted, but whether it is required for minimum successful production is still a product decision.
- [website/backend/routers/uploads.py](/home/samba/share/slomix_discord/website/backend/routers/uploads.py) is mounted, but not required for base stats/website availability if upload library is considered optional.
- [website/backend/services/planning_discord_bridge.py](/home/samba/share/slomix_discord/website/backend/services/planning_discord_bridge.py) is present in the mounted planning stack, but some behavior is config-gated.
- [website/etlegacy-website.service](/home/samba/share/slomix_discord/website/etlegacy-website.service) is a repo-local deployment surface, but not proof of live production deployment.
- [bot/core/checks.py](/home/samba/share/slomix_discord/bot/core/checks.py) is imported later from bot runtime paths, but it was not confirmed as a primary startup dependency in this pass.
- [greatshot/contracts](/home/samba/share/slomix_discord/greatshot/contracts) is referenced by scanner/highlight code, but the full package was not enumerated file-by-file in this pass.

## unknowns

- How the Discord bot is actually deployed in live production outside repo scripts. The repo shows [scripts/prod_up.sh](/home/samba/share/slomix_discord/scripts/prod_up.sh) and [start_bot.sh](/home/samba/share/slomix_discord/start_bot.sh), but not a bot systemd unit in the scanned allowlist.
- Whether [vps_scripts/stats_webhook_notify.py](/home/samba/share/slomix_discord/vps_scripts/stats_webhook_notify.py) is still used anywhere live, or whether Lua `STATS_READY` has fully replaced it.
- Exact minimum-required subset of startup-loaded bot cogs for your definition of “successful production”.
- Whether [proximity](/home/samba/share/slomix_discord/proximity) is enabled live or only integrated/ready-to-run.
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
