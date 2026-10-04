"""Use the real adapter's parameter translation in raw-asyncpg proof fixtures."""

from bot.core.database_adapter import PostgreSQLAdapter


def pg_query(query):
    """The converter is stateless; no adapter connection or pool is created."""
    return PostgreSQLAdapter._translate_placeholders(None, query)  # noqa: SLF001
