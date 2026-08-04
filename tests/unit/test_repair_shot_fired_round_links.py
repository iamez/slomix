# ruff: noqa: SLF001

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import scripts.repair_shot_fired_round_links as repair


def test_sync_driver_receives_canonical_dbname(monkeypatch):
    """get_connection_kwargs() hands back the asyncpg/psycopg2 spelling
    ("database"); psycopg 3 only accepts the libpq keyword and errors on the
    other, so the fallback import path needs the translation."""
    connect = Mock(return_value=object())
    monkeypatch.setattr(repair, "_pg", SimpleNamespace(connect=connect))
    monkeypatch.setattr(
        repair,
        "get_connection_kwargs",
        lambda: {
            "host": "db.example",
            "port": 5432,
            "database": "etlegacy",
            "user": "etlegacy_user",
            "password": "secret",
        },
    )

    repair._connect()

    connect.assert_called_once_with(
        host="db.example",
        port=5432,
        dbname="etlegacy",
        user="etlegacy_user",
        password="secret",
    )


def test_survey_verifies_the_sibling_link_against_rounds():
    """A unanimous sibling link can still be a stale one — proximity rows can
    point at the wrong round (that is what the relinker's mismatch leg exists
    to catch), so the candidate must be checked against the rounds row it names
    before being copied onto the orphans."""
    sql = " ".join(repair._SURVEY_SQL.split())

    assert "LEFT JOIN rounds r" in sql
    for predicate in (
        "r.id = s.round_id",
        "r.round_number = o.round_number",
        "r.round_start_unix = o.round_start_unix",
        "LOWER(TRIM(r.map_name)) = LOWER(TRIM(o.map_name))",
    ):
        assert predicate in sql, predicate
    # Unverified candidates must not survive into resolved_round_id.
    assert "s.distinct_round_ids = 1 AND r.id IS NOT NULL" in sql


def test_survey_does_not_require_the_dates_to_match():
    """round_linker relaxes the date filter on purpose: a round starting 23:5x
    is stored under the NEXT day's round_date while proximity recorded the
    previous one. Requiring equality here would report correctly-linked
    midnight rounds as stale. round_start_unix already pins the round to the
    second, so the date would add no safety — only false negatives."""
    sql = " ".join(repair._SURVEY_SQL.split())
    assert "r.round_date" not in sql


def test_survey_covers_dangling_links():
    """A third damaged state: round_id naming a rounds row that no longer
    exists. migration 055 created the column with no foreign key, and
    postgresql_database_manager.py:3021 deletes rounds on a date-range reimport
    while its STEP 2 clears player/weapon stats but no proximity table — so the
    rows keep pointing at deleted ids, and ON CONFLICT DO NOTHING means
    reimport never rewrites them.

    The LEFT JOIN is what makes this reachable at all: under an inner join a
    dangling row has no `cur` and drops silently out of the survey."""
    sql = " ".join(repair._SURVEY_SQL.split())
    assert "LEFT JOIN rounds cur ON cur.id = sf.round_id" in sql
    assert "sf.round_id IS NOT NULL AND cur.id IS NULL" in sql
    assert "AS dangling_rows" in sql


def test_apply_covers_dangling_links():
    sql = " ".join(repair._APPLY_SQL.split())
    assert "NOT EXISTS (SELECT 1 FROM rounds cur WHERE cur.id = sf.round_id)" in sql


def test_survey_requires_unanimous_siblings():
    """Siblings split across two round_ids mean the round itself is
    mis-linked; picking one of them would launder that into shot_fired."""
    sql = " ".join(repair._SURVEY_SQL.split())
    assert "COUNT(DISTINCT round_id) AS distinct_round_ids" in sql


