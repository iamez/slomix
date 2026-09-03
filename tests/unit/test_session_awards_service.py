"""The session awards roll-up (stats 2.0) — every engine award has a rule,
and the rule is what decides the winner, not a blind SUM."""
from __future__ import annotations

from bot.endstats_parser import KNOWN_AWARDS
from website.backend.services.session_awards_service import (
    AWARD_RULES,
    IPOD_MIN_PLAYED_PCT,
    computed_awards,
    format_value,
    group_by_category,
    numeric_of,
    roll_up,
    rule_for,
)

#: Every award name observed in round_awards on 2026-09-03 (44). A new engine
#: award that is not here still rolls up (rule_for falls back) — but a name
#: here without an explicit rule means we forgot to decide how it ranks.
OBSERVED = [
    "Longest killing spree", "Most deaths", "Most damage given", "Most damage received", "Most headshots",
    "Most bullets fired", "Most playtime denied", "Most light weapon kills", "Most team damage given",
    "Most team damage received", "Longest death spree", "Highest light weapons accuracy",
    "Highest headshot accuracy", "Most corpse gibs", "Most headshot kills", "Most kill assists",
    "Most selfkills", "Most revives", "Most revived", "Best K/D ratio", "Most objectives stolen",
    "Most kills per minute", "Most killsteals", "Full respawn king", "Most grenade kills",
    "Least time dead (What spawn?)", "Most pistol kills", "Most dynamites planted", "Most teamkills",
    "Most multikills", "Quickest multikill w/ light weapons", "Most doublekills", "Most sniper kills",
    "Most rifle kills", "Most MG42 kills", "Most objectives returned", "Most dynamites defused",
    "Most air support kills", "Most MG42 deaths", "Tank/Meatshield (Refuses to die)",
    "Farthest riflenade kill", "Most riflenade kills", "Most mine kills", "Most knife kills",
]


def test_every_observed_and_declared_award_has_an_explicit_rule():
    missing = [a for a in OBSERVED if a not in AWARD_RULES]
    assert missing == []
    declared_missing = [a for a in KNOWN_AWARDS if a not in AWARD_RULES]
    assert declared_missing == []


def test_an_unknown_award_still_rolls_up_under_its_own_name():
    rule = rule_for("Most teabags")
    assert rule.nickname == "Most teabags" and rule.category == "other" and rule.mode == "sum"


def test_ratios_and_percentages_take_the_best_round_never_a_sum():
    rows = [
        ("Best K/D ratio", "alpha", "AAAAAAAA", "2.33", 2.33),
        ("Best K/D ratio", "alpha", "AAAAAAAA", "2.5", 2.5),
        ("Best K/D ratio", "bravo", "BBBBBBBB", "3.1", 3.1),
    ]
    (won,) = roll_up(rows)
    # alpha's SUM (4.83) would beat bravo; the rule is max, so bravo wins.
    assert won["player"] == "bravo" and won["value_numeric"] == 3.1 and won["value"] == "3.10"


def test_least_time_dead_ranks_ascending_and_formats_as_percent():
    rows = [
        ("Least time dead (What spawn?)", "alpha", "AAAAAAAA", "12.01 percent, 1.44 min", 12.01),
        ("Least time dead (What spawn?)", "bravo", "BBBBBBBB", "5.21 percent, 1.2 min", 5.21),
        ("Least time dead (What spawn?)", "bravo", "BBBBBBBB", "9.0 percent, 1.0 min", 9.0),
    ]
    (won,) = roll_up(rows)
    assert won["player"] == "bravo" and won["value_numeric"] == 5.21
    assert won["value"] == "5.2 %"  # not an m:ss clock
    assert won["rounds_won"] == 2


