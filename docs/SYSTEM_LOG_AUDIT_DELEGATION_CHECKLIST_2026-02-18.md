# System Log Audit Delegation Checklist (2026-02-18)

Purpose: Convert findings into executable workstreams for follow-up agents.

Primary findings report:

1. `docs/SYSTEM_LOG_AUDIT_FINDINGS_2026-02-18.md`

## Execution Rules

1. Do not re-open closed incidents unless new evidence appears.
2. Fix highest severity first (`High`, then `Medium`).
3. Every workstream must end with:
   - code/tests evidence,
   - runtime/log evidence,
   - DB verification evidence.
4. No destructive DB actions without explicit backup and rollback notes.

## Workstream 1 - Website Greatshot Crossref Schema Drift

Owner: Website/backend agent  
Priority: P0 (High)  
Finding ID: `F-001`

### Scope

Candidate files:

1. `website/backend/services/greatshot_crossref.py`
2. `website/backend/routers/greatshot.py`
3. `website/backend/services/greatshot_jobs.py` (if query path shared)
4. `tests/` (add/update coverage for crossref query behavior)

### Tasks

1. Remove hard dependency on missing `skill_rating` column in runtime query path.
2. Make crossref enrichment tolerant to schema differences:
   - feature-detect columns before selecting, or
   - use query variant without non-existent fields.
3. Ensure failures do not silently appear as success:
   - either return partial result with explicit `degraded=true`, or
   - return structured non-200 error for true backend failures (choose one contract and document it).
4. Add unit/integration tests that reproduce:
   - missing column scenario,
   - healthy schema scenario.
5. Reduce log noise:
   - one concise structured error per failed request, no duplicate stack spam.

### Definition of Done

1. No `UndefinedColumnError: skill_rating` for `/api/greatshot/*/crossref`.
2. Crossref endpoint behavior is deterministic and documented (partial-success vs explicit error).
3. Tests for missing-column behavior pass in CI/local.

### Validation Commands

1. `rg -n "Cross-reference enrichment failed|skill_rating" website/logs/error.log | tail -n 50`
2. `rg -n "GET /api/greatshot/.*/crossref" website/logs/access.log | tail -n 50`
3. `PGPASSWORD='***' psql -h localhost -p 5432 -U website_app -d etlegacy -Atc "SELECT table_name, column_name FROM information_schema.columns WHERE column_name='skill_rating';"`

## Workstream 2 - Bot Restart Stability and Restart Cause Isolation

Owner: Bot/runtime agent  
Priority: P0 (Medium, high operational effect)  
Finding IDs: `F-003`, partially `F-002`

### Scope

Candidate files:

1. `bot/ultimate_bot.py`
2. Bot startup/runtime wrappers/scripts used in deployment
3. Service definitions/scripts used to launch bot (if in repo-managed paths)
4. Logging/health modules used during startup

### Tasks

1. Identify why bot logged `15` startups on `2026-02-18`.
2. Separate non-production test DB probes from production runtime path:
   - avoid noisy `localhost:5432/etlegacy_test` timeout errors in production logs.
3. Enforce single-instance safety:
   - prevent accidental double-start.
4. Add startup reason logging:
   - normal start, restart policy trigger, crash recovery, manual restart.
5. Add low-noise heartbeat health line every N minutes with key state.

### Definition of Done

1. Startup count during one normal session is stable (no churn bursts).
2. No recurring production log errors for `etlegacy_test` connectivity.
3. Startup reason is visible in logs for each process start.

### Validation Commands

1. `rg -n "^2026-..-.. .*ET:LEGACY DISCORD BOT - STARTING UP" logs/bot.log | tail -n 100`
2. `rg -n "etlegacy_test|Failed to connect to PostgreSQL at localhost:5432/etlegacy_test" logs/bot.log logs/errors.log`
3. `rg -n "startup reason|instance lock|duplicate instance" logs/bot.log`

## Workstream 3 - DNS/SSH Resilience for Game Host Access

Owner: Bot + website network-path agent  
Priority: P1 (Medium)  
Finding ID: `F-002`

### Scope

Candidate files:

1. Bot SSH polling/automation modules (`bot/automation/...`)
2. Website game-server query service (`website/backend/services/game_server_query.py`)
3. Config parsing/environment defaults for host fallback logic

### Tasks

1. Add safe fallback host behavior:
   - primary `puran.hehe.si`,
   - fallback IP (as documented in ops docs), gated by config.
2. Add DNS retry/backoff strategy before failing a scan cycle.
3. Add short TTL host resolution cache to reduce resolver flapping impact.
4. Log one concise incident per outage window, not per poll burst.

### Definition of Done

1. Short DNS failures do not break ingestion cycles.
2. `Temporary failure in name resolution` no longer floods logs.
3. Fallback behavior is explicit, auditable, and configurable.

