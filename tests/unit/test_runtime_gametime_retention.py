"""Admission errors cannot touch storage; no DB or Discord required."""

import hashlib
import json

import pytest

from bot.runtime_gametime_retention import retain_gametime_source
from tests.unit.test_runtime_gametime_source import NAME, document


@pytest.mark.parametrize('source', ['UPPER', ':legacy', '', None, 'x' * 65, 'é', 'a\n'])
async def test_source_identity_rejects_before_descriptor_or_database(source):
    with pytest.raises(ValueError, match='lowercase configured source ID'):
        await retain_gametime_source(None, -1, source_id=source, generation='a' * 32,
                                    filename=NAME, expected_size=1, expected_sha256='a' * 64)


@pytest.mark.parametrize('fault', ['hash', 'generation', 'filename', 'projection'])
async def test_real_descriptor_validation_rejects_before_database(tmp_path, fault):
    data = document()
    if fault == 'projection':
        data['meta']['actual_duration_seconds'] = 599
    raw = json.dumps(data).encode()
    path = tmp_path / 'synthetic-gametime'
    path.write_bytes(raw)
    args = dict(source_id='fixture-server', generation='a' * 32, filename=NAME,
                expected_size=len(raw), expected_sha256=hashlib.sha256(raw).hexdigest())
    if fault == 'hash':
        args['expected_sha256'] = '0' * 64
    elif fault == 'generation':
        args['generation'] = '../escape'
    elif fault == 'filename':
        args['filename'] = NAME.replace('supply', 'oasis')
    with path.open('rb') as stream, pytest.raises(ValueError):
        await retain_gametime_source(None, stream.fileno(), **args)
