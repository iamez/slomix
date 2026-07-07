"""Background job service for Greatshot analysis and render tasks."""

from __future__ import annotations

import asyncio
import json
import threading
import traceback
import uuid
from pathlib import Path

from greatshot.config import CONFIG as GREATSHOT_CONFIG
from greatshot.cutter.api import build_clip_window, cut_demo
from greatshot.renderer.api import render_clip
from greatshot.worker.runner import run_analysis_job
from website.backend.logging_config import get_app_logger
from website.backend.services.greatshot_crossref import find_matching_round
from website.backend.services.greatshot_store import GreatshotStorageService

logger = get_app_logger("greatshot.jobs")


class GreatshotJobService:
    def __init__(self, db, storage: GreatshotStorageService):
        self.db = db
        self.storage = storage
        self.analysis_queue: asyncio.Queue[str] = asyncio.Queue()
        self.render_queue: asyncio.Queue[str] = asyncio.Queue()
        self.analysis_workers: list[asyncio.Task] = []
        self.render_workers: list[asyncio.Task] = []
        self.started = False

    async def start(self, analysis_workers: int = 1, render_workers: int = 1) -> None:
        if self.started:
            return

        self.storage.ensure_storage_tree()
        await self.storage.ensure_schema(self.db)

        try:
            await self._recover_stalled_jobs()
        except Exception:
            logger.error("Greatshot job recovery failed (continuing startup)\n%s",
                         traceback.format_exc())

        for idx in range(max(1, analysis_workers)):
            task = asyncio.create_task(self._analysis_worker(idx), name=f"greatshot-analysis-{idx}")
            self.analysis_workers.append(task)

        for idx in range(max(1, render_workers)):
            task = asyncio.create_task(self._render_worker(idx), name=f"greatshot-render-{idx}")
            self.render_workers.append(task)

        self.started = True
        logger.info(
            "✅ Greatshot job service started (analysis_workers=%s render_workers=%s)",
            len(self.analysis_workers),
            len(self.render_workers),
        )

    async def stop(self) -> None:
        tasks = self.analysis_workers + self.render_workers
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass

        self.analysis_workers = []
        self.render_workers = []
        self.started = False
        logger.info("🛑 Greatshot job service stopped")

    async def _recover_stalled_jobs(self) -> None:
        """Re-enqueue work stranded by a restart.

        The queues are in-memory, so a restart after the DB insert but before
        job completion leaves rows stuck forever: demos at 'uploaded' (never
        picked up) or 'scanning' (worker died mid-scan), renders at 'queued'
        or 'rendering'. At startup no job is in flight in this process, so
        every such row is recoverable.
        """
        stalled_scans = await self.db.fetch_all(
            "UPDATE greatshot_demos SET status = 'uploaded', "
            "updated_at = CURRENT_TIMESTAMP "
            "WHERE status = 'scanning' RETURNING id"
        )
        pending_demos = await self.db.fetch_all(
            "SELECT id FROM greatshot_demos WHERE status = 'uploaded'"
        )
        stalled_renders = await self.db.fetch_all(
            "UPDATE greatshot_renders SET status = 'queued', "
            "updated_at = CURRENT_TIMESTAMP "
            "WHERE status = 'rendering' RETURNING id"
        )
        pending_renders = await self.db.fetch_all(
            "SELECT id FROM greatshot_renders WHERE status = 'queued'"
        )

        for row in pending_demos or []:
            await self.analysis_queue.put(str(row[0]))
        for row in pending_renders or []:
            await self.render_queue.put(str(row[0]))

        if pending_demos or pending_renders or stalled_scans or stalled_renders:
            logger.info(
                "♻️ Greatshot recovery: re-enqueued %d demo(s) (%d were mid-scan) "
                "and %d render(s) (%d were mid-render)",
                len(pending_demos or []), len(stalled_scans or []),
                len(pending_renders or []), len(stalled_renders or []),
            )

    async def enqueue_analysis(self, demo_id: str) -> None:
        await self.analysis_queue.put(demo_id)

    async def enqueue_render(self, render_id: str) -> None:
        await self.render_queue.put(render_id)

    async def _analysis_worker(self, worker_id: int) -> None:
        MAX_RETRIES = 2  # Retry failed jobs up to 2 times
        retry_delay = 5  # seconds

        while True:
            demo_id = await self.analysis_queue.get()
            retries = 0
            success = False

            while retries <= MAX_RETRIES and not success:
                try:
                    logger.info("[analysis:%s] Processing demo_id=%s (attempt %d/%d)",
                               worker_id, demo_id, retries + 1, MAX_RETRIES + 1)
                    success = await self._process_analysis_job(demo_id)
                    if success:
                        break
                    retries += 1
                    if retries <= MAX_RETRIES:
                        logger.info("Retrying demo_id=%s in %ds...", demo_id, retry_delay)
                        await asyncio.sleep(retry_delay)
                    else:
                        logger.error(
                            "Analysis failed for demo_id=%s after %d attempts",
                            demo_id,
                            MAX_RETRIES + 1,
                        )
                except TimeoutError:
                    # Don't retry timeouts - these are likely corrupted demos
                    logger.error("Analysis timeout for demo_id=%s - not retrying", demo_id)
                    break
                except Exception:
                    logger.error(
                        "Analysis worker failure for demo_id=%s (attempt %d/%d)\n%s",
                        demo_id,
                        retries + 1,
                        MAX_RETRIES + 1,
                        traceback.format_exc(),
                    )
                    retries += 1
                    if retries <= MAX_RETRIES:
                        logger.info("Retrying demo_id=%s in %ds...", demo_id, retry_delay)
                        await asyncio.sleep(retry_delay)
                    else:
                        # Mark as failed after all retries exhausted
                        await self.db.execute(
                            """
                            UPDATE greatshot_demos
                            SET status = 'failed',
                                error = 'Analysis failed after retries',
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = $1
                            """,
                            (demo_id,),
                        )

            self.analysis_queue.task_done()

    async def _render_worker(self, worker_id: int) -> None:
        MAX_RETRIES = 1  # Retry failed renders once (rendering is expensive)
        retry_delay = 10  # seconds

        while True:
            render_id = await self.render_queue.get()
            retries = 0
            success = False

            while retries <= MAX_RETRIES and not success:
                try:
                    logger.info("[render:%s] Processing render_id=%s (attempt %d/%d)",
                               worker_id, render_id, retries + 1, MAX_RETRIES + 1)
                    success = await self._process_render_job(render_id)
                    if success:
                        break
                    retries += 1
                    if retries <= MAX_RETRIES:
                        logger.info("Retrying render_id=%s in %ds...", render_id, retry_delay)
                        await asyncio.sleep(retry_delay)
                    else:
                        logger.error(
                            "Render failed for render_id=%s after %d attempts",
                            render_id,
                            MAX_RETRIES + 1,
                        )
                except Exception:
                    logger.error(
                        "Render worker failure for render_id=%s (attempt %d/%d)\n%s",
                        render_id,
                        retries + 1,
                        MAX_RETRIES + 1,
                        traceback.format_exc(),
                    )
                    retries += 1
                    if retries <= MAX_RETRIES:
                        logger.info("Retrying render_id=%s in %ds...", render_id, retry_delay)
                        await asyncio.sleep(retry_delay)

            self.render_queue.task_done()

    async def _process_analysis_job(self, demo_id: str) -> bool:
        # F-05: Use FOR UPDATE inside a transaction to prevent concurrent
        # workers from processing the same demo simultaneously.
        async with self.db.connection() as conn, conn.transaction():
            row = await conn.fetchrow(
                """
                    SELECT stored_path, extension
                    FROM greatshot_demos
                    WHERE id = $1 AND status NOT IN ('scanning', 'analyzed')
                    FOR UPDATE SKIP LOCKED
                    """,
                demo_id,
            )
            if not row:
                logger.warning("Analysis job skipped: demo %s not found or already being processed", demo_id)
                return True

            stored_path, _ = row["stored_path"], row["extension"]
            demo_path = Path(stored_path)

            await conn.execute(
                """
                    UPDATE greatshot_demos
                    SET status = 'scanning',
                        error = NULL,
                        processing_started_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = $1
                    """,
                demo_id,
            )

        try:
            artifacts_dir = self.storage.artifacts_dir(demo_id)

            # Enforce timeout to prevent analysis from hanging forever
            timeout_seconds = getattr(GREATSHOT_CONFIG, 'scanner_timeout_seconds', 300)  # Default 5 min

            # F-06: Cooperative cancellation event so the worker thread
            # stops promptly when the asyncio timeout fires.
            cancel_event = threading.Event()

            def _cancellable_analysis():
                """Wrapper that periodically checks for cancellation."""
                # Check before starting
                if cancel_event.is_set():
                    raise RuntimeError("Analysis cancelled before start")
                result = run_analysis_job(
                    demo_path,
                    artifacts_dir,
                    None,
                    cancel_event=cancel_event,
                )
                return result

            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(_cancellable_analysis),
                    timeout=timeout_seconds
                )
            except TimeoutError:
                # Signal the worker thread to stop
                cancel_event.set()
                error_msg = f"Analysis timed out after {timeout_seconds}s"
                logger.error(f"{error_msg} for demo {demo_id}")
                await self.db.execute(
                    """
                    UPDATE greatshot_demos
                    SET status = 'failed',
                        error = $2,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = $1
                    """,
                    (demo_id, error_msg),
                )
                return False

            analysis = result["analysis"]
            metadata_json = json.dumps(analysis.get("metadata") or {})
            stats_json = json.dumps(analysis.get("stats") or {})
            events_json = json.dumps(analysis.get("timeline") or [])
            warnings_json = json.dumps(analysis.get("warnings") or [])

            # Calculate total_kills for efficient topshots queries (avoids N+1 file reads)
            player_stats = analysis.get("player_stats") or {}
            total_kills = sum([p.get("kills", 0) for p in player_stats.values()])

            await self.db.execute(
                """
                INSERT INTO greatshot_analysis (demo_id, metadata_json, stats_json, events_json, total_kills, created_at)
                VALUES ($1, $2::jsonb, $3::jsonb, $4::jsonb, $5, CURRENT_TIMESTAMP)
                ON CONFLICT (demo_id) DO UPDATE SET
                    metadata_json = EXCLUDED.metadata_json,
                    stats_json = EXCLUDED.stats_json,
                    events_json = EXCLUDED.events_json,
                    total_kills = EXCLUDED.total_kills,
                    created_at = CURRENT_TIMESTAMP
                """,
                (demo_id, metadata_json, stats_json, events_json, total_kills),
            )

            await self.db.execute(
                "DELETE FROM greatshot_highlights WHERE demo_id = $1",
                (demo_id,),
            )

            # Batch the highlight inserts. Each highlight row is independent
            # (post-DELETE) and shares the same INSERT statement; executemany
            # ships one prepared statement + N param sets in a single
            # round-trip vs the prior N sequential round-trips that ran
            # while the user waits for demo-analysis to complete.
            highlight_rows: list[tuple] = []
            for highlight in analysis.get("highlights", []) or []:
                meta_payload = dict(highlight.get("meta") or {})
                if highlight.get("explanation"):
                    meta_payload.setdefault("explanation", str(highlight.get("explanation")))
                highlight_rows.append(
                    (
                        uuid.uuid4().hex,
                        demo_id,
                        str(highlight.get("type") or "unknown"),
                        str(highlight.get("player") or "unknown"),
                        int(highlight.get("start_ms") or 0),
                        int(highlight.get("end_ms") or 0),
                        float(highlight.get("score") or 0.0),
                        json.dumps(meta_payload),
                    )
                )
            if highlight_rows:
                await self.db.executemany(
                    """
                    INSERT INTO greatshot_highlights (
                        id, demo_id, type, player, start_ms, end_ms, score, meta_json, clip_demo_path
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, NULL)
                    """,
                    highlight_rows,
                )

            await self.db.execute(
                """
                UPDATE greatshot_demos
                SET status = 'analyzed',
                    error = NULL,
                    metadata_json = $2::jsonb,
                    warnings_json = $3::jsonb,
                    analysis_json_path = $4,
                    report_txt_path = $5,
                    processing_finished_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                (
                    demo_id,
                    metadata_json,
                    warnings_json,
                    result["analysis_json_path"],
                    result["report_txt_path"],
                ),
            )

            # Auto-crossref: try to match demo to a round in the database
            try:
                metadata = analysis.get("metadata") or {}
                crossref_match = await find_matching_round(metadata, self.db)
                if crossref_match and crossref_match.get("confidence", 0) >= 50:
                    metadata["matched_round_id"] = crossref_match["round_id"]
                    metadata["crossref_confidence"] = crossref_match["confidence"]
                    metadata["crossref_match_details"] = crossref_match.get("match_details", [])
                    updated_metadata_json = json.dumps(metadata)
                    await self.db.execute(
                        """
                        UPDATE greatshot_demos
                        SET metadata_json = $2::jsonb,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = $1
                        """,
                        (demo_id, updated_metadata_json),
                    )
                    logger.info(
                        "Greatshot crossref: demo=%s matched round_id=%s (confidence=%.1f)",
                        demo_id, crossref_match["round_id"], crossref_match["confidence"],
                    )
            except Exception as crossref_exc:
                logger.warning("Greatshot crossref failed for %s: %s", demo_id, crossref_exc)

            logger.info("✅ Greatshot analysis completed for %s", demo_id)
            return True

        except Exception as exc:
            await self.db.execute(
                """
                UPDATE greatshot_demos
                SET status = 'failed',
                    error = $2,
                    processing_finished_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                (demo_id, str(exc)[:1200]),
            )
            logger.error("❌ Greatshot analysis failed for %s: %s", demo_id, exc)
            return False

    async def _process_render_job(self, render_id: str) -> bool:
        row = await self.db.fetch_one(
            """
            SELECT
                r.highlight_id,
                h.demo_id,
                h.start_ms,
                h.end_ms,
                h.clip_demo_path,
                d.stored_path,
                d.extension,
                d.metadata_json
            FROM greatshot_renders r
            JOIN greatshot_highlights h ON h.id = r.highlight_id
            JOIN greatshot_demos d ON d.id = h.demo_id
            WHERE r.id = $1
            """,
            (render_id,),
        )

        if not row:
            logger.warning("Render job skipped: render %s not found", render_id)
            return True

        (
            highlight_id,
            demo_id,
            start_ms,
            end_ms,
            clip_demo_path,
            stored_path,
            extension,
            metadata_json,
        ) = row

        await self.db.execute(
            """
            UPDATE greatshot_renders
            SET status = 'rendering',
                error = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
            """,
            (render_id,),
        )

        try:
            metadata = metadata_json or {}
            if isinstance(metadata_json, str):
                try:
                    metadata = json.loads(metadata_json)
                except Exception:
                    metadata = {}

            # Highlights use absolute server-time offsets (e.g. 8.7M ms).
            # We need the demo's maximum server-time as the upper clamp.
            # metadata["end_ms"] = absolute server time at demo end.
            # metadata["duration_ms"] = gameplay-only length (NOT usable as clamp).
            demo_end_ms = int(metadata.get("end_ms") or 0)
            if demo_end_ms <= 0:
                demo_end_ms = int(end_ms or 0) + 3000

            clip_start, clip_end = build_clip_window(
                highlight_start_ms=int(start_ms or 0),
                highlight_end_ms=int(end_ms or 0),
                demo_duration_ms=demo_end_ms,
            )

            # The cutter is an external process that can run for minutes —
            # never hold a DB row lock across it. Pattern: check without a
            # lock, cut into a job-unique temp file, then adopt or discard the
            # result in a short FOR UPDATE transaction (concurrent workers
            # race harmlessly; the loser deletes its temp file).
            clip_demo_path = None
            existing_row = await self.db.fetch_one(
                "SELECT clip_demo_path FROM greatshot_highlights WHERE id = $1",
                (highlight_id,),
            )
            existing_clip = str(existing_row[0]) if existing_row and existing_row[0] else None
            if existing_clip and Path(existing_clip).is_file():
                clip_demo_path = existing_clip
            else:
                clips_dir = self.storage.clips_dir(demo_id)
                clips_dir.mkdir(parents=True, exist_ok=True)
                final_clip = clips_dir / f"{highlight_id}{extension}"
                tmp_clip = clips_dir / f"{highlight_id}.{render_id}.tmp{extension}"

                try:
                    await asyncio.to_thread(
                        cut_demo,
                        stored_path,
                        clip_start,
                        clip_end,
                        tmp_clip,
                        None,
                        GREATSHOT_CONFIG.cutter_timeout_seconds,
                    )

                    # Short transaction: re-check under lock, adopt or discard.
                    async with self.db.connection() as conn, conn.transaction():
                        locked_highlight = await conn.fetchrow(
                            "SELECT clip_demo_path FROM greatshot_highlights "
                            "WHERE id = $1 FOR UPDATE",
                            highlight_id,
                        )
                        locked_clip = locked_highlight[0] if locked_highlight else None
                        if locked_clip and Path(str(locked_clip)).is_file():
                            clip_demo_path = str(locked_clip)  # concurrent worker won
                        else:
                            tmp_clip.replace(final_clip)
                            clip_demo_path = str(final_clip)
                            await conn.execute(
                                "UPDATE greatshot_highlights "
                                "SET clip_demo_path = $2 WHERE id = $1",
                                highlight_id,
                                clip_demo_path,
                            )
                finally:
                    tmp_clip.unlink(missing_ok=True)

            if not clip_demo_path:
                raise RuntimeError(
                    f"clip_demo_path unavailable for highlight {highlight_id}"
                )

            videos_dir = self.storage.videos_dir(demo_id)
            videos_dir.mkdir(parents=True, exist_ok=True)
            output_mp4 = videos_dir / f"{highlight_id}.mp4"

            render_options = {
                "timeout_seconds": GREATSHOT_CONFIG.render_timeout_seconds,
            }
            if GREATSHOT_CONFIG.render_command:
                render_options["render_command"] = GREATSHOT_CONFIG.render_command

            await asyncio.to_thread(
                render_clip,
                clip_demo_path,
                output_mp4,
                render_options,
            )

            await self.db.execute(
                """
                UPDATE greatshot_renders
                SET status = 'rendered',
                    mp4_path = $2,
                    error = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                (render_id, str(output_mp4)),
            )
            return True

        except Exception as exc:
            await self.db.execute(
                """
                UPDATE greatshot_renders
                SET status = 'failed',
                    error = $2,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                (render_id, str(exc)[:1200]),
            )
            logger.warning("Render job failed for %s: %s", render_id, exc)
            return False


_greatshot_jobs: GreatshotJobService | None = None


def set_greatshot_job_service(service: GreatshotJobService) -> None:
    global _greatshot_jobs
    _greatshot_jobs = service


def get_greatshot_job_service() -> GreatshotJobService:
    if _greatshot_jobs is None:
        raise RuntimeError("Greatshot job service not initialized")
    return _greatshot_jobs
