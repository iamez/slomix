"""Generation lookup stays inside owned directory descriptors."""
import os
from contextlib import contextmanager

import pytest

from bot import runtime_timing_import_cli as cli


@pytest.mark.parametrize('fault', ['none', 'traversal', 'symlink', 'shared'])
def test_generation_directory_boundary(tmp_path, monkeypatch, fault):
    generation = 'a' * 32
    child = tmp_path / generation
    child.mkdir(mode=0o700)
    if fault == 'traversal':
        generation = '../other'
    elif fault == 'symlink':
        child.rename(tmp_path / 'real')
        child.symlink_to(tmp_path / 'real')
    elif fault == 'shared':
        child.chmod(0o755)
    seen = []

    @contextmanager
    def source(fd, fields, identity, map_name):
        seen.append(os.fstat(fd).st_ino)
        yield 'source'

    monkeypatch.setattr(cli, '_timing_source', source)
    root = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        if fault == 'none':
            with cli._generation_timing_source(root, (generation,), None, 'supply', True) as result:  # noqa: SLF001
                assert result == 'source'
                assert seen == [child.stat().st_ino]
        else:
            with (pytest.raises((ValueError, OSError)),
                  cli._generation_timing_source(root, (generation,), None, 'supply', True)):  # noqa: SLF001
                pytest.fail('Unsafe generation accepted')
            assert not seen
    finally:
        os.close(root)
