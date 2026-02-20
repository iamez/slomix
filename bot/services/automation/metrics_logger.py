"""
📊 Metrics Logger
=================

Comprehensive logging system for automation metrics.
Tracks everything so you can analyze bot behavior after long runs.

Features:
- Logs all automation events
- Tracks performance metrics
- Records errors with context
- Generates analysis reports
- Exports metrics to JSON/CSV
"""

import asyncio
import aiosqlite
import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

logger = logging.getLogger("MetricsLogger")


class MetricsLogger:
    """
    Comprehensive metrics logging and analysis system.

    Tracks:
    - File processing events
    - Performance metrics (timing, resources)
    - Error events with context
    - System health checks
    - Bot uptime and availability
    """

    def __init__(self, db_path: str, log_dir: str = "bot/logs/metrics"):
        """
        Initialize metrics logger.

        Args:
            db_path: Path to metrics SQLite database
            log_dir: Directory for metrics logs
        """
        self.db_path = db_path
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

        # In-memory metrics (for fast access)
        self.events: List[Dict[str, Any]] = []
        self.errors: List[Dict[str, Any]] = []
        self.performance: List[Dict[str, Any]] = []

        # Counters
        self.event_counts = defaultdict(int)
        self.error_counts = defaultdict(int)

        # Start time
        self.start_time = datetime.now()

        # Metrics database path (explicit config path wins)
        self.metrics_db_path = db_path or os.path.join(log_dir, "metrics.db")
        metrics_db_dir = os.path.dirname(self.metrics_db_path)
        if metrics_db_dir:
            os.makedirs(metrics_db_dir, exist_ok=True)

        # Lazy one-time initialization guard
        self._is_initialized = False
        self._init_lock = asyncio.Lock()
        self._db_lock = asyncio.Lock()
        self._db_connection: Optional[aiosqlite.Connection] = None

        logger.info(
            f"📊 Metrics Logger initialized: log_dir={self.log_dir}, db={self.metrics_db_path}"
        )

    async def initialize_metrics_db(self):
        """Create metrics database tables"""
        try:
            db = await self._get_db_connection()
            async with self._db_lock:
                # Events table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        event_data TEXT,
                        duration_ms REAL,
                        success INTEGER DEFAULT 1
                    )
                """)

                # Errors table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS errors (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        error_type TEXT NOT NULL,
                        error_message TEXT,
                        stack_trace TEXT,
                        context TEXT
                    )
                """)

                # Performance metrics table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS performance (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        metric_value REAL NOT NULL,
                        unit TEXT
                    )
                """)

                # Health checks table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS health_checks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        status TEXT NOT NULL,
                        uptime_seconds INTEGER,
                        error_count INTEGER,
                        ssh_status TEXT,
                        db_size_mb REAL,
                        memory_mb REAL,
                        cpu_percent REAL
                    )
                """)

                await db.commit()
            self._is_initialized = True
            logger.info("✅ Metrics database initialized")

        except Exception as e:
            logger.error(f"❌ Failed to initialize metrics DB: {e}")

    async def _ensure_initialized(self):
        """Ensure metrics schema exists before reads/writes."""
        if self._is_initialized:
            return
        async with self._init_lock:
            if self._is_initialized:
                return
            await self.initialize_metrics_db()

    async def _get_db_connection(self) -> aiosqlite.Connection:
        if self._db_connection is not None:
            return self._db_connection
        self._db_connection = await aiosqlite.connect(self.metrics_db_path)
        return self._db_connection

    async def _execute_write(self, query: str, params: tuple) -> None:
        await self._ensure_initialized()
        db = await self._get_db_connection()
        async with self._db_lock:
            await db.execute(query, params)
            await db.commit()

    async def close(self) -> None:
        if self._db_connection is None:
            return
        async with self._db_lock:
            if self._db_connection is not None:
                await self._db_connection.close()
                self._db_connection = None
        self._is_initialized = False

    async def log_event(self, event_type: str, event_data: Optional[Dict] = None,
                       duration_ms: Optional[float] = None, success: bool = True):
        """
        Log an automation event.

        Args:
            event_type: Type of event (e.g., 'file_processed', 'ssh_check', 'round_posted')
            event_data: Additional data about the event
            duration_ms: How long the event took (milliseconds)
            success: Whether the event succeeded
        """
        try:
            timestamp = datetime.now().isoformat()

            # Store in memory
            event = {
                'timestamp': timestamp,
                'type': event_type,
                'data': event_data,
                'duration_ms': duration_ms,
                'success': success
            }
            self.events.append(event)
            self.event_counts[event_type] += 1

            # Keep only last 1000 events in memory
            if len(self.events) > 1000:
                self.events.pop(0)

            # Store in database
            await self._execute_write(
                """
                    INSERT INTO events (timestamp, event_type, event_data, duration_ms, success)
                    VALUES (?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    event_type,
                    json.dumps(event_data) if event_data else None,
                    duration_ms,
                    1 if success else 0
                ),
            )

            logger.debug(f"📝 Event logged: {event_type} (success={success})")

        except Exception as e:
            logger.error(f"❌ Failed to log event: {e}")

    async def log_error(self, error_type: str, error_message: str,
                       stack_trace: Optional[str] = None, context: Optional[Dict] = None):
        """
        Log an error with full context.

        Args:
            error_type: Type of error (e.g., 'ssh_connection', 'database', 'parsing')
            error_message: Error message
            stack_trace: Full stack trace if available
            context: Additional context about when/where error occurred
        """
        try:
            timestamp = datetime.now().isoformat()

            # Store in memory
            error = {
                'timestamp': timestamp,
                'type': error_type,
                'message': error_message,
                'stack_trace': stack_trace,
                'context': context
            }
            self.errors.append(error)
            self.error_counts[error_type] += 1

            # Keep only last 500 errors in memory
            if len(self.errors) > 500:
                self.errors.pop(0)

            # Store in database
            await self._execute_write(
                """
                    INSERT INTO errors (timestamp, error_type, error_message, stack_trace, context)
                    VALUES (?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    error_type,
                    error_message,
                    stack_trace,
                    json.dumps(context) if context else None
                ),
            )

            logger.warning(f"⚠️ Error logged: {error_type} - {error_message}")

        except Exception as e:
            logger.error(f"❌ Failed to log error: {e}")

    async def log_performance(self, metric_name: str, value: float, unit: str = "ms"):
        """
        Log a performance metric.

        Args:
            metric_name: Name of metric (e.g., 'ssh_check_time', 'file_download_time')
            value: Metric value
            unit: Unit of measurement (e.g., 'ms', 'seconds', 'bytes')
        """
        try:
            timestamp = datetime.now().isoformat()

            # Store in memory
            metric = {
                'timestamp': timestamp,
                'name': metric_name,
                'value': value,
                'unit': unit
            }
            self.performance.append(metric)

            # Keep only last 1000 metrics in memory
            if len(self.performance) > 1000:
                self.performance.pop(0)

            # Store in database
            await self._execute_write(
                """
                    INSERT INTO performance (timestamp, metric_name, metric_value, unit)
                    VALUES (?, ?, ?, ?)
                """,
                (timestamp, metric_name, value, unit),
            )

            logger.debug(f"📊 Performance logged: {metric_name} = {value} {unit}")

        except Exception as e:
            logger.error(f"❌ Failed to log performance: {e}")

    async def log_health_check(self, status: str, uptime_seconds: int, error_count: int,
                               ssh_status: str, db_size_mb: float, memory_mb: float, cpu_percent: float):
        """
        Log a health check result.

        Args:
            status: Overall status ('healthy', 'degraded', 'error')
            uptime_seconds: Bot uptime in seconds
            error_count: Total error count
            ssh_status: SSH connection status
            db_size_mb: Database size in MB
            memory_mb: Memory usage in MB
            cpu_percent: CPU usage percentage
        """
        try:
            timestamp = datetime.now().isoformat()

            await self._execute_write(
                """
                    INSERT INTO health_checks
                    (timestamp, status, uptime_seconds, error_count, ssh_status, db_size_mb, memory_mb, cpu_percent)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (timestamp, status, uptime_seconds, error_count, ssh_status, db_size_mb, memory_mb, cpu_percent),
            )

            logger.debug(f"💚 Health check logged: {status}")

        except Exception as e:
            logger.error(f"❌ Failed to log health check: {e}")

    async def generate_report(self, hours: int = 24) -> Dict[str, Any]:
        """
        Generate comprehensive metrics report.

        Args:
            hours: Number of hours to include in report

        Returns:
            Dictionary with analysis results
        """
        for attempt in range(2):
            try:
                await self._ensure_initialized()
                cutoff_time = datetime.now() - timedelta(hours=hours)
                cutoff_str = cutoff_time.isoformat()
                db = await self._get_db_connection()

                report = {
                    'generated_at': datetime.now().isoformat(),
                    'time_range_hours': hours,
                    'summary': {},
                    'events': {},
                    'errors': {},
                    'performance': {},
                    'health': {}
                }

                async with self._db_lock:
                    # Event summary
                    cursor = await db.execute("""
                        SELECT event_type, COUNT(*), AVG(duration_ms), SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END)
                        FROM events
                        WHERE timestamp > ?
                        GROUP BY event_type
                    """, (cutoff_str,))

                    events = await cursor.fetchall()
                    report['events'] = {
                        row[0]: {
                            'count': row[1],
                            'avg_duration_ms': row[2],
                            'success_count': row[3],
                            'success_rate': (row[3] / row[1] * 100) if row[1] > 0 else 0
                        }
                        for row in events
                    }

                    # Error summary
                    cursor = await db.execute("""
                        SELECT error_type, COUNT(*), MAX(timestamp)
                        FROM errors
                        WHERE timestamp > ?
                        GROUP BY error_type
                    """, (cutoff_str,))

                    errors = await cursor.fetchall()
                    report['errors'] = {
                        row[0]: {
                            'count': row[1],
                            'last_occurrence': row[2]
                        }
                        for row in errors
                    }

                    # Performance metrics
                    cursor = await db.execute("""
                        SELECT metric_name, AVG(metric_value), MIN(metric_value), MAX(metric_value), unit
                        FROM performance
                        WHERE timestamp > ?
                        GROUP BY metric_name, unit
                    """, (cutoff_str,))

                    perf = await cursor.fetchall()
                    report['performance'] = {
                        row[0]: {
                            'avg': row[1],
                            'min': row[2],
                            'max': row[3],
                            'unit': row[4]
                        }
                        for row in perf
                    }

                    # Health checks
                    cursor = await db.execute("""
                        SELECT
                            COUNT(*) as check_count,
                            SUM(CASE WHEN status = 'healthy' THEN 1 ELSE 0 END) as healthy_count,
                            AVG(memory_mb) as avg_memory,
                            AVG(cpu_percent) as avg_cpu,
                            MAX(db_size_mb) as max_db_size
                        FROM health_checks
                        WHERE timestamp > ?
                    """, (cutoff_str,))

                    health_row = await cursor.fetchone()
                    if health_row:
                        report['health'] = {
                            'total_checks': health_row[0],
                            'healthy_checks': health_row[1],
                            'health_rate': (health_row[1] / health_row[0] * 100) if health_row[0] > 0 else 0,
                            'avg_memory_mb': health_row[2],
                            'avg_cpu_percent': health_row[3],
                            'max_db_size_mb': health_row[4]
                        }

                    # Overall summary
                    total_events = sum(e['count'] for e in report['events'].values())
                    total_errors = sum(e['count'] for e in report['errors'].values())

                    report['summary'] = {
                        'total_events': total_events,
                        'total_errors': total_errors,
                        'error_rate': (total_errors / total_events * 100) if total_events > 0 else 0,
                        'uptime_hours': hours,
                        'events_per_hour': total_events / hours if hours > 0 else 0
                    }

                logger.info(f"📊 Report generated for last {hours} hours")
                return report
            except aiosqlite.OperationalError as e:
                if "no such table" in str(e).lower() and attempt == 0:
                    logger.warning(
                        "Metrics schema missing during report generation; reinitializing metrics DB"
                    )
                    self._is_initialized = False
                    await self.initialize_metrics_db()
                    continue
                logger.error(f"❌ Failed to generate report: {e}")
                return {}
            except Exception as e:
                logger.error(f"❌ Failed to generate report: {e}")
                return {}

        return {}

    async def export_to_json(self, filepath: Optional[str] = None) -> str:
        """
        Export all metrics to JSON file.

        Args:
            filepath: Optional path for JSON file

        Returns:
            Path to exported file
        """
        try:
            if not filepath:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filepath = os.path.join(self.log_dir, f"metrics_export_{timestamp}.json")

            # Generate comprehensive report
            report = await self.generate_report(hours=24*7)  # Last week

            # Add raw event counts
            report['event_counts'] = dict(self.event_counts)
            report['error_counts'] = dict(self.error_counts)

            # Write to file
            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2)

            logger.info(f"📄 Metrics exported to: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"❌ Failed to export metrics: {e}")
            return ""

    def get_summary(self) -> Dict[str, Any]:
        """Get quick summary of current metrics"""
        uptime = datetime.now() - self.start_time

        return {
            'uptime_seconds': int(uptime.total_seconds()),
            'uptime_formatted': str(uptime).split('.')[0],
            'total_events': len(self.events),
            'total_errors': len(self.errors),
            'event_types': len(self.event_counts),
            'error_types': len(self.error_counts),
            'most_common_event': max(self.event_counts.items(), key=lambda x: x[1])[0] if self.event_counts else None,
            'most_common_error': max(self.error_counts.items(), key=lambda x: x[1])[0] if self.error_counts else None,
        }
