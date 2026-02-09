"""Background job service for Greatshot analysis and render tasks."""

from __future__ import annotations

import asyncio
import json
import traceback
import uuid
from pathlib import Path
from typing import Optional

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
                    await self._process_analysis_job(demo_id)
                    success = True
                except asyncio.TimeoutError:
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
                    await self._process_render_job(render_id)
                    success = True
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

    async def _process_analysis_job(self, demo_id: str) -> None:
        row = await self.db.fetch_one(
            """
            SELECT stored_path, extension
            FROM greatshot_demos
            WHERE id = $1
            """,
            (demo_id,),
        )
        if not row:
            logger.warning("Analysis job skipped: demo %s not found", demo_id)
            return

        stored_path, extension = row
        demo_path = Path(stored_path)

        await self.db.execute(
            """
            UPDATE greatshot_demos
            SET status = 'scanning',
                error = NULL,
                processing_started_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
            """,
            (demo_id,),
        )

        try:
            artifacts_dir = self.storage.artifacts_dir(demo_id)

            # Enforce timeout to prevent analysis from hanging forever
            timeout_seconds = getattr(GREATSHOT_CONFIG, 'scanner_timeout_seconds', 300)  # Default 5 min
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        run_analysis_job,
                        demo_path,
                        artifacts_dir,
                        None,
                    ),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
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
                return

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

            for highlight in analysis.get("highlights", []) or []:
                highlight_id = uuid.uuid4().hex
                meta_payload = dict(highlight.get("meta") or {})
                if highlight.get("explanation"):
                    meta_payload.setdefault("explanation", str(highlight.get("explanation")))

                await self.db.execute(
                    """
                    INSERT INTO greatshot_highlights (
                        id, demo_id, type, player, start_ms, end_ms, score, meta_json, clip_demo_path
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, NULL)
                    """,
                    (
                        highlight_id,
                        demo_id,
                        str(highlight.get("type") or "unknown"),
                        str(highlight.get("player") or "unknown"),
                        int(highlight.get("start_ms") or 0),
                        int(highlight.get("end_ms") or 0),
                        float(highlight.get("score") or 0.0),
                        json.dumps(meta_payload),
                    ),
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

    async def _process_render_job(self, render_id: str) -> None:
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
            return

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

            # Lock the highlight row to prevent race conditions when multiple workers
            # try to extract the same clip simultaneously (SELECT FOR UPDATE)
            locked_highlight = await self.db.fetch_one(
                "SELECT clip_demo_path FROM greatshot_highlights WHERE id = $1 FOR UPDATE",
                (highlight_id,)
            )

            # Re-check after acquiring lock (another worker may have just finished)
            locked_clip_path = locked_highlight[0] if locked_highlight else None
            clip_missing = not locked_clip_path or not Path(str(locked_clip_path)).is_file()
            if clip_missing:
                clips_dir = self.storage.clips_dir(demo_id)
                clips_dir.mkdir(parents=True, exist_ok=True)
                clip_demo = clips_dir / f"{highlight_id}{extension}"

                await asyncio.to_thread(
                    cut_demo,
                    stored_path,
                    clip_start,
                    clip_end,
                    clip_demo,
                    None,
                    GREATSHOT_CONFIG.cutter_timeout_seconds,
                )

                clip_demo_path = str(clip_demo)
                await self.db.execute(
                    "UPDATE greatshot_highlights SET clip_demo_path = $2 WHERE id = $1",
                    (highlight_id, clip_demo_path),
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


_greatshot_jobs: Optional[GreatshotJobService] = None


def set_greatshot_job_service(service: GreatshotJobService) -> None:
    global _greatshot_jobs
    _greatshot_jobs = service


def get_greatshot_job_service() -> GreatshotJobService:
    if _greatshot_jobs is None:
        raise RuntimeError("Greatshot job service not initialized")
    return _greatshot_jobs
