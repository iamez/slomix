from __future__ import annotations

import asyncio

import pytest

from bot.ultimate_bot import UltimateETLegacyBot


class _RetryBot:
    _schedule_endstats_retry = UltimateETLegacyBot._schedule_endstats_retry
    _get_endstats_retry_delay = UltimateETLegacyBot._get_endstats_retry_delay
    _clear_endstats_retry_state = UltimateETLegacyBot._clear_endstats_retry_state
    _safe_create_task = staticmethod(UltimateETLegacyBot._safe_create_task)

    def __init__(self):
        self.endstats_retry_tasks = {}
        self.endstats_retry_counts = {}
        self.endstats_retry_max_attempts = 5
        self.endstats_retry_base_delay = 0
        self.endstats_retry_max_delay = 0
        self.processed_endstats_files = set()
        self.retry_invocations = 0
        self._schedule_inside_first_retry = True

    async def _retry_webhook_endstats_link(
        self,
        filename: str,
        local_path: str,
        endstats_data: dict,
        trigger_message,
    ) -> None:
        self.retry_invocations += 1
        if self._schedule_inside_first_retry:
            self._schedule_inside_first_retry = False
            await self._schedule_endstats_retry(
                filename, local_path, endstats_data, trigger_message
            )


class _ListLogger:
    def __init__(self):
        self.records = []

    def info(self, *args, **kwargs):
        self.records.append(("info", args, kwargs))

    def warning(self, *args, **kwargs):
        self.records.append(("warning", args, kwargs))

    def error(self, *args, **kwargs):
        self.records.append(("error", args, kwargs))

    def debug(self, *args, **kwargs):
        self.records.append(("debug", args, kwargs))


class _QualityDbAdapter:
    def __init__(self, existing_filename: str, awards_count: int, vs_count: int):
        self.existing_filename = existing_filename
        self.awards_count = awards_count
        self.vs_count = vs_count
        self.executed_queries = []

    async def fetch_one(self, query, _params):
        normalized = " ".join(str(query).split())
        if "FROM processed_endstats_files" in normalized:
            return (self.existing_filename, "2026-02-18 21:51:00")
        if "FROM round_awards" in normalized and "FROM round_vs_stats" in normalized:
            return (self.awards_count, self.vs_count)
        return None

    async def execute(self, query, params):
        normalized = " ".join(str(query).split())
        self.executed_queries.append((normalized, params))


class _QualityBot:
    _log_endstats_transition = UltimateETLegacyBot._log_endstats_transition
    _summarize_endstats_quality = UltimateETLegacyBot._summarize_endstats_quality
    _is_endstats_quality_better = UltimateETLegacyBot._is_endstats_quality_better
    _mark_endstats_filename_handled = UltimateETLegacyBot._mark_endstats_filename_handled
    _get_round_endstats_quality = UltimateETLegacyBot._get_round_endstats_quality
    _is_endstats_round_already_processed = (
        UltimateETLegacyBot._is_endstats_round_already_processed
    )

    def __init__(self, db_adapter):
        self.db_adapter = db_adapter


class _NoopTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _PublishConflictDbAdapter:
    def __init__(self):
        self.existing_success_checks = 0
        self.executed_queries = []

    def transaction(self):
        return _NoopTransaction()

    async def fetch_one(self, query, _params):
        normalized = " ".join(str(query).split())
        if "FROM processed_endstats_files" in normalized and "LIMIT 1" in normalized:
            self.existing_success_checks += 1
            if self.existing_success_checks == 1:
                return None
            return ("older-endstats.txt", "2026-02-18 22:47:31")
        if "RETURNING id" in normalized:
            return (99,)
        if "SELECT guid FROM player_aliases" in normalized:
            return None
        return None

    async def execute(self, query, params):
        normalized = " ".join(str(query).split())
        self.executed_queries.append((normalized, params))
        if (
            "UPDATE processed_endstats_files" in normalized
            and "success = TRUE" in normalized
        ):
            raise RuntimeError(
                'duplicate key value violates unique constraint "uq_processed_endstats_round_id"'
            )


class _StoreBot:
    _log_endstats_transition = UltimateETLegacyBot._log_endstats_transition
    _summarize_endstats_quality = UltimateETLegacyBot._summarize_endstats_quality
    _is_endstats_quality_better = UltimateETLegacyBot._is_endstats_quality_better
    _mark_endstats_filename_handled = UltimateETLegacyBot._mark_endstats_filename_handled
    _is_endstats_round_unique_violation = (
        UltimateETLegacyBot._is_endstats_round_unique_violation
    )
    _get_round_endstats_quality = UltimateETLegacyBot._get_round_endstats_quality
    _store_endstats_and_publish = UltimateETLegacyBot._store_endstats_and_publish

    def __init__(self, db_adapter):
        self.db_adapter = db_adapter

        class _Publisher:
            async def publish_endstats(self, *_args, **_kwargs):
                return True

        self.round_publisher = _Publisher()


