"""Dedicated runtime parsing must not borrow legacy or symlinked R1 files."""

import pytest

from bot.community_stats_parser import C0RNP0RN3StatsParser


@pytest.mark.parametrize('r1_stamp,r2_stamp', [
    ('2026-09-20-120000', '2026-09-20-120000'),
    ('2026-09-20-120000', '2026-09-20-121000'),
    ('2026-09-19-235500', '2026-09-20-000500'),
])
def test_strict_spool_isolation_preserves_local_matching(tmp_path, monkeypatch, r1_stamp, r2_stamp):
    """Exact, same-day and midnight selection retain matching within the spool."""
    monkeypatch.chdir(tmp_path)
    spool = tmp_path / 'spool'
    spool.mkdir()
    legacy = tmp_path / 'local_stats'
    legacy.mkdir()
    r1 = legacy / f'{r1_stamp}-map-round-1.txt'
    r1.write_text('fixture')
    r2 = spool / f'{r2_stamp}-map-round-2.txt'
    strict = C0RNP0RN3StatsParser(allow_legacy_r1_fallback=False)
    old = C0RNP0RN3StatsParser()
    assert old.find_corresponding_round_1_file(str(r2)) is not None
    assert strict.find_corresponding_round_1_file(str(r2)) is None
    link = spool / r1.name
    link.symlink_to(r1)
    assert strict.find_corresponding_round_1_file(str(r2)) is None
    link.unlink()
    link.write_text('fixture')
    assert strict.find_corresponding_round_1_file(str(r2)) == str(link)