### Validation Commands

1. `rg -n "Temporary failure in name resolution|DNS resolution failed for puran.hehe.si" logs/bot.log logs/errors.log | tail -n 100`
2. `rg -n "fallback|resolved host|dns cache" logs/bot.log website/logs/app.log | tail -n 100`

## Workstream 4 - Endstats Duplicate-Key Error Hygiene

Owner: Webhook/ingestion agent  
Priority: P1  
Finding ID: `F-004`

### Scope

Candidate files:

1. Endstats webhook ingestion path in bot pipeline (webhook + dedupe handling modules)
2. DB persistence layer handling `processed_endstats_files` idempotency

### Tasks

1. Reclassify expected duplicate-key races as idempotent-noise where safe.
2. Keep hard-failure semantics only for true data-loss paths.
3. Ensure dedupe decisions are explicitly logged with correlation keys:
   - filename,
   - round_id,
   - superseded_by,
   - attempt number.
4. Add test for duplicate delivery of same round endstats payload.

### Definition of Done

1. No high-severity error noise for benign duplicate-key races.
2. Latest rounds still publish exactly once.
3. `processed_endstats_files` reflects clear success/superseded semantics.

### Validation Commands

1. `rg -n "uq_processed_endstats_round_id|superseded_by_richer_payload|state=published" logs/webhook.log | tail -n 120`
2. `PGPASSWORD='***' psql -h 192.168.64.116 -p 5432 -U etlegacy_user -d etlegacy -F $'\t' -Atc "SELECT id, filename, round_id, success, error_message, processed_at FROM processed_endstats_files ORDER BY id DESC LIMIT 20;"`

## Workstream 5 - Warning Budget Reduction (Round Linker + Time Validation)

Owner: Data-quality/analytics agent  
Priority: P2  
Finding ID: `F-005`

### Scope

Candidate files:

1. Round linking logic
2. Time validation logic in DB manager/parser
3. Any warning emission thresholds/config

### Tasks

1. Classify warnings into:
   - actionable,
   - expected transient,
   - known-low-risk noise.
2. Lower log level for non-actionable noise, preserve structured counters.
3. Keep strict warnings for true data integrity risks.
4. Add daily warning summary output with top signatures.

### Definition of Done

1. Warning volume is reduced without losing integrity signals.
2. Daily log review can isolate real incidents quickly.

### Validation Commands

1. `rg -n "Round linker unresolved|\\[TIME VALIDATION\\]" logs/bot.log logs/errors.log | wc -l`
2. `rg -n "Round linker unresolved|\\[TIME VALIDATION\\]" logs/bot.log logs/errors.log | tail -n 100`

## Workstream 6 - Game Server Log Hygiene Follow-Up

Owner: Game-server ops agent  
Priority: P2  
Finding ID: `F-006` observation

### Scope

Remote paths:

1. `/home/et/.etlegacy/legacy/etconsole.log`
2. `/home/et/.etlegacy/legacy/legacy3.log`
3. `/home/et/start_servers.log`
4. `/home/et/scripts/webhook_notify.log`

### Tasks

1. Confirm whether repeated `qagame.mp.x86_64.so ... failed` lines are expected fallback noise or misconfiguration.
2. If misconfiguration, clean load order/path to avoid repeated failure logs.
3. Keep daily server restart behavior documented and intentional.

### Definition of Done

1. `qagame ... failed` lines are either eliminated or explicitly documented as benign.
2. No negative impact on stats webhook generation flow.

### Validation Commands

1. `ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si "tail -n 4000 /home/et/.etlegacy/legacy/etconsole.log | grep -c 'qagame.mp.x86_64.so)... failed'"`
2. `ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si "tail -n 120 /home/et/scripts/webhook_notify.log"`

## Global Acceptance Criteria

1. High severity finding `F-001` is fixed and validated.
2. Bot restart churn is materially reduced and causally explained.
3. DNS outage handling is resilient and low-noise.
4. Endstats dedupe path remains correct with cleaner operational logs.
5. Daily audit can be run with the command pack below and produce deterministic output.

## Daily Re-Run Command Pack (Read-Only)

1. `date -Is`
2. `rg -n "^$(date +%F).*(ERROR|CRITICAL|FATAL|Traceback|Exception)" logs/bot.log logs/errors.log logs/webhook.log website/logs/error.log website/logs/app.log`
3. `rg -n "^$(date +%F).*→ 5[0-9]{2}\\b" website/logs/access.log`
4. `ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si "date -Is; ls -lt /home/et/.etlegacy/legacy/gamestats | head"`
5. `PGPASSWORD='***' psql -h 192.168.64.116 -p 5432 -U etlegacy_user -d etlegacy -Atc "SELECT now(), current_date;"`