@pytest.mark.asyncio
async def test_retry_progresses_when_rescheduled_from_active_retry_task():
    bot = _RetryBot()
    filename = "2026-02-18-215111-etl_adlernest-round-2-endstats.txt"

    await bot._schedule_endstats_retry(filename, "/tmp/endstats.txt", {}, None)
    await asyncio.sleep(0.05)

    for _ in range(20):
        task = bot.endstats_retry_tasks.get(filename)
        if task is None or task.done():
            break
        await asyncio.sleep(0.01)

    if bot.endstats_retry_counts.get(filename) != 2:
        pytest.fail(
            "expected retry counter to advance to 2 when unresolved retry re-schedules itself"
        )
    if bot.retry_invocations != 2:
        pytest.fail(
            "expected two retry invocations after re-scheduling from active retry task"
        )


@pytest.mark.asyncio
async def test_richer_duplicate_is_allowed_to_replace_existing_round_payload():
    db_adapter = _QualityDbAdapter(
        existing_filename="2026-02-18-215112-etl_adlernest-round-2-endstats.txt",
        awards_count=0,
        vs_count=6,
    )
    bot = _QualityBot(db_adapter)
    log = _ListLogger()

    should_skip = await bot._is_endstats_round_already_processed(
        round_id=9874,
        filename="2026-02-18-215111-etl_adlernest-round-2-endstats.txt",
        source="test",
        log=log,
        endstats_data={
            "awards": [{"name": "Most damage given"}],
            "vs_stats": [{"player": "p1", "kills": 1, "deaths": 1}] * 6,
        },
    )

    if should_skip:
        pytest.fail("richer duplicate payload should not be skipped for same round_id")


@pytest.mark.asyncio
async def test_poorer_duplicate_is_skipped_when_round_already_has_richer_payload():
    db_adapter = _QualityDbAdapter(
        existing_filename="2026-02-18-215111-etl_adlernest-round-2-endstats.txt",
        awards_count=27,
        vs_count=12,
    )
    bot = _QualityBot(db_adapter)
    log = _ListLogger()

    should_skip = await bot._is_endstats_round_already_processed(
        round_id=9874,
        filename="2026-02-18-215112-etl_adlernest-round-2-endstats.txt",
        source="test",
        log=log,
        endstats_data={
            "awards": [],
            "vs_stats": [{"player": "p1", "kills": 1, "deaths": 1}] * 6,
        },
    )

    if not should_skip:
        pytest.fail("poorer duplicate payload should be skipped when richer payload exists")

    has_dedupe_marker = any(
        (
            "INSERT INTO processed_endstats_files" in query
            and isinstance(params, tuple)
            and len(params) >= 2
            and params[0] == "2026-02-18-215112-etl_adlernest-round-2-endstats.txt"
            and str(params[1]).startswith("duplicate_round_skip_existing:")
        )
        for query, params in db_adapter.executed_queries
    )
    if not has_dedupe_marker:
        pytest.fail("expected poorer duplicate skip to persist filename dedupe marker")


@pytest.mark.asyncio
async def test_store_endstats_handles_round_unique_violation_as_dedupe_skip():
    db_adapter = _PublishConflictDbAdapter()
    bot = _StoreBot(db_adapter)
    log = _ListLogger()

    result = await bot._store_endstats_and_publish(
        filename="2026-02-18-224726-te_escape2-round-2-endstats.txt",
        endstats_data={
            "awards": [{"name": "Most damage given", "player": "p1", "value": "123", "numeric": 123}],
            "vs_stats": [{"player": "p1", "kills": 5, "deaths": 3}],
        },
        round_id=9886,
        round_date="2026-02-18",
        map_name="te_escape2",
        round_number=2,
        log=log,
        source="test",
    )

    if not result:
        pytest.fail("expected dedupe race conflict to be treated as successful skip")

    has_conflict_marker = any(
        (
            "UPDATE processed_endstats_files" in query
            and "success = FALSE" in query
            and isinstance(params, tuple)
            and len(params) >= 3
            and str(params[2]).startswith("duplicate_round_conflict_existing_success:")
        )
        for query, params in db_adapter.executed_queries
    )
    if not has_conflict_marker:
        pytest.fail("expected conflict fallback to persist duplicate_round_conflict_existing_success marker")
