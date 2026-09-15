"""Narrow opt-in retry gate for an explicitly failed endstats publication."""

import os


def endstats_retry_enabled() -> bool:
    return os.getenv("ENDSTATS_RETRY_ENABLED", "false").strip().lower() == "true"


def endstats_filename_gate_query() -> str:
    """Unknown/in-flight and terminal markers stay blocking, including NULLs.

    This is eligibility only: existing scheduling and in-memory guards still
    apply. A successful handled marker is not necessarily a Discord ACK.
    """
    query = "SELECT 1 FROM processed_endstats_files WHERE filename = $1"
    if endstats_retry_enabled():
        query += " AND (success IS DISTINCT FROM FALSE OR error_message IS DISTINCT FROM 'publish_failed')"
    return query