def test_counts_sum_and_playtime_denied_is_a_clock():
    rows = [
        ("Most playtime denied", "alpha", "AAAAAAAA", "184 seconds", 184.0),
        ("Most playtime denied", "alpha", "AAAAAAAA", "167 seconds", 167.0),
        ("Most playtime denied", "bravo", "BBBBBBBB", "300 seconds", 300.0),
        ("Most damage given", "bravo", "BBBBBBBB", "4075", 4075.0),
        ("Most damage given", "bravo", "BBBBBBBB", "13064", 13064.0),
    ]
    by = {a["engine_name"]: a for a in roll_up(rows)}
    assert by["Most playtime denied"]["player"] == "alpha"
    assert by["Most playtime denied"]["value"] == "5:51"
    assert by["Most playtime denied"]["nickname"] == "Warden"
    assert by["Most damage given"]["value"] == "17 139"
    assert by["Most damage given"]["sentence"] == "The Damage Dealer award goes to bravo for most damage given — 17 139"


def test_tank_ratio_is_read_out_of_the_text_the_parser_could_not():
    assert numeric_of("Tank/Meatshield (Refuses to die)", "Damage received vs death ratio: 3.34x", None) == 3.34
    rows = [
        ("Tank/Meatshield (Refuses to die)", "alpha", "AAAAAAAA", "Damage received vs death ratio: 3.07x", None),
        ("Tank/Meatshield (Refuses to die)", "bravo", "BBBBBBBB", "Damage received vs death ratio: 3.34x", None),
    ]
    (won,) = roll_up(rows)
    assert won["player"] == "bravo" and won["value"] == "3.34"


def test_quickest_multikill_keeps_the_engine_text_because_the_number_is_the_kill_count():
    rows = [
        ("Quickest multikill w/ light weapons", "alpha", "AAAAAAAA", "3 kills in 0.62s", 3.0),
        ("Quickest multikill w/ light weapons", "alpha", "AAAAAAAA", "4 kills in 1.10s", 4.0),
    ]
    (won,) = roll_up(rows)
    assert won["value"] == "4 kills in 1.10s" and won["unit"] == "kills"


def test_ties_break_on_rounds_won_then_name():
    rows = [
        ("Most revives", "bravo", "BBBBBBBB", "3", 3.0),
        ("Most revives", "alpha", "AAAAAAAA", "2", 2.0),
        ("Most revives", "alpha", "AAAAAAAA", "1", 1.0),
    ]
    (won,) = roll_up(rows)
    assert won["player"] == "alpha" and won["rounds_won"] == 2


def test_name_only_rows_group_by_name_and_keep_guid_null():
    rows = [("Most deaths", "^1charlie", None, "20", 20.0), ("Most deaths", "^1charlie", None, "9", 9.0)]
    (won,) = roll_up(rows)
    assert won["guid"] is None and won["rounds_won"] == 2 and won["value_numeric"] == 29.0


def test_computed_awards_gate_ipod_on_playtime_and_skip_when_no_one_played():
    players = [
        {"guid": "A", "name": "alpha", "kills": 40, "deaths": 30, "played_pct": 98.0},
        {"guid": "B", "name": "bravo", "kills": 12, "deaths": 2, "played_pct": IPOD_MIN_PLAYED_PCT - 1},
        {"guid": "C", "name": "charlie", "kills": 25, "deaths": 20, "played_pct": 100.0},
    ]
    by = {a["engine_name"]: a for a in computed_awards(players)}
    assert by["Top Fragger"]["player"] == "alpha"
    # bravo has the fewest deaths but left early — charlie takes the iPod.
    assert by["iPod"]["player"] == "charlie"
    assert by["Playtime"]["player"] == "charlie" and by["Playtime"]["value"] == "100.0 %"
    assert computed_awards([]) == []


def test_categories_come_in_the_fixed_order_with_labels():
    rows = [("Most deaths", "a", "AAAAAAAA", "1", 1.0), ("Most revives", "b", "BBBBBBBB", "1", 1.0)]
    cats = group_by_category(computed_awards([{"guid": "A", "name": "a", "kills": 1, "deaths": 1, "played_pct": 100.0}]) + roll_up(rows))
    assert [c["key"] for c in cats] == ["computed", "teamwork", "deaths"]
    assert cats[-1]["label"] == "deaths & mayhem"


def test_format_value_units():
    assert format_value(184, "seconds") == "3:04"
    assert format_value(44.72, "percent") == "44.7 %"
    assert format_value(30.94, "metres") == "30.9 m"
    assert format_value(17139, "count") == "17 139"
    assert format_value(None, "count", text="n/a") == "n/a"
