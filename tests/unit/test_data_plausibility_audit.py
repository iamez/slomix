"""scripts/data_plausibility_audit.py — Data Trust pillar B rulebook sanity.

Two layers:
1. The rules table itself is well-formed (unique names, valid tiers/
   severities/tables) — pure Python, always runs.
2. Every rule's SQL predicate at least PARSES against the real schema
   (LIMIT 0 query) — DB-dependent, skipped cleanly when unreachable so this
   suite doesn't become a hidden DB requirement for `pytest tests/unit`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.data_plausibility_audit import (  # noqa: E402
    PROVENANCE_CUTOFF,
    RULES,
    TREND_RULES,
    VALID_SEVERITIES,
    VALID_TABLES,
    VALID_TIERS,
    MonthlyPoint,
    Rule,
    TrendResult,
    TrendRule,
    build_count_sql,
    build_split_sql,
    build_top_rows_sql,
    build_trend_sql,
    find_shifts,
    get_connection,
    live_boundary,
    unexplained_shift_count,
    validate_rules,
    validate_trend_rules,
)
from shared.round_time import round_duration_sql  # noqa: E402


def test_rules_table_is_well_formed():
    """validate_rules() must accept the real RULES list as-is."""
    validate_rules(RULES)  # raises on any structural problem


def test_rule_names_are_unique():
    names = [r.name for r in RULES]
    assert len(names) == len(set(names)), "duplicate rule names in RULES"


def test_rule_tiers_and_severities_are_valid():
    for rule in RULES:
        assert rule.tier in VALID_TIERS, rule.name
        assert rule.severity in VALID_SEVERITIES, rule.name
        assert rule.table in VALID_TABLES, rule.name


def test_rule_predicates_are_nonempty_strings():
    for rule in RULES:
        assert isinstance(rule.predicate, str)
        assert rule.predicate.strip(), f"{rule.name} has an empty predicate"


def test_rounds_table_rules_never_need_round_join():
    """needs_round_join is a pcs-only concept — the rounds table is already `r`."""
    for rule in RULES:
        if rule.table == "rounds":
            assert not rule.needs_round_join, rule.name


def test_at_least_one_rule_per_table():
    tables = {r.table for r in RULES}
    assert tables == VALID_TABLES, f"expected rules covering {VALID_TABLES}, got {tables}"


def test_validate_rules_rejects_duplicate_names():
    import dataclasses

    bad = list(RULES[:2])
    bad[1] = dataclasses.replace(bad[1], name=bad[0].name)
    with pytest.raises(ValueError, match="Duplicate rule names"):
        validate_rules(bad)


def test_validate_rules_rejects_invalid_severity():
    import dataclasses

    bad = [dataclasses.replace(RULES[0], severity="apocalyptic")]
    with pytest.raises(ValueError, match="invalid severity"):
        validate_rules(bad)


def test_sql_builders_produce_nonempty_statements():
    """Cheap, DB-free check that every builder returns a SELECT for every rule."""
    for rule in RULES:
        assert build_count_sql(rule).strip().upper().startswith("SELECT COUNT(*)")
        assert build_split_sql(rule).strip().upper().startswith("SELECT")
        sql, labels = build_top_rows_sql(rule, 3)
        assert sql.strip().upper().startswith("SELECT")
        assert labels, rule.name


# ── DB-dependent: predicates must actually PARSE against the schema ────────


def _try_connect():
    # get_connection() raises SystemExit (not an Exception subclass) when the
    # POSTGRES_* env vars are absent — exactly the CI situation — so catching
    # bare Exception is not enough for the "skip cleanly without a DB" promise.
    try:
        conn = get_connection()
    except (Exception, SystemExit):
        return None
    return conn


@pytest.fixture(scope="module")
def db_conn():
    conn = _try_connect()
    if conn is None:
        pytest.skip("Database unreachable — skipping DB-dependent plausibility-audit tests")
    yield conn
    conn.close()


@pytest.mark.parametrize("rule", RULES, ids=[r.name for r in RULES])
def test_rule_predicate_parses_against_schema(db_conn, rule):
    """Run each rule's count/split/top-rows SQL as `... LIMIT 0` (no rows read,
    still forces the planner to resolve every column/cast/regex in the
    predicate). A rule that references a renamed column or a bad cast fails
    here instead of silently reporting 0 violations forever in production.
    """
    with db_conn.cursor() as cur:
        cur.execute(build_count_sql(rule))
        cur.execute(build_split_sql(rule))
        sql, _labels = build_top_rows_sql(rule, 0)  # LIMIT 0 — plan/parse only, no rows
        cur.execute(sql)


# ── Duration doctrine (PR #770): actual_time is a TARGET, not a measurement ──


def _rule(name: str):
    for rule in RULES:
        if rule.name == name:
            return rule
    raise AssertionError(f"rule {name!r} disappeared from RULES")


def test_tps_rule_measures_duration_through_shared_round_time():
    """The row-vs-round duration rule must compare against the MEASURED
    duration (shared.round_time), never against the bare stopwatch target.

    Reading actual_time as a duration overstated ~15% of rounds (RCA
    2026-08-18); a rule built on it would have quietly excused rows that
    played longer than the round actually lasted.
    """
    predicate = _rule("pcs_tps_exceeds_round_duration").predicate
    assert "actual_duration_seconds" in predicate, "rule ignores the Lua measurement"
    # Strip every occurrence of the shared expression (the predicate names it
    # twice: once to require a known duration, once to compare against it) —
    # whatever is left must not touch actual_time on its own.
    assert "actual_time" not in predicate.replace(round_duration_sql("r"), ""), (
        "rule references actual_time outside the shared round_duration_sql fallback"
    )
    assert round_duration_sql("r") in predicate, "rule does not use shared.round_time SQL"
    assert f'{round_duration_sql("r")} > 0' in predicate, (
        "rule must skip rounds of unknown duration instead of treating 0s as a real round"
    )


def test_actual_time_rules_still_target_actual_time_itself():
    """The two rounds-table rules are ABOUT the header clock — they must keep
    reading actual_time directly, or the audit stops watching the field whose
    lie started all of this."""
    for name in ("rounds_actual_time_missing_or_nonpositive", "rounds_actual_time_diverges_without_surrender"):
        assert "actual_time" in _rule(name).predicate, name


# ---------------------------------------------------------------------------
# "Known, under repair" — rules that fire on purpose
#
# Three of today's four new time rules report real, already-tracked breakage.
# Without a way to say so they would hold the exit code non-zero until the
# repairs land, and a sensor that is always red stops being read -- which is
# how the NEXT problem hides. `Rule.acknowledged` is that way to say so.
# ---------------------------------------------------------------------------

from dataclasses import dataclass  # noqa: E402

from scripts.data_plausibility_audit import (  # noqa: E402
    unacknowledged_live_count,
)


@dataclass
class _Result:
    rule: object
    live: int


def _fake_rule(name, acknowledged=""):
    """A throwaway Rule for exercising the exit-code logic.

    NB: not `_rule` -- that name is already taken above by the lookup helper
    that finds a real rule in RULES. Two different things under one name is
    exactly the confusion this rulebook exists to catch.
    """
    return Rule(name=name, table="player_comprehensive_stats", tier="T1",
                severity="critical", predicate="TRUE", note="n",
                acknowledged=acknowledged)


def test_acknowledged_rules_do_not_hold_the_exit_code_open():
    results = [
        _Result(_fake_rule("known", acknowledged="tracked in #886. Remove once live is 0."), 4682),
        _Result(_fake_rule("also_known", acknowledged="tracked. Remove once live is 0."), 30),
        _Result(_fake_rule("clean"), 0),
    ]
    assert unacknowledged_live_count(results) == 0


def test_an_unacknowledged_live_rule_still_breaks_the_exit_code():
    """The mechanism must not become a way to silence everything."""
    results = [
        _Result(_fake_rule("known", acknowledged="tracked. Remove once live is 0."), 4682),
        _Result(_fake_rule("new_problem"), 1),
    ]
    assert unacknowledged_live_count(results) == 1


def test_every_acknowledgement_names_what_closes_it():
    """An acknowledgement with no exit condition is a mute, and a mute is how
    five months go by. Each one has to say what makes it removable."""
    for rule in RULES:
        if not rule.acknowledged:
            continue
        assert "Remove" in rule.acknowledged, (
            f"{rule.name}: acknowledgement does not say what closes it")
        assert len(rule.acknowledged) > 60, (
            f"{rule.name}: acknowledgement is too short to carry a reason")


def test_the_time_field_rules_are_present():
    """These four are the ones the 23-rule audit could not see: it checked
    whether values were possible, never whether they were written, and had no
    rule for dead time at all."""
    names = {r.name for r in RULES}
    for expected in ("pcs_time_played_percent_is_zero",
                     "pcs_time_dead_exceeds_time_played",
                     "pcs_time_dead_ratio_out_of_range",
                     "pcs_time_dead_inconsistent_with_ratio"):
        assert expected in names, f"{expected} is missing"


def test_the_consistency_rule_is_r1_only_and_stays_green():
    """R2 diverges by design -- the parser recomputes time_dead_ratio after the
    differential while the minutes are taken raw, so ~8% of live R2 rows differ
    legitimately. A blanket rule would report 263 correct rows as broken."""
    rule = next(r for r in RULES if r.name == "pcs_time_dead_inconsistent_with_ratio")
    assert "pcs.round_number = 1" in rule.predicate
    assert not rule.acknowledged, (
        "this rule was calibrated to land green (live R1 max deviation 1.70 "
        "against a 2.0 threshold); acknowledging it would hide a real hit")


@pytest.mark.parametrize(
    "rule", [r for r in RULES if r.acknowledged], ids=lambda r: r.name)
def test_no_acknowledgement_has_outlived_its_reason(db_conn, rule):
    """When the repair lands and the live count reaches zero, the
    acknowledgement is stale and has to go -- otherwise a future recurrence of
    the same breakage would be silently excused."""
    # build_split_sql, not build_count_sql: the latter returns a single
    # COUNT(*) and reading a "live" column out of it silently yields nothing,
    # which this test would then report as "the acknowledgement is stale" --
    # a wrong verdict rather than an error.
    with db_conn.cursor() as cur:
        cur.execute(build_split_sql(rule))
        row = cur.fetchone()
    assert row is not None and len(row) == 3, (
        f"build_split_sql changed shape ({row!r}); this test cannot judge "
        f"{rule.name} until it is updated")
    live = int(row[2])
    assert live > 0, (
        f"{rule.name} no longer fires on live rows. Its acknowledgement has "
        f"outlived its reason -- remove it so a recurrence is reported again.")


# ── Distribution shifts (the aggregate rule class) ───────────────────────────
#
# The detector is a pure function over a monthly series, so most of it is
# tested on hand-built series -- including the shapes this database does not
# contain, and the one it no longer contains because #886 repaired it.


def _pt(month, value, rows=500):
    return MonthlyPoint(month=month, rows=rows, value=value)


def _trend(**kw):
    base = dict(name="t", statistic="AVG(pcs.kills)", threshold_pct=25.0, note="n")
    base.update(kw)
    return TrendRule(**base)


def test_a_quiet_series_never_reports_a_shift():
    """The measured shape of the control metrics: months wobble a few percent
    around each other for years and nothing is wrong."""
    rule = _trend(threshold_pct=20.0)
    series = [_pt(f"2026-{m:02d}", v) for m, v in
              enumerate([1.00, 1.03, 0.98, 1.02, 0.97, 1.01, 1.04], start=1)]
    assert find_shifts(rule, series) == []


def test_a_step_change_is_reported_with_its_size():
    """The 2026-04 shape: a level that moves once and stays moved."""
    rule = _trend(threshold_pct=25.0)
    series = [_pt("2026-01", 0.35), _pt("2026-02", 0.34), _pt("2026-03", 0.36),
              _pt("2026-04", 0.19)]
    shifts = find_shifts(rule, series)
    assert [s.month for s in shifts] == ["2026-04"]
    assert shifts[0].kind == "moved"
    assert shifts[0].baseline == pytest.approx(0.35)
    assert shifts[0].change_pct == pytest.approx(-45.7, abs=0.1)


def test_a_field_that_starts_being_written_is_an_appearance_not_a_percentage():
    """revives_given is 0 on all 5,538 rows before 2025-12 and non-zero on 653
    of 982 in it. "0 -> 0.18" has no percentage; calling it +inf% would be a
    number where a state change belongs."""
    rule = _trend()
    series = [_pt("2025-01", 0.0), _pt("2025-02", 0.0), _pt("2025-03", 0.0),
              _pt("2025-04", 0.18)]
    shifts = find_shifts(rule, series)
    assert [(s.month, s.kind, s.change_pct) for s in shifts] == [("2025-04", "appeared", None)]


def test_a_statistic_that_becomes_undefined_is_reported_as_vanished():
    """Absent is a third state, distinct from zero and from a value. A month
    whose statistic is NULL (every row NULL, or every denominator zero) is not
    a quiet month -- it is a month that could not be measured at all."""
    rule = _trend()
    series = [_pt("2026-01", 1.0), _pt("2026-02", 1.0), _pt("2026-03", 1.0),
              _pt("2026-04", None)]
    shifts = find_shifts(rule, series)
    assert [(s.month, s.kind) for s in shifts] == [("2026-04", "vanished")]


def test_zero_that_stays_zero_is_not_an_appearance():
    """The companion to the appearance test: a metric that is simply not
    collected yet must stay silent, or every such rule is red from birth."""
    rule = _trend()
    series = [_pt(f"2025-{m:02d}", 0.0) for m in range(1, 6)]
    assert find_shifts(rule, series) == []


def test_a_month_too_small_to_measure_is_neither_measured_nor_a_baseline():
    """A month in progress is not a measurement. It must not fire, and -- the
    half that is easy to forget -- it must not drag the next month's baseline
    either."""
    rule = _trend(threshold_pct=25.0, min_rows=200)
    series = [_pt("2026-01", 1.0), _pt("2026-02", 1.0), _pt("2026-03", 1.0),
              _pt("2026-04", 0.10, rows=12),   # two sessions in: wild, and tiny
              _pt("2026-05", 1.0)]
    shifts = find_shifts(rule, series)
    assert shifts == [], "a sub-threshold month must be skipped, not judged"
    # And it left no trace: 2026-05 is compared against 1.0, not against a
    # baseline poisoned by the 0.10.
    shifts = find_shifts(rule, [*series, _pt("2026-06", 0.5)])
    assert [s.month for s in shifts] == ["2026-06"]
    assert shifts[0].baseline == pytest.approx(1.0)


def test_a_shift_cannot_fire_before_a_full_lookback_exists():
    """With less history than `lookback`, there is no baseline -- and no
    baseline means no verdict, not a default one."""
    rule = _trend(lookback=3, threshold_pct=10.0)
    series = [_pt("2026-01", 1.0), _pt("2026-02", 5.0), _pt("2026-03", 0.1)]
    assert find_shifts(rule, series) == []


def test_the_median_baseline_absorbs_a_single_outlier_month():
    """Why the baseline is a median of three and not last month's value: one
    freak month must not make the next two months look broken."""
    rule = _trend(lookback=3, threshold_pct=25.0)
    series = [_pt("2026-01", 1.0), _pt("2026-02", 1.0), _pt("2026-03", 4.0),
              _pt("2026-04", 1.0)]
    assert find_shifts(rule, series) == []


def test_a_known_shift_is_matched_by_its_month_and_carries_its_explanation():
    rule = _trend(threshold_pct=25.0, known_shifts=(("2026-04", "the Lua fix"),))
    series = [_pt("2026-01", 0.35), _pt("2026-02", 0.34), _pt("2026-03", 0.36),
              _pt("2026-04", 0.19), _pt("2026-05", 0.19)]
    shifts = find_shifts(rule, series)
    by_month = {s.month: s.explanation for s in shifts}
    assert by_month["2026-04"] == "the Lua fix"
    # The echo month is a separate shift and is NOT covered by its neighbour's
    # explanation -- each month has to be named on its own.
    assert by_month.get("2026-05") == ""


def test_an_unexplained_shift_breaks_the_exit_code_and_an_explained_one_does_not():
    series = [_pt("2026-01", 0.35), _pt("2026-02", 0.34), _pt("2026-03", 0.36),
              _pt("2026-04", 0.19)]
    naked = _trend(name="naked", threshold_pct=25.0)
    named = _trend(name="named", threshold_pct=25.0,
                   known_shifts=(("2026-04", "the Lua fix"),))
    results = [TrendResult(rule=r, series=series, shifts=find_shifts(r, series))
               for r in (naked, named)]
    assert unexplained_shift_count(results) == 1
    assert unexplained_shift_count(results[1:]) == 0


def test_an_acknowledged_trend_rule_does_not_hold_the_exit_code_open():
    """Same contract as Rule.acknowledged: a rule whose whole reason for
    firing is written down and already being repaired stays visible in the
    report but does not colour the sensor red."""
    series = [_pt("2026-01", 1.0), _pt("2026-02", 1.0), _pt("2026-03", 1.0),
              _pt("2026-04", 0.0)]
    rule = _trend(threshold_pct=10.0, acknowledged="#885 lands, then this stops")
    result = TrendResult(rule=rule, series=series, shifts=find_shifts(rule, series))
    assert result.unexplained, "the shift is still detected and still reported"
    assert unexplained_shift_count([result]) == 0


def test_the_trend_rules_table_is_well_formed():
    validate_trend_rules(TREND_RULES)


@pytest.mark.parametrize("bad", [
    _trend(statistic="  "),
    _trend(threshold_pct=0.0),
    _trend(lookback=0),
    _trend(min_rows=0),
    _trend(known_shifts=(("2026-4", "malformed month"),)),
    _trend(known_shifts=(("2026-04", "   "),)),
    _trend(known_shifts=(("2026-04", "a"), ("2026-04", "b"))),
])
def test_validate_trend_rules_rejects_a_malformed_rule(bad):
    with pytest.raises(ValueError):
        validate_trend_rules([bad])


def test_every_trend_statistic_is_robust_to_the_rows_the_row_rules_catch():
    """A trend rule must not be movable by the very rows the per-row rules
    exist to report. Measured on this database: the ratio-of-sums version of
    the dead-time share calls 2025-12 a +96% move; the median calls it +14%.
    The whole difference is a handful of impossible rows (largest
    time_dead_minutes that month: 580, in a round that lasted seven).

    So every statistic here is either a median (an outlier cannot pull it) or
    a proportion of rows (bounded in [0, 1] by construction). A SUM would pass
    review and fail in the field.
    """
    for rule in TREND_RULES:
        robust = ("percentile_cont" in rule.statistic
                  or ("AVG(CASE WHEN" in rule.statistic and "1.0 ELSE 0.0" in rule.statistic))
        assert robust, (
            f"{rule.name}: statistic is neither a median nor a proportion — "
            f"one impossible row can move it: {rule.statistic}")


def test_the_dead_time_share_rule_names_the_month_it_was_built_for():
    """2026-04 is the month the Lua fix landed and 23 per-row rules saw
    nothing. If it ever stops being named here, this rule has lost its
    provenance."""
    rule = next(r for r in TREND_RULES if r.name == "pcs_dead_time_share_monthly")
    assert "2026-04" in dict(rule.known_shifts)


@pytest.mark.parametrize("rule", TREND_RULES, ids=[r.name for r in TREND_RULES])
def test_trend_statistic_parses_against_schema(db_conn, rule):
    with db_conn.cursor() as cur:
        cur.execute(build_trend_sql(rule) + " LIMIT 0")


@pytest.mark.parametrize(
    "rule", [r for r in TREND_RULES if r.known_shifts], ids=lambda r: r.name)
def test_every_known_shift_still_fires(db_conn, rule):
    """A known shift is an explanation attached to a month. If the month stops
    firing, the explanation is describing something that is no longer there --
    which is exactly what happens the day we rewrite that history (the phase-3
    reconstruction in docs/PLAN.md rewrites pre-2026-04 dead times). Fail then,
    loudly, rather than carry a note about a shift that no longer exists.
    """
    with db_conn.cursor() as cur:
        cur.execute(build_trend_sql(rule))
        series = [MonthlyPoint(month=str(m), rows=int(n), value=None if v is None else float(v))
                  for m, n, v in cur.fetchall()]
    fired = {s.month for s in find_shifts(rule, series)}
    named = {m for m, _ in rule.known_shifts}
    assert named <= fired, (
        f"{rule.name}: known_shifts names {sorted(named - fired)}, which no "
        f"longer fire. Either the data changed under us or the entry was "
        f"never right — re-measure and update the rulebook.")


@pytest.mark.parametrize("rule", TREND_RULES, ids=[r.name for r in TREND_RULES])
def test_the_live_database_carries_no_unexplained_shift(db_conn, rule):
    """The sensor's steady state. A failure here is the point of the whole
    class: some monthly statistic moved and nobody has written down why."""
    with db_conn.cursor() as cur:
        cur.execute(build_trend_sql(rule))
        series = [MonthlyPoint(month=str(m), rows=int(n), value=None if v is None else float(v))
                  for m, n, v in cur.fetchall()]
    unexplained = [s for s in find_shifts(rule, series) if not s.explanation]
    assert not unexplained or rule.acknowledged, (
        f"{rule.name}: unexplained shift(s) "
        + ", ".join(f"{s.month} ({s.kind}"
                    + (f", {s.change_pct:+.1f}%)" if s.change_pct is not None else ")")
                    for s in unexplained))


@pytest.mark.parametrize(
    "rule", [r for r in TREND_RULES if r.acknowledged], ids=lambda r: r.name)
def test_no_trend_acknowledgement_has_outlived_its_reason(db_conn, rule):
    """The mirror of the per-row stale check. An acknowledgement on a rule
    that no longer fires is not caution — it is a mute left armed over a
    healthy sensor, ready to swallow the next, unrelated break."""
    with db_conn.cursor() as cur:
        cur.execute(build_trend_sql(rule))
        series = [MonthlyPoint(month=str(m), rows=int(n), value=None if v is None else float(v))
                  for m, n, v in cur.fetchall()]
    assert [s for s in find_shifts(rule, series) if not s.explanation], (
        f"{rule.name} carries no unexplained shift any more — its "
        f"acknowledgement has outlived its reason, remove it.")


# ── Arming: muting the past without muting the rule ─────────────────────────


def _armed(name="a", armed_from="2026-04-01", acknowledged=""):
    return Rule(name=name, table="player_comprehensive_stats", tier="T1",
                severity="critical", predicate="pcs.kills < 0", note="n",
                armed_from=armed_from, acknowledged=acknowledged)


def test_live_boundary_is_the_later_of_the_two_dates():
    assert live_boundary(_armed(armed_from="")) == PROVENANCE_CUTOFF
    assert live_boundary(_armed(armed_from="2026-04-01")) == "2026-04-01"
    # An arming date before the cutover carves nothing out, and must not
    # silently WIDEN the live window back into backfill territory.
    assert live_boundary(_armed(armed_from="2020-01-01")) == PROVENANCE_CUTOFF


def test_arming_and_acknowledgement_cannot_both_be_set():
    """They do the same job by different means, and the difference is the
    whole point: acknowledged mutes the rule, arming mutes only the past.
    A rule carrying both would look armed and behave muted."""
    with pytest.raises(ValueError, match="Pick one"):
        validate_rules([_armed(acknowledged="because reasons")])


@pytest.mark.parametrize("bad", ["2026-4-1", "2026/04/01", "yesterday", "2026-04"])
def test_armed_from_must_be_an_iso_date(bad):
    with pytest.raises(ValueError, match="armed_from"):
        validate_rules([_armed(armed_from=bad)])


def test_no_time_field_rule_is_muted_any_more():
    """The three time-field rules landed acknowledged, which mutes the WHOLE
    rule: a fresh occurrence of the same breakage would have been swallowed
    along with the history the acknowledgement excused. They are armed now.
    If one of them ever goes back to `acknowledged`, that trade is being made
    again and should be argued for, not slipped in."""
    for name in ("pcs_time_played_percent_is_zero",
                 "pcs_time_dead_exceeds_time_played",
                 "pcs_time_dead_ratio_out_of_range"):
        rule = next(r for r in RULES if r.name == name)
        assert rule.armed_from, f"{name} lost its arming date"
        assert not rule.acknowledged, f"{name} is muted again"


def test_the_split_query_names_three_buckets():
    sql = build_split_sql(_armed())
    assert "AS backfill" in sql and "AS pre_arming" in sql and "AS live" in sql
    # The middle bucket is bounded on BOTH sides, or it double-counts backfill.
    assert f"< '{PROVENANCE_CUTOFF}') AS backfill" in sql
    assert f">= '{PROVENANCE_CUTOFF}'" in sql and "< '2026-04-01') AS pre_arming" in sql


@pytest.mark.parametrize("rule", RULES, ids=[r.name for r in RULES])
def test_the_three_buckets_sum_to_the_total(db_conn, rule):
    """The arming column must MOVE rows, never drop them. A bucket that does
    not add up is how a sensor quietly stops counting."""
    with db_conn.cursor() as cur:
        cur.execute(build_count_sql(rule))
        total = int(cur.fetchone()[0])
        cur.execute(build_split_sql(rule))
        row = cur.fetchone()
    assert row is not None and len(row) == 3, f"split query shape changed: {row!r}"
    assert sum(int(v) for v in row) == total, (
        f"{rule.name}: buckets {row} do not sum to {total}")


@pytest.mark.parametrize(
    "rule", [r for r in RULES if r.armed_from], ids=lambda r: r.name)
def test_an_armed_rule_carries_history_and_a_quiet_present(db_conn, rule):
    """What arming claims, measured. If `live` ever leaves zero here, the
    defect the arming date closed has come back and the sensor is doing its
    job -- fix the data, do not move the date."""
    with db_conn.cursor() as cur:
        cur.execute(build_split_sql(rule))
        backfill, pre_arming, live = (int(v) for v in cur.fetchone())
    assert pre_arming > 0, (
        f"{rule.name}: nothing before {rule.armed_from} — the arming date is "
        f"carving out nothing and should be removed")
    assert live == 0, (
        f"{rule.name}: {live} row(s) on or after {rule.armed_from}, which is "
        f"exactly what this rule is armed to catch")
