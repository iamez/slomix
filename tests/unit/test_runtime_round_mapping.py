"""Explicit bounded stats mapping inputs and strict admission before any DB."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.community_stats_parser import C0RNP0RN3StatsParser
from bot.runtime_completed_import import import_completed_round
from bot.runtime_round_mapping import StatsRoundBinding
from tests.unit.test_runtime_identity_contract import FIRST, SECOND
from tests.unit.test_runtime_identity_import import completed_identity_pair


def first_binding():
    return StatsRoundBinding(FIRST, '1' * 32, '2026-09-25-120000-supply-round-1.txt', 100, 'a' * 64, 'supply')


@pytest.mark.parametrize('changes', [
    {'identity': None}, {'size': True}, {'size': 0}, {'size': 8388609},
    {'sha256': 'a' * 63}, {'generation': 'g' * 32}, {'generation': None},
    {'filename': '../file'}, {'filename': '2026-09-25-120000-supply-round-2.txt'},
    {'map_name': 'oasis'}, {'map_name': 'invalid/name'}, {'first': first_binding()},
])
def test_invalid_binding_rejected(changes):
    with pytest.raises(ValueError):
        replace(first_binding(), **changes)


@pytest.mark.parametrize('first', [None, {}, replace(first_binding(), identity=replace(FIRST, match_id='f' * 32))])
def test_second_requires_matching_explicit_first(first):
    with pytest.raises(ValueError):
        StatsRoundBinding(SECOND, '2' * 32, '2026-09-25-120000-supply-round-2.txt', 100, 'b' * 64, 'supply', first)


async def test_expected_identity_rejected_before_manager_even_in_default_mode(tmp_path):
    first, _ = completed_identity_pair(tmp_path)
    manager = SimpleNamespace(parser=C0RNP0RN3StatsParser(), process_file=AsyncMock())
    with pytest.raises(ValueError, match='disagrees with expected'):
        await import_completed_round(manager, first, expected_identity=replace(FIRST, match_id='f' * 32))
    manager.process_file.assert_not_awaited()


@pytest.mark.parametrize('line_ending', [b'\n', b'\r\n'])
async def test_strict_mapping_delivers_exact_frozen_dependency(tmp_path, line_ending):
    first, second = completed_identity_pair(tmp_path, line_ending=line_ending)
    manager = SimpleNamespace(parser=C0RNP0RN3StatsParser(), process_file=AsyncMock(return_value=(True, 'fixture')))
    await import_completed_round(manager, second, first=first, expected_identity=SECOND)
    binding = manager.process_file.call_args.kwargs['runtime_binding']
    assert binding.identity == SECOND and binding.first.identity == FIRST
    assert (binding.sha256, binding.generation, binding.size) == (second.sha256, second.generation, second.size)
    assert (binding.first.sha256, binding.first.filename) == (first.sha256, first.filename)
