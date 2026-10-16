"""Opt-in identity rejection before canonical importer/database access."""

import hashlib
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.community_stats_parser import C0RNP0RN3StatsParser
from bot.runtime_completed_import import CompletedRoundInput, import_completed_round
from shared.runtime_completion_manifest import record_completion_once
from shared.runtime_source_reservation import reserve_source_generation
from shared.runtime_spool import publish_stats_file
from tests.unit.test_runtime_identity_contract import FIRST, SECOND


def completed_identity_pair(root, declarations=None, *, line_ending=b'\n'):
    root.mkdir(mode=0o700, exist_ok=True)
    root.chmod(0o700)
    declarations = declarations if declarations is not None else [FIRST.encode(), SECOND.encode()]
    inputs = []
    for number, declared in enumerate(declarations, 1):
        filename = f'2026-09-25-120000-supply-round-{number}.txt'
        header = f'x\\supply\\x\\{number}\\2\\1\\20:00\\10:00\\600000'.encode()
        if declared is not None:
            header += b'\\' + (declared.encode() if isinstance(declared, str) else declared)
        raw = header + f'\n12345678\\Player\\1\\1\\1 {number} {number} {number} {number} {number}\n'.encode()
        raw = raw.replace(b'\n', line_ending)
        digest, generation = hashlib.sha256(raw).hexdigest(), str(number) * 32
        directory = reserve_source_generation(root, generation)
        publish_stats_file(directory, filename, [raw], expected_size=len(raw), expected_sha256=digest)
        record_completion_once(directory, dict(version=1, filename=filename, bytes=len(raw), state='writer_closed'),
                               expected_sha256=digest)
        inputs.append(CompletedRoundInput(root, generation, filename, len(raw), digest))
    return inputs


@pytest.mark.parametrize('declarations', [
    [None, None], [FIRST.encode(), None], [None, SECOND.encode()],
    [FIRST.encode(), replace(SECOND, source_id='other').encode()],
    [FIRST.encode(), replace(SECOND, match_id='d' * 32).encode()],
    [FIRST.encode(), replace(SECOND, first_round_id='d' * 32).encode()],
    [FIRST.encode(), SECOND.encode().replace('v1:', 'v2:')],
    [FIRST.encode(), SECOND.encode().encode().replace(b'fixture', b'fi\xffxture')],
])
async def test_declared_pair_rejected_before_importer(tmp_path, declarations):
    first, second = completed_identity_pair(tmp_path, declarations)
    manager = SimpleNamespace(parser=C0RNP0RN3StatsParser(), process_file=AsyncMock())
    with pytest.raises(ValueError):
        await import_completed_round(manager, second, first=first, require_declared_identity=True)
    manager.process_file.assert_not_called()


@pytest.mark.parametrize('declared', [None, '', FIRST.encode().replace('v1:', 'v2:'),
    SECOND.encode(), FIRST.encode().encode().replace(b'fixture', b'fi\xffxture')])
async def test_declared_first_half_rejected_before_importer(tmp_path, declared):
    first, _ = completed_identity_pair(tmp_path, [declared, SECOND.encode()])
    manager = SimpleNamespace(parser=C0RNP0RN3StatsParser(), process_file=AsyncMock())
    with pytest.raises(ValueError):
        await import_completed_round(manager, first, require_declared_identity=True)
    manager.process_file.assert_not_called()


@pytest.mark.parametrize('required,declarations', [(True, None), (False, [None, None])])
async def test_actual_parser_preserved_on_opt_in_and_legacy(tmp_path, required, declarations):
    first, second = completed_identity_pair(tmp_path, declarations)
    parsed = []

    async def process(path, *, input_source):
        parsed.append(input_source.parse(None))
        assert input_source.read_bytes()
        return True, path.name

    manager = SimpleNamespace(parser=C0RNP0RN3StatsParser(), process_file=process)
    assert (await import_completed_round(manager, first, require_declared_identity=required))[0]
    assert (await import_completed_round(manager, second, first=first, require_declared_identity=required))[0]
    assert [row['round_num'] for row in parsed] == [1, 2]
    assert parsed[1]['r1_filename'] == first.filename
    assert parsed[1]['match_summary']['players']


@pytest.mark.parametrize('policy', [None, 'true', 1])
async def test_policy_type_rejected_before_io(policy):
    with pytest.raises(ValueError, match='boolean'):
        await import_completed_round(None, None, require_declared_identity=policy)
