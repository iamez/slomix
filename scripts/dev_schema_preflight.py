#!/usr/bin/env python3
"""Read-only ledger and minimum-column gate for an explicitly supplied DEV DB.

This is not a deployment, migration, service-environment verification, or a
complete readiness certificate. No .env discovery or process-env fallback.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

import asyncpg
from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.release_manifest import file_hash, verify_release  # noqa: E402
from shared.runtime_environment import read_external_environment, refuse_config_overrides  # noqa: E402

REQUIRED_COLUMNS = {
    ("proximity_processed_files", "runtime_parent_gate"): ("boolean", True),
    ("proximity_processed_files", "linked_round_id"): ("integer", False),
    ("player_track", "death_type"): ("text", False),
}


class PreflightError(Exception):
    """A non-secret, operator-facing refusal."""


def connection_options(env_file, expected, *, release_root=None, expected_digest=None):
    values = (read_external_environment(Path(env_file), root=release_root, expected_digest=expected_digest)
              if release_root is not None else dotenv_values(env_file, interpolate=False))
    # Require an explicit engine so bot_config.json cannot silently select SQLite.
    if values.get("DATABASE_TYPE", "").lower() != "postgresql":
        raise PreflightError("Explicit DATABASE_TYPE=postgresql required")
    config_file = Path(env_file).parent / "bot_config.json"
    try:
        config = (json.loads(config_file.read_text())
                  if release_root is None and config_file.exists() else {})
    except (OSError, ValueError):
        raise PreflightError("Cannot verify application database configuration") from None
    if not isinstance(config, dict):
        raise PreflightError("Application configuration must be an object")
    if values.get("POSTGRES_SSL_MODE", config.get("POSTGRES_SSL_MODE", "disable")) != "disable":
        raise PreflightError("DEV schema gate requires POSTGRES_SSL_MODE=disable")
    keys = ("HOST", "PORT", "DATABASE", "USER", "PASSWORD")
    if any(values.get("POSTGRES_" + key) is None for key in keys):
        raise PreflightError("Explicit POSTGRES_HOST/PORT/DATABASE/USER/PASSWORD required")
    try:
        port = int(values["POSTGRES_PORT"])
    except (TypeError, ValueError):
        raise PreflightError("Invalid explicit database port") from None
    identity = (values["POSTGRES_HOST"], port, values["POSTGRES_DATABASE"], values["POSTGRES_USER"])
    if not all(identity) or not 1 <= port <= 65535 or identity != expected:
        raise PreflightError("Explicit database identity does not match expected identity")
    return {
        "host": identity[0], "port": port, "database": identity[2], "user": identity[3],
        "password": values["POSTGRES_PASSWORD"],
        "passfile": None, "ssl": False, "timeout": 5, "command_timeout": 10,
        "server_settings": {
            "default_transaction_read_only": "on", "lock_timeout": "2000",
            "statement_timeout": "8000", "search_path": "pg_catalog, public",
            "application_name": "slomix-dev-schema-preflight",
        },
    }


def migration_checksums(directory):
    files = sorted(Path(directory).glob("*.sql"))
    if not files or any(path.is_symlink() for path in files):
        raise PreflightError("Migration directory is empty or contains symlinked SQL")
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}


def compare_contract(checksums, ledger, columns):
    recorded = {row["filename"]: row for row in ledger}
    if len(recorded) != len(ledger):
        raise PreflightError("Duplicate migration filenames in ledger")
    failed = sorted(name for name, row in recorded.items() if row["success"] is not True)
    pending = sorted(set(checksums) - set(recorded))
    missing = sorted(set(recorded) - set(checksums))
    mismatches = sorted(name for name in set(checksums) & set(recorded)
                        if recorded[name]["checksum"] is not None
                        and recorded[name]["checksum"] != checksums[name])
    # Historical NULL checksums are not a proven match. Keep this uncertainty
    # visible, consistent with the runner's allowance for pre-checksum rows.
    unknown = sorted(name for name, row in recorded.items() if row["checksum"] is None)
    measured = {(row["table_name"], row["column_name"]):
                (row["data_type"], row["not_null"]) for row in columns}
    invalid = [f"{table}.{column}" for (table, column), contract in REQUIRED_COLUMNS.items()
               if measured.get((table, column)) != contract]
    return {
        "scope": "supplied-identity ledger and minimum columns only",
        "clean": not (failed or pending or missing or mismatches or invalid),
        "applied_count": sum(row["success"] is True for row in ledger),
        "failed": failed, "pending": pending, "missing": missing,
        "checksum_mismatches": mismatches, "unknown_checksums": unknown,
        "invalid_columns": invalid,
    }


async def inspect_database(options, checksums):
    conn = await asyncpg.connect(**options)
    try:
        async with conn.transaction(isolation="repeatable_read", readonly=True):
            identity = await conn.fetchrow(
                "SELECT current_database() AS database, current_user AS role, "
                "current_setting('transaction_read_only') AS read_only")
            if (identity["database"] != options["database"] or identity["role"] != options["user"]
                    or identity["read_only"] != "on"):
                raise PreflightError("Connected database identity/read-only check failed")
            if await conn.fetchval("SELECT to_regclass('public.schema_migrations')") is None:
                raise PreflightError("Migration ledger is missing; no objects were created")
            ledger = await conn.fetch(
                "SELECT filename, checksum, success FROM public.schema_migrations")
            columns = await conn.fetch(
                "SELECT c.relname AS table_name, a.attname AS column_name, "
                "format_type(a.atttypid, a.atttypmod) AS data_type, a.attnotnull AS not_null "
                "FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
                "JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relkind IN ('r','p') "
                "AND c.relname=ANY($1::text[]) AND a.attnum>0 AND NOT a.attisdropped",
                sorted({table for table, _ in REQUIRED_COLUMNS}),
            )
            return compare_contract(checksums, ledger, columns)
    finally:
        await conn.close(timeout=5)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--expected-host", required=True)
    parser.add_argument("--expected-port", required=True, type=int)
    parser.add_argument("--expected-database", required=True)
    parser.add_argument("--expected-user", required=True)
    parser.add_argument("--migrations-dir", type=Path,
                        default=Path(__file__).resolve().parents[1] / "migrations")
    parser.add_argument("--release-mode", action="store_true",
                        help="Verify packaged payload and refuse inherited config overrides")
    parser.add_argument("--expected-env-sha256", help="Required in release mode; pins approved config bytes")
    args = parser.parse_args(argv)
    try:
        release_root = None
        if args.release_mode:
            release_root = Path(__file__).resolve().parents[1]
            verify_release(release_root)
            if (args.migrations_dir != release_root / "migrations"
                    or os.getenv("SLOMIX_ENV_FILE") != str(args.env_file)
                    or file_hash(args.env_file) != args.expected_env_sha256):
                raise PreflightError("Release migration/config paths do not match startup contract")
            refuse_config_overrides(
                read_external_environment(args.env_file, root=release_root,
                                          expected_digest=args.expected_env_sha256), os.environ)
        options = connection_options(args.env_file, (
            args.expected_host, args.expected_port, args.expected_database, args.expected_user),
            release_root=release_root, expected_digest=args.expected_env_sha256)
        checksums = migration_checksums(args.migrations_dir)
        report = asyncio.run(inspect_database(options, checksums))
        print(json.dumps(report, sort_keys=True))
        return 0 if report["clean"] else 1
    except PreflightError as error:
        print(json.dumps({"clean": False, "error": str(error)}))
    except Exception:
        # Driver/parser/OS messages may contain credentials or environment data.
        print(json.dumps({"clean": False, "error": "Preflight could not complete safely"}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
