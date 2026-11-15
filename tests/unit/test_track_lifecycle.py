"""New source unknown is explicit, not permission to infer a death from a path."""

from unittest.mock import AsyncMock

import pytest

from proximity.parser.parser import ProximityParserV4
from tests.unit.test_proximity_boundary_metrics import boundary_track
from website.backend.services.track_lifecycle import track_end_sql


@pytest.mark.parametrize('cause', [None, 'unknown', 'shutdown', 'disconnect', 'round_end', 'future_cause'])
async def test_import_preserves_source_cause_without_rewriting_path(cause):
    parser = ProximityParserV4(db_adapter=AsyncMock())
    track = boundary_track()
    track.death_type = cause
    parser.player_tracks = [track]
    parser.metadata.update(round_num=1, map_name='supply', round_start_unix=1000)
    parser._table_has_column = AsyncMock(return_value=False)  # noqa: SLF001
    parser._append_round_link_columns = AsyncMock()  # noqa: SLF001
    await parser._import_player_tracks('2099-01-01')  # noqa: SLF001
    sql, values = parser.db_adapter.execute.call_args.args
    columns = [x.strip() for x in sql.split('(', 1)[1].split(')', 1)[0].split(',')]
    stored = dict(zip(columns, values))
    assert stored['death_type'] == cause
    assert track.death_type == cause
    assert track.path[-1].event == 'sample'


def test_lifecycle_sql_cannot_accept_untrusted_alias():
    with pytest.raises(ValueError, match='unsupported'):
        track_end_sql('malicious;')


@pytest.mark.parametrize('declared', [None, '', 'unknown', 'shutdown', 'world'])
def test_parser_distinguishes_absent_legacy_field_from_explicit_unknown(declared):
    parser = ProximityParserV4()
    fields = ['G', 'Synthetic', 'AXIS', 'MEDIC', '0', '200', '100']
    if declared is not None:
        fields.append(declared)
    fields.extend(['1', '200,1,2,3,100,0,8,0,0,world'])
    parser._parse_player_track_line(';'.join(fields))  # noqa: SLF001
    assert len(parser.player_tracks) == 1
    assert parser.player_tracks[0].death_type == (None if declared is None else declared or 'unknown')
