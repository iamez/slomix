#!/usr/bin/env python3
"""usage_report.py — the missing consumption loop (FIX 2, root cause).

Every audit of this project keeps finding the same shape of decay: surfaces
that are produced but never consumed (dead commands, dead API routes, dead
columns) and values that drift outside their declared scale with nothing
ever complaining (accuracy 1000%, push_quality 2.16, 8-round players atop
the rating ladder). The production loops (CI, tests, ledger) are healthy;
there is no CONSUMPTION loop. This script is that loop.

Read-only by construction: every DB statement is a SELECT; filesystem access
is read-only. Run it ad hoc or from cron; it prints a sectioned report and
exits 0 (it is a report, not a gate — pair sections with tests when a rule
should become blocking, like tests/unit/test_round_id_coverage_contract.py).

Sections (each independently skippable on missing inputs):
  1. commands   — registered bot commands vs. calls seen in logs/commands.log
                  (NOTE: log liveness itself is under investigation, FIX 4a —
                  treat "0 calls" as provisional until a live !ping confirms)
  2. api        — HTTP paths seen in logs/access.log vs. registered routers
  3. bounds     — *_pct/*_score/*_quality/*_efficiency/*_ratio columns whose
                  MIN/MAX violate their declared scale
  4. deadfields — numeric columns that are all-zero across every row
  5. samples    — rating tables ranking tiny-sample players above
                  large-sample ones (no shrinkage)
  6. coverage   — tables with a round_id column missing from
                  LINKAGE_INVENTORY_TABLES (the shot_fired class of loss)

Canary (2026-08-11): on the pre-fix database this report MUST reproduce
FIX 3 (accuracy_pct > 100), FIX 7 (push_quality > 1), FIX 8 (skill sample
spread), FIX 9 (uncovered round_id tables) and FIX 13 (escort/vehicle
all-zero spatial columns). If it cannot find known-present defects, the
report is broken, not the system.
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import asyncpg
except ImportError:  # pragma: no cover
    asyncpg = None


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _env(*names: str, default: str = "") -> str:
    for n in names:
        v = os.getenv(n)
        if v:
            return v
    return default


async def _connect():
    if asyncpg is None:
        raise RuntimeError("asyncpg missing")
    ssl_mode = _env("POSTGRES_SSL_MODE", default="disable")
    ssl_arg: object = False
    if ssl_mode and ssl_mode != "disable":
        import ssl as _ssl

        ctx = _ssl.create_default_context(
            cafile=_env("POSTGRES_SSL_ROOT_CERT", default="") or None
        )
        if ssl_mode == "require":  # require = šifriranje brez verifikacije
            ctx.check_hostname = False
            ctx.verify_mode = _ssl.CERT_NONE
        ssl_arg = ctx
    return await asyncpg.connect(
        host=_env("POSTGRES_HOST", "DB_HOST", default="127.0.0.1"),
        port=int(_env("POSTGRES_PORT", "DB_PORT", default="5432")),
        database=_env("POSTGRES_DATABASE", "DB_NAME", default="etlegacy"),
        user=_env("POSTGRES_USER", "DB_USER", default="etlegacy_user"),
        password=_env("POSTGRES_PASSWORD", "DB_PASSWORD", default=""),
        timeout=10,
        command_timeout=120,
        ssl=ssl_arg,
    )


def _section(title: str) -> None:
    print(f"\n{'=' * 70}\n== {title}\n{'=' * 70}")


# --------------------------------------------------------------------------
# 1. commands: registered vs. called
# --------------------------------------------------------------------------

_CMD_DECORATOR = re.compile(r"^(?:commands?\.)?(?:command|group)$")


def _registered_commands() -> dict[str, list[str]]:
    """name -> aliases, from AST over bot/cogs (same source of truth the
    COMMANDS.md regenerator walks)."""
    found: dict[str, list[str]] = {}
    for path in sorted((ROOT / "bot" / "cogs").rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for deco in node.decorator_list:
                if not isinstance(deco, ast.Call):
                    continue
                if not _CMD_DECORATOR.match(ast.unparse(deco.func)):
                    continue
                name = node.name
                aliases: list[str] = []
                for kw in deco.keywords:
                    if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                        name = str(kw.value.value)
                    if kw.arg == "aliases" and isinstance(kw.value, (ast.List, ast.Tuple)):
                        aliases = [
                            str(e.value)
                            for e in kw.value.elts
                            if isinstance(e, ast.Constant)
                        ]
                found[name] = aliases
    return found


def report_commands(days: int) -> None:
    _section(f"1. BOT KOMANDE — registrirane vs. klicane (zadnjih {days} dni)")
    registered = _registered_commands()
    log_dir = Path(os.getenv("BOT_LOG_DIR") or (ROOT / "logs"))
    log_path = log_dir / "commands.log"
    if not log_path.exists():
        print(f"{log_path} ne obstaja — sekcija preskočena")
        return

    cutoff = datetime.now().astimezone() - timedelta(days=days)
    calls: Counter[str] = Counter()
    newest: datetime | None = None
    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?!(\w+)", line)
        if not m:
            continue
        ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").astimezone()
        newest = max(newest or ts, ts)
        if ts >= cutoff:
            calls[m.group(2)] += 1

    alias_to_name = {a: n for n, als in registered.items() for a in als}
    used: Counter[str] = Counter()
    for cmd, cnt in calls.items():
        used[alias_to_name.get(cmd, cmd)] += cnt

    unused = sorted(n for n in registered if used.get(n, 0) == 0)
    print(f"registriranih: {len(registered)} · klicanih (≥1): {len([n for n in registered if used.get(n)])}")
    if newest:
        print(f"zadnji vpis v commands.log: {newest} "
              f"{'⚠️ (starejši od okna — log morda ne teče, glej FIX 4a)' if newest < cutoff else ''}")
    print(f"NEKLICANE ({len(unused)}): {', '.join(unused) or '—'}")
    top = used.most_common(5)
    if top:
        print("top 5: " + ", ".join(f"!{n}×{c}" for n, c in top))


# --------------------------------------------------------------------------
# 2. api: registered routes vs. access.log traffic
# --------------------------------------------------------------------------

_ROUTE_DECO = re.compile(r"@router\.(get|post|put|delete|patch)\(\s*[\"']([^\"']+)")
_PREFIX_RE = re.compile(r"include_router\(([\w.]+)\.router(?:,\s*prefix=[\"']([^\"']*)[\"'])?")


def _registered_routes() -> set[str]:
    """Approximate route table: decorator paths joined with main.py prefixes.
    ⚠️ prefiks je obvezen del ključa — brez njega je primerjava nesmisel
    (pravilo §1.5 iz FIX_ME: to je napako že enkrat proizvedlo)."""
    main_path = ROOT / "website" / "backend" / "main.py"
    routers_dir = ROOT / "website" / "backend" / "routers"
    if not main_path.exists() or not routers_dir.is_dir():
        return set()
    prefixes: dict[str, str] = {}
    main_py = main_path.read_text(encoding="utf-8")
    for m in _PREFIX_RE.finditer(main_py):
        module = m.group(1).split(".")[-1]
        prefixes[module] = m.group(2) or ""

    routes: set[str] = set()
    for path in sorted(routers_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        prefix = prefixes.get(path.stem, "/api")
        for m in _ROUTE_DECO.finditer(text):
            routes.add(prefix + m.group(2))
    return routes


def _normalize_api_path(path: str) -> str:
    path = path.split("?")[0]
    path = re.sub(r"/\d+(?=/|$)", "/{id}", path)
    path = re.sub(r"/[0-9a-fA-F]{16,}(?=/|$)", "/{guid}", path)
    path = re.sub(r"/\d{4}-\d{2}-\d{2}(?=/|$)", "/{date}", path)
    return path


def report_api() -> None:
    _section("2. API POTI — registrirane vs. promet (access.log)")
    log_path = ROOT / "logs" / "access.log"
    if not log_path.exists():
        print("logs/access.log ne obstaja — sekcija preskočena")
        return
    routes = _registered_routes()
    if not routes:
        print("website/backend ni na voljo — sekcija preskočena")
        return
    seen: Counter[str] = Counter()
    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.search(r"(?:GET|POST|PUT|DELETE|PATCH)\s+(/\S+)", line)
        if m:
            seen[_normalize_api_path(m.group(1))] += 1

    def _match(route: str) -> int:
        pattern = re.sub(r"\\\{[^}]+\\\}", "[^/]+", re.escape(route))
        rx = re.compile(f"^{pattern}$")
        return sum(c for p, c in seen.items() if rx.match(p))

    unused = sorted(r for r in routes if _match(r) == 0)
    print(f"registriranih poti (heuristika AST+prefiks): {len(routes)} · "
          f"videnih normaliziranih poti v logu: {len(seen)}")
    print(f"POTI BREZ PROMETA ({len(unused)}):")
    for r in unused[:40]:
        print(f"  {r}")
    if len(unused) > 40:
        print(f"  … in še {len(unused) - 40}")


# --------------------------------------------------------------------------
# 3. bounds + 4. deadfields + 5. samples + 6. coverage (DB)
# --------------------------------------------------------------------------

_BOUND_RULES = (
    (re.compile(r"_pct$"), 0.0, 100.0),
    (re.compile(r"(_score|_quality|_efficiency|_ratio)$"), 0.0, 1.0),
)

_BOUND_EXEMPT = {
    # Deklarirano ne-[0,1] po pregledu — dopolnjuj Z RAZLOGOM.
    ("player_skill_ratings", "et_rating"),  # odprta skala
    ("player_comprehensive_stats", "kd_ratio"),  # kills/deaths, odprta skala
    # time_dead_ratio: znan artefakt R2 kumulative — poizvedbe uporabljajo
    # LEAST-cap workaround (bot/services/CLAUDE.md), surova vrednost ni [0,1]
    ("player_comprehensive_stats", "time_dead_ratio"),
    ("matchup_history", "lineup_a_score"),  # število map, ne delež
    ("matchup_history", "lineup_b_score"),  # število map, ne delež
    ("session_results", "team_1_score"),  # število map, ne delež
    ("session_results", "team_2_score"),  # število map, ne delež
}


async def report_bounds(conn) -> None:
    _section("3. MEJE — polja zunaj deklarirane lestvice")
    cols = await conn.fetch(
        """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND data_type IN ('smallint', 'integer', 'real', 'double precision', 'numeric', 'bigint')
          AND column_name ~ '(_pct|_score|_quality|_efficiency|_ratio)$'
        ORDER BY table_name, column_name
        """
    )
    violations = 0
    for row in cols:
        table, col = row["table_name"], row["column_name"]
        if (table, col) in _BOUND_EXEMPT:
            continue
        rule = next((r for r in _BOUND_RULES if r[0].search(col)), None)
        if not rule:
            continue
        _, lo, hi = rule
        stats = await conn.fetchrow(
            f'SELECT MIN("{col}") AS lo, MAX("{col}") AS hi, '
            f'COUNT(*) FILTER (WHERE "{col}" < $1 OR "{col}" > $2) AS out_n '
            f'FROM "{table}"',  # nosec B608 — identifiers from information_schema
            lo, hi,
        )
        if stats and stats["out_n"]:
            violations += 1
            print(f"  ⚠️ {table}.{col}: min={stats['lo']} max={stats['hi']} "
                  f"→ {stats['out_n']} vrstic zunaj [{lo}, {hi}]")
    if not violations:
        print("  ✓ nič kršitev")


async def report_deadfields(conn) -> None:
    _section("4. MRTVA POLJA — numerični stolpci, ki so povsod 0")
    cols = await conn.fetch(
        """
        SELECT c.table_name, c.column_name
        FROM information_schema.columns c
        JOIN information_schema.tables t
          ON t.table_name = c.table_name AND t.table_schema = 'public'
        WHERE c.table_schema = 'public'
          AND t.table_type = 'BASE TABLE'
          AND (c.table_name LIKE 'proximity_%' OR c.table_name = 'combat_engagement')
          AND c.data_type IN ('smallint', 'integer', 'real', 'double precision', 'numeric', 'bigint')
          AND c.column_name NOT IN ('id', 'round_id')
        """
    )
    dead = 0
    for row in cols:
        table, col = row["table_name"], row["column_name"]
        stats = await conn.fetchrow(
            f'SELECT COUNT(*) AS n, MIN("{col}") AS lo, MAX("{col}") AS hi '
            f'FROM "{table}"'  # nosec B608 — identifiers from information_schema
        )
        if stats and stats["n"] and stats["n"] >= 50 and stats["lo"] == 0 and stats["hi"] == 0:
            dead += 1
            print(f"  ⚠️ {table}.{col}: {stats['n']} vrstic, vse 0 — se servira kot podatek?")
    if not dead:
        print("  ✓ nič mrtvih polj")


async def report_samples(conn) -> None:
    _section("5. LESTVICE — sample-size brez korekcije")
    try:
        rows = await conn.fetch(
            """
            SELECT display_name AS player_name, et_rating, games_rated
            FROM player_skill_ratings
            ORDER BY et_rating DESC
            """
        )
    except asyncpg.UndefinedTableError:
        print("  player_skill_ratings ne obstaja — preskočeno")
        return
    if not rows:
        print("  prazna tabela — preskočeno")
        return
    flagged = 0
    for i, row in enumerate(rows):
        n_small = int(row["games_rated"] or 0)
        if n_small >= 20:
            continue
        for below in rows[i + 1:]:
            if int(below["games_rated"] or 0) > 500:
                flagged += 1
                print(f"  ⚠️ '{row['player_name']}' ({n_small} enot, rating {row['et_rating']}) "
                      f"nad '{below['player_name']}' ({below['games_rated']} enot, {below['et_rating']})")
                break
    ns = sorted(int(r["games_rated"] or 0) for r in rows)
    print(f"  razpon vzorca: {ns[0]} → {ns[-1]} (faktor ×{(ns[-1] / max(ns[0], 1)):.0f}), "
          f"igralcev: {len(rows)}")
    if not flagged:
        print("  ✓ noben majhen vzorec ne prehiteva velikih")


async def report_coverage(conn) -> None:
    _section("6. round_id POKRITOST — tabele izven LINKAGE_INVENTORY_TABLES")
    from bot.services.linkage_inventory_service import LINKAGE_INVENTORY_TABLES
    rows = await conn.fetch(
        """
        SELECT c.table_name
        FROM information_schema.columns c
        JOIN information_schema.tables t
          ON t.table_name = c.table_name AND t.table_schema = 'public'
        WHERE c.table_schema = 'public'
          AND t.table_type = 'BASE TABLE'
          AND c.column_name = 'round_id'
        ORDER BY 1
        """
    )
    have_round_id = {r["table_name"] for r in rows}
    covered = set(LINKAGE_INVENTORY_TABLES)
    missing = sorted(have_round_id - covered - {"rounds"})
    print(f"  tabel z round_id: {len(have_round_id)} · v inventarju: {len(covered)}")
    if missing:
        for t in missing:
            n = await conn.fetchval(
                f'SELECT COUNT(*) FROM "{t}" WHERE round_id IS NULL'  # nosec B608
            )
            print(f"  ⚠️ {t}: NI v inventarju ({n} NULL round_id vrstic)")
    else:
        print("  ✓ vse pokrite")


# --------------------------------------------------------------------------

async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=30, help="okno za commands sekcijo")
    parser.add_argument(
        "--sections",
        default="commands,api,bounds,deadfields,samples,coverage",
        help="katere sekcije (privzeto vse)",
    )
    args = parser.parse_args()
    if args.days < 0:
        parser.error("--days ne sme biti negativen")
    wanted = {s.strip() for s in args.sections.split(",")}

    print(f"usage_report — {datetime.now().astimezone():%Y-%m-%d %H:%M} — potrošna zanka (FIX 2)")

    if "commands" in wanted:
        report_commands(args.days)
    if "api" in wanted:
        report_api()

    db_sections = wanted & {"bounds", "deadfields", "samples", "coverage"}
    if db_sections:
        try:
            conn = await _connect()
        except Exception as exc:
            print(f"\nDB nedosegljiva ({exc}) — DB sekcije preskočene")
            return 0
        try:
            if "bounds" in wanted:
                await report_bounds(conn)
            if "deadfields" in wanted:
                await report_deadfields(conn)
            if "samples" in wanted:
                await report_samples(conn)
            if "coverage" in wanted:
                await report_coverage(conn)
        finally:
            await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
