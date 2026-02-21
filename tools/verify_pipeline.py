#!/usr/bin/env python3
"""Pipeline Verification Tool (WS1-007 Gate Check)

Verifies the ET:Legacy stats pipeline is functioning end-to-end.
Checks: DB connectivity, recent rounds, R1/R2 pairing, Lua webhook
data, cross-references, and data staleness.

Usage: python tools/verify_pipeline.py
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path


def load_env():
    """Load .env file from project root if it exists."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def get_connection():
    """Get PostgreSQL connection using .env or environment variables."""
    import psycopg2

    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ.get("POSTGRES_DATABASE", "etlegacy"),
        user=os.environ.get("POSTGRES_USER", "etlegacy_user"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
    )


class PipelineVerifier:
    """Runs pipeline verification checks and reports results."""

    WARN_STALENESS_DAYS = 7
    FAIL_STALENESS_DAYS = 30

    def __init__(self):
        self.results = []
        self.conn = None

    def record(self, name, status, detail=""):
        self.results.append((name, status, detail))

    def check_db_connectivity(self):
        """Check 1: Can we connect to PostgreSQL?"""
        try:
            self.conn = get_connection()
            self.conn.autocommit = True
            cur = self.conn.cursor()
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
            cur.close()
            self.record("DB Connectivity", "PASS", version.split(",")[0])
        except Exception as e:
            self.record("DB Connectivity", "FAIL", str(e))

    def check_recent_rounds(self):
        """Check 2: Are there rounds in the DB? What's the latest?"""
        if not self.conn:
            self.record("Recent Rounds", "SKIP", "No DB connection")
            return None

        cur = self.conn.cursor()
        cur.execute(
            "SELECT COUNT(*), MAX(round_date), MAX(gaming_session_id) FROM rounds;"
        )
        count, latest_date, max_session = cur.fetchone()
        cur.close()

        if count == 0:
            self.record("Recent Rounds", "FAIL", "No rounds in database")
            return None

        self.record(
            "Recent Rounds",
            "PASS",
            f"{count} rounds, latest: {latest_date}, max session: {max_session}",
        )
        return latest_date

    def check_r1_r2_pairing(self):
        """Check 3: Do recent rounds have proper R1+R2 matches?"""
        if not self.conn:
            self.record("R1/R2 Pairing", "SKIP", "No DB connection")
            return

        cur = self.conn.cursor()
        # Check last 20 matches for R1+R2 pairing
        cur.execute("""
            SELECT match_id,
                   array_agg(DISTINCT round_number ORDER BY round_number) AS rounds
            FROM rounds
            WHERE match_id IS NOT NULL AND round_number IN (1, 2)
            GROUP BY match_id
            ORDER BY match_id DESC
            LIMIT 20;
        """)
        rows = cur.fetchall()
        cur.close()

        if not rows:
            self.record("R1/R2 Pairing", "FAIL", "No matches found with R1/R2")
            return

        paired = sum(1 for _, rounds in rows if rounds == [1, 2])
        r1_only = sum(1 for _, rounds in rows if rounds == [1])
        total = len(rows)

        status = "PASS" if paired > 0 else "WARN"
        self.record(
            "R1/R2 Pairing",
            status,
            f"{paired}/{total} recent matches fully paired, {r1_only} R1-only",
        )

    def check_lua_webhook_data(self):
        """Check 4: Is there data in lua_round_teams? What's the latest?"""
        if not self.conn:
            self.record("Lua Webhook Data", "SKIP", "No DB connection")
            return None

        cur = self.conn.cursor()
        cur.execute(
            "SELECT COUNT(*), MAX(captured_at) FROM lua_round_teams;"
        )
        count, latest_captured = cur.fetchone()
        cur.close()

        if count == 0:
            self.record("Lua Webhook Data", "WARN", "No data in lua_round_teams")
            return None

        self.record(
            "Lua Webhook Data",
            "PASS",
            f"{count} entries, latest captured: {latest_captured}",
        )
        return latest_captured

    def check_cross_reference(self):
        """Check 5: Do lua_round_teams entries match rounds table entries?"""
        if not self.conn:
            self.record("Cross-Reference", "SKIP", "No DB connection")
            return

        cur = self.conn.cursor()
        # Check lua entries that have a round_id link
        cur.execute("""
            SELECT
                COUNT(*) AS total_lua,
                COUNT(lrt.round_id) AS with_round_id,
                COUNT(r.id) AS matched_rounds
            FROM lua_round_teams lrt
            LEFT JOIN rounds r ON lrt.round_id = r.id;
        """)
        total_lua, with_round_id, matched = cur.fetchone()
        cur.close()

        if total_lua == 0:
            self.record("Cross-Reference", "WARN", "No lua data to cross-reference")
            return

        unlinked = total_lua - with_round_id
        orphaned = with_round_id - matched

        if orphaned > 0:
            status = "WARN"
            detail = (
                f"{matched}/{total_lua} linked to rounds, "
                f"{orphaned} orphaned round_id refs"
            )
        elif unlinked > 0:
            status = "PASS"
            detail = (
                f"{matched}/{total_lua} linked, "
                f"{unlinked} without round_id (may be unmatched)"
            )
        else:
            status = "PASS"
            detail = f"All {total_lua} lua entries linked to valid rounds"

        self.record("Cross-Reference", status, detail)

    def check_staleness(self, latest_round_date):
        """Check 6: How old is the newest data?"""
        if latest_round_date is None:
            self.record("Data Staleness", "FAIL", "No round data to check")
            return

        today = datetime.now().date()
        if isinstance(latest_round_date, str):
            latest_round_date = datetime.strptime(
                latest_round_date, "%Y-%m-%d"
            ).date()
        age_days = (today - latest_round_date).days

        if age_days > self.FAIL_STALENESS_DAYS:
            status = "FAIL"
        elif age_days > self.WARN_STALENESS_DAYS:
            status = "WARN"
        else:
            status = "PASS"

        self.record(
            "Data Staleness",
            status,
            f"Latest round: {latest_round_date} ({age_days} days ago)",
        )

    def run_all(self):
        """Run all checks and print report."""
        print("=" * 60)
        print("  ET:Legacy Pipeline Verification (WS1-007)")
        print(f"  Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        print()

        self.check_db_connectivity()
        latest_date = self.check_recent_rounds()
        self.check_r1_r2_pairing()
        self.check_lua_webhook_data()
        self.check_cross_reference()
        self.check_staleness(latest_date)

        if self.conn:
            self.conn.close()

        # Print results
        has_fail = False
        has_warn = False
        for name, status, detail in self.results:
            icon = {"PASS": "✓", "FAIL": "✗", "WARN": "!", "SKIP": "-"}[status]
            color_status = f"[{status}]"
            print(f"  {icon} {color_status:8s} {name}: {detail}")
            if status == "FAIL":
                has_fail = True
            if status == "WARN":
                has_warn = True

        print()
        if has_fail:
            print("RESULT: FAIL — Pipeline has critical issues")
            return 1
        elif has_warn:
            print("RESULT: PASS with warnings")
            return 0
        else:
            print("RESULT: PASS — Pipeline verified")
            return 0


def main():
    load_env()
    verifier = PipelineVerifier()
    sys.exit(verifier.run_all())


if __name__ == "__main__":
    main()
