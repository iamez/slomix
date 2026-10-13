"""No-data geometry checks must never claim that player alignment passed."""

import json

import pytest

from scripts import verify_map_geometry as verifier


@pytest.mark.asyncio
@pytest.mark.parametrize('case,expected', [
    ('missing_mesh', 1), ('no_positions', 1), ('no_maps', 1),
    ('unsupported', 1), ('supported', 0), ('quarter_missing', 0),
    ('over_quarter_missing', 1), ('all_high', 1),
])
async def test_verdict_names_its_evidence(tmp_path, monkeypatch, capsys, case, expected):
    (tmp_path / 'manifest.json').write_text(json.dumps({
        'maps': {} if case == 'no_maps' else {'fixture': {'available': True}},
    }))
    if case != 'missing_mesh':
        (tmp_path / 'fixture.json').write_text(json.dumps({
            'vertices': [0, 0, 0, 100, 0, 0, 0, 100, 0], 'indexes': [0, 1, 2],
        }))

    async def init():
        pass

    async def sample(_db, _map, _limit):
        if case == 'no_positions':
            return []
        if case == 'quarter_missing':
            return [(10, 10, 24)] * 3 + [(1000, 1000, 24)]
        if case == 'over_quarter_missing':
            return [(10, 10, 24)] * 2 + [(1000, 1000, 24)]
        if case == 'all_high':
            return [(10, 10, 200)]
        return [(1000, 1000, 24)] if case == 'unsupported' else [(10, 10, 24)]

    monkeypatch.setattr(verifier, 'init_db_pool', init)
    monkeypatch.setattr(verifier, 'get_db_pool', lambda: None)
    monkeypatch.setattr(verifier, 'sample_positions', sample)
    monkeypatch.setattr('sys.argv', ['verify_map_geometry', '--geometry', str(tmp_path)])
    assert await verifier.main() == expected
    output = capsys.readouterr().out
    if expected:
        assert '✅' not in output
    else:
        assert 'poravnava ni potrjena' in output
