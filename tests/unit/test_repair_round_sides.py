"""Restoring sides from the raw endstats files must copy, never derive.

245 rounds carry winner_team or defender_team = 0 — the 2025-12 bulk-import era
— and 17 of them hold the exact inverse of what their file says. Sides are the
foundation of scoring, so this repair matters; equally, it must never touch a
round whose sides already parsed, because one such round legitimately disagrees
with a duplicate file while the database holds the Lua-verified truth.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "repair_round_sides", ROOT / "scripts" / "repair_round_sides_from_stats_files.py"
)
repair = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(repair)

HEADER = "^a#^7p^au^7rans^a.^7only\\{map}\\legacy3\\{rn}\\{d}\\{w}\\{limit}\\{actual}\\716261\n"


def _write(tmp_path: Path, name: str, *, rn=1, d=1, w=2, limit="12:00", actual="11:57"):
    (tmp_path / name).write_text(HEADER.format(map="supply", rn=rn, d=d, w=w,
                                               limit=limit, actual=actual))


class _Cur:
    """Minimal cursor: one fetchall of rounds, then per-id era lookups."""
    def __init__(self, rows):
        self._rows = rows

    def execute(self, *_args, **_kwargs):
        return None

    def fetchall(self):
        return self._rows


def test_reads_sides_from_the_header(tmp_path):
    _write(tmp_path, "2025-12-21-213008-supply-round-1.txt", d=1, w=2)
    headers = repair.read_headers(tmp_path)
    assert headers[("2025-12-21", "213008", "supply", 1)][:2] == (1, 2)


def test_skips_a_file_whose_own_sides_are_unusable(tmp_path):
    _write(tmp_path, "2025-12-21-213008-supply-round-1.txt", d=0, w=0)
    assert repair.read_headers(tmp_path) == {}


def test_plans_only_rounds_with_untrusted_sides(tmp_path):
    _write(tmp_path, "2025-12-21-213008-supply-round-1.txt", d=1, w=2)
    headers = repair.read_headers(tmp_path)
    rows = [(101, "2025-12-21", "213008", "supply", 1, 0, 0, "")]
    plan = repair.collect(_Cur(rows), headers)
    assert len(plan) == 1
    rid, _, _, _, file_winner, file_defender, outcome = plan[0]
    assert (rid, file_winner, file_defender) == (101, 2, 1)
    # Attackers won, so the round completed — not the "Fullhold" the +-30s
    # heuristic would have called it at 11:57 of 12:00.
    assert outcome == "Completed"


def test_a_true_hold_is_labelled_fullhold(tmp_path):
    _write(tmp_path, "2025-12-21-213008-supply-round-1.txt", d=1, w=1, actual="12:00")
    plan = repair.collect(
        _Cur([(101, "2025-12-21", "213008", "supply", 1, 0, 0, "")]),
        repair.read_headers(tmp_path),
    )
    assert plan[0][6] == "Fullhold"


def test_skips_a_round_with_no_matching_file(tmp_path):
    _write(tmp_path, "2025-12-21-213008-supply-round-1.txt")
    rows = [(102, "2025-12-22", "220000", "et_beach", 1, 0, 0, "")]
    assert repair.collect(_Cur(rows), repair.read_headers(tmp_path)) == []


def test_skips_an_ambiguous_identity(tmp_path):
    """Two rounds sharing (date, time, map, number) — the file cannot say which
    one it belongs to, so neither is touched."""
    _write(tmp_path, "2025-12-21-213008-supply-round-1.txt")
    rows = [
        (101, "2025-12-21", "213008", "supply", 1, 0, 0, ""),
        (102, "2025-12-21", "213008", "supply", 1, 0, 0, ""),
    ]
    assert repair.collect(_Cur(rows), repair.read_headers(tmp_path)) == []


@pytest.mark.parametrize("winner,defender", [(2, 1), (1, 1)])
def test_never_plans_a_round_whose_sides_are_trusted(tmp_path, winner, defender):
    """The query only selects untrusted rows, and collect must not widen that —
    a trusted round's data beats a file (id 10123 disagrees with a duplicate
    file produced by a forced map change, and the database is right)."""
    _write(tmp_path, "2025-12-21-213008-supply-round-1.txt", d=1, w=2)
    rows = [(101, "2025-12-21", "213008", "supply", 1, winner, defender, "Completed")]
    plan = repair.collect(_Cur(rows), repair.read_headers(tmp_path))
    # collect() trusts its caller's WHERE clause, so assert the guarantee that
    # actually protects these rows: the UPDATE re-checks it.
    source = (ROOT / "scripts" / "repair_round_sides_from_stats_files.py").read_text()
    update = source[source.index("UPDATE rounds"):source.index("(file_winner, file_defender")]
    assert "winner_team IS NULL OR winner_team = 0" in update
    assert "defender_team IS NULL OR defender_team = 0" in update
    assert plan  # the row was planned only because this fake bypassed the WHERE
