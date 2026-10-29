"""Explicit declarations agree with source names; legacy absence stays unbound."""

import pytest

from shared.runtime_proximity_identity import proximity_header_identity
from tests.unit.test_runtime_round_identity import FIRST, SECOND


@pytest.mark.parametrize('identity', [FIRST, SECOND])
def test_header_roundtrip_and_legacy_absence(identity):
    name = f'2026-10-08-120000-sw_goldrush_te-round-{identity.round_number}_engagements.txt'
    lines = ['# map=sw_goldrush_te', f'# round={identity.round_number}']
    assert proximity_header_identity(lines, name) is None
    lines.append('# runtime_identity=' + identity.encode())
    assert proximity_header_identity(iter(lines), name) == identity


@pytest.mark.parametrize('change', [
    'duplicate_id', 'duplicate_map', 'duplicate_round', 'missing_map', 'missing_round',
    'wrong_map', 'wrong_half', 'malformed_id', 'malformed_header', 'wrong_filename',
])
def test_conflicting_or_malformed_declaration_never_becomes_legacy(change):
    name = '2026-10-08-120000-supply-round-1_engagements.txt'
    lines = ['# map=supply', '# round=1', '# runtime_identity=' + FIRST.encode()]
    if change.startswith('duplicate_'):
        index = {'duplicate_id': 2, 'duplicate_map': 0, 'duplicate_round': 1}[change]
        # A declaration following a data section must still be detected.
        lines += ['[PLAYER_TRACKS]', 'synthetic record', lines[index]]
    elif change.startswith('missing_'):
        lines.pop(0 if change == 'missing_map' else 1)
    elif change == 'wrong_map':
        lines[0] = '# map=oasis'
    elif change == 'wrong_half':
        lines[1] = '# round=2'
    elif change == 'malformed_id':
        lines[2] = '# runtime_identity=unknown'
    elif change == 'malformed_header':
        lines[2] = '# runtime_identity ' + FIRST.encode()
    else:
        name = name.replace('round-1', 'round-2')
    with pytest.raises(ValueError):
        proximity_header_identity(iter(lines), name)