def test_survey_covers_stale_links_not_just_nulls():
    """A wrong non-NULL round_id is the worse of the two damaged states: a NULL
    drops the row out of round-scoped analytics, a stale link attributes those
    shots to another round and corrupts it. Both went unrepaired for the same
    reason, so both must be surveyed."""
    sql = " ".join(repair._SURVEY_SQL.split())
    assert "sf.round_id IS NULL OR" in sql
    assert "sf.round_start_unix != cur.round_start_unix" in sql


def test_apply_predicate_mirrors_the_survey_predicate():
    """The write set must be exactly what the survey counted. A looser
    predicate (`round_id IS DISTINCT FROM`) would also rewrite rows linked to a
    different round starting at the same second, or whose linked round has a
    NULL round_start_unix — rows the survey does not call damaged, so they
    would be committed without appearing in --expect-repairable-rows."""
    sql = " ".join(repair._APPLY_SQL.split())
    assert "sf.round_id IS DISTINCT FROM" not in sql
    # One branch per damaged state, matching _SURVEY_SQL's three.
    assert "sf.round_id IS NULL" in sql
    assert "NOT EXISTS (SELECT 1 FROM rounds cur WHERE cur.id = sf.round_id)" in sql
    assert "cur.round_start_unix != sf.round_start_unix" in sql


def test_apply_rolls_back_when_the_write_set_differs_from_the_survey():
    """--expect-repairable-rows only bounds anything if the actual rowcount is
    checked against it before COMMIT."""
    source = Path(repair.__file__).read_text()
    assert "if written != repairable_rows:" in source
    assert "conn.rollback()" in source


def test_survey_row_fields_match_the_select_list():
    """SurveyRow is built with SurveyRow(*row), so a field added to the SELECT
    without a matching field here silently shifts every later one. That is not
    hypothetical: adding stale_rows moved resolved_round_id from position 5 to
    6 while the apply loop still read 5, which would have written row COUNTS
    into round_id."""
    select = repair._SURVEY_SQL.split("SELECT o.session_date")[1].split("FROM orphans")[0]
    select = "o.session_date" + select
    # Split on top-level commas only: CASE/COALESCE and the parenthesized
    # boolean all contain commas of their own.
    columns, depth, current = [], 0, ""
    for ch in select:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            columns.append(current)
            current = ""
        else:
            current += ch
    columns.append(current)
    columns = [c.strip() for c in columns if c.strip()]

    assert len(columns) == len(repair.SurveyRow._fields), (
        f"SELECT has {len(columns)} columns, SurveyRow has "
        f"{len(repair.SurveyRow._fields)}"
    )


def test_apply_reads_the_round_id_by_name():
    """The write must take resolved_round_id, never a positional index."""
    source = Path(repair.__file__).read_text()
    assert '"round_id": r.resolved_round_id' in source


def test_expect_db_is_bound_to_the_server_not_just_the_name(monkeypatch, capsys):
    """dev and prod are both called 'etlegacy' (.env.example and the Docker
    defaults use that name), so a name-only guard would pass on production
    while the operator believed they had preview-checked dev."""
    monkeypatch.setattr(
        repair,
        "get_target_dsn_parts",
        lambda: {"host": "prod.example", "port": "5432", "database": "etlegacy"},
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "repair_shot_fired_round_links.py",
            "--apply",
            "--expect-repairable-rows=1",
            "--expect-db=localhost:5432/etlegacy",
        ],
    )

    assert repair.main() == 1
    assert "ABORT" in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv",
    [
        ["--apply"],
        ["--apply", "--expect-db=localhost:5432/etlegacy"],
        ["--apply", "--expect-repairable-rows=1"],
    ],
)
def test_apply_refuses_without_both_expectations(monkeypatch, argv):
    """--apply must restate what the dry run reported: a candidate set that
    shifted between preview and apply is no longer what the operator
    approved, and the wrong database is the other way this goes badly."""
    monkeypatch.setattr("sys.argv", ["repair_shot_fired_round_links.py", *argv])

    with pytest.raises(SystemExit) as exc:
        repair.main()

    assert exc.value.code == 2  # argparse.error()
