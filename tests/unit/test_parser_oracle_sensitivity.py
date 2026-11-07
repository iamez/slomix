"""Negative controls prove the file-to-parser assertions reject bad outcomes."""

import copy
from types import SimpleNamespace

import pytest

from bot.community_stats_parser import C0RNP0RN3StatsParser
from tests.integration.test_stats_parser_integration import (
    TestStatsParserIntegration as _Contract,
)
from tests.integration.test_stats_parser_integration import (
    test_explicit_local_corpus_is_not_silent_success as _corpus_contract,
)
from tests.integration.test_stats_parser_integration import (
    write_round_pair,
)


@pytest.mark.parametrize("fault", ["failed", "empty", "cumulative", "headshots", "revives", "stale_name"])
def test_r2_contract_rejects_plausible_regressions(tmp_path, fault):
    pair = write_round_pair(tmp_path)
    parser = C0RNP0RN3StatsParser(allow_legacy_r1_fallback=False)
    result = copy.deepcopy(parser.parse_stats_file(str(pair[1])))
    _Contract().test_parse_round_2_with_independent_oracle(
        SimpleNamespace(parse_stats_file=lambda path: result), pair)
    if fault == "failed":
        result["success"] = False
    elif fault == "empty":
        result["players"] = []
        result["total_players"] = 0
    elif fault == "cumulative":
        result["players"][0]["kills"] = 10
    elif fault == "headshots":
        result["players"][0]["headshots"] = 8
    elif fault == "revives":
        result["players"][0]["objective_stats"]["revives_given"] = 3
    else:
        result["players"][0]["name"] = "Before"
    broken = SimpleNamespace(parse_stats_file=lambda path: result)
    with pytest.raises(AssertionError):
        _Contract().test_parse_round_2_with_independent_oracle(broken, pair)


@pytest.mark.parametrize("bad", [{}, {"success": True}, {"success": False}])
def test_missing_file_contract_rejects_incomplete_or_success_reply(tmp_path, bad):
    broken = SimpleNamespace(parse_stats_file=lambda path: bad)
    with pytest.raises((AssertionError, KeyError)):
        _Contract().test_missing_file_has_explicit_error_contract(broken, tmp_path)


@pytest.mark.parametrize("bad", [{"success": False}, {"success": True, "players": []}])
def test_requested_corpus_failure_cannot_silently_continue(tmp_path, monkeypatch, bad):
    write_round_pair(tmp_path)
    monkeypatch.setenv("SLOMIX_PARSER_CORPUS", str(tmp_path))
    monkeypatch.setattr(C0RNP0RN3StatsParser, "parse_stats_file", lambda self, path: bad)
    with pytest.raises(AssertionError):
        _corpus_contract()


def test_requested_valid_synthetic_corpus_is_actually_evaluated(tmp_path, monkeypatch):
    write_round_pair(tmp_path)
    monkeypatch.setenv("SLOMIX_PARSER_CORPUS", str(tmp_path))
    _corpus_contract()
