"""Versioned wire contract and actual Lua writer/legacy parser compatibility."""

import json
import shutil
import subprocess
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from shared.runtime_round_identity import (
    RoundIdentity,
    decode_round_identity,
    require_round_pair,
    stats_header_identity,
)

ROOT = Path(__file__).resolve().parents[2]
FIRST = RoundIdentity('fixture-server', 'a' * 32, 'b' * 32, 1, 'b' * 32)
SECOND = RoundIdentity('fixture-server', 'a' * 32, 'c' * 32, 2, 'b' * 32)
HEADER = 'x\\supply\\x\\1\\2\\1\\20:00\\10:00\\600000'


def test_roundtrip_and_dependency():
    for identity in (FIRST, SECOND):
        assert decode_round_identity(identity.encode()) == identity
    require_round_pair(FIRST, SECOND)
    with pytest.raises(FrozenInstanceError):
        FIRST.round_id = 'd' * 32


def test_consistent_copied_declarations_are_not_authentication():
    # No historical state/secret exists here: replayed or forged agreement passes.
    # Only a later trusted allocator/artifact binding can establish provenance.
    for _ in range(2):
        require_round_pair(decode_round_identity(FIRST.encode()), decode_round_identity(SECOND.encode()))


@pytest.mark.parametrize('change', [
    dict(source_id='UPPER'), dict(source_id=''), dict(source_id='x' * 65),
    dict(source_id='a:b'), dict(source_id='é'), dict(source_id='a\n'),
    dict(match_id='a' * 31), dict(match_id='A' * 32), dict(round_id=None),
    dict(round_number=True), dict(round_number=1.0), dict(round_number=0),
    dict(round_number=3), dict(round_number='1'), dict(first_round_id='c' * 32),
])
def test_invalid_values_rejected(change):
    with pytest.raises(ValueError):
        replace(FIRST, **change)


@pytest.mark.parametrize('other', [
    replace(SECOND, source_id='another-server'), replace(SECOND, match_id='d' * 32),
    replace(SECOND, first_round_id='d' * 32), FIRST, None,
])
def test_mismatched_pair_rejected(other):
    with pytest.raises(ValueError):
        require_round_pair(FIRST, other)


def test_reversed_pair_and_self_dependency_rejected():
    with pytest.raises(ValueError):
        require_round_pair(SECOND, FIRST)
    with pytest.raises(ValueError):
        replace(SECOND, first_round_id=SECOND.round_id)


@pytest.mark.parametrize('value', [None, '', 'x' * 201, FIRST.encode() + ':extra',
    FIRST.encode() + '\n', FIRST.encode().replace('v1:', 'v2:'),
    FIRST.encode().replace(':1:', ':01:'), FIRST.encode().replace(':1:', ':1.0:')])
def test_malformed_wire_never_becomes_legacy(value):
    with pytest.raises(ValueError):
        decode_round_identity(value)


@pytest.mark.parametrize('ending', ['', '\n', '\r\n'])
def test_optional_header(ending):
    assert stats_header_identity(HEADER + ending) is None
    assert stats_header_identity(HEADER.rsplit('\\', 1)[0] + ending) is None
    assert stats_header_identity(HEADER + '\\' + FIRST.encode() + ending) == FIRST


@pytest.mark.parametrize('header', [HEADER + '\\', HEADER + '\\unknown',
    HEADER + '\\' + SECOND.encode(), HEADER + '\\' + FIRST.encode() + '\\extra',
    HEADER + '\nmore', 'x' * 4097, 'x\\y', None])
def test_unsupported_header_fails(header):
    with pytest.raises(ValueError):
        stats_header_identity(header)


@pytest.fixture(params=['lua5.1', 'lua5.4'])
def lua(request):
    executable = shutil.which(request.param)
    if executable is None and request.param == 'lua5.1':
        pytest.skip('Optional Lua5.1 not installed')
    assert executable, 'Lua5.4 required for wire compatibility'
    return executable


def run_lua(lua, body):
    prelude = 'local identity = dofile(' + json.dumps(str(ROOT / 'vps_scripts/runtime_round_identity.lua')) + ')\n'
    return subprocess.run([lua, '-'], input=prelude + body, text=True,
                          capture_output=True, timeout=10, check=True).stdout


def declaration(value):
    return ("{source_id=" + json.dumps(value.source_id) + ',match_id="' + value.match_id
            + '",round_id="' + value.round_id + '",round_number=' + str(value.round_number)
            + ',first_round_id="' + value.first_round_id + '"}')


@pytest.mark.parametrize('value', [FIRST, SECOND, replace(FIRST, source_id='a' * 64)])
def test_lua_wire_matches_python(lua, value):
    output = run_lua(lua, 'io.write(identity.encode(' + declaration(value) + '))')
    assert output == value.encode()
    assert decode_round_identity(output) == value


@pytest.mark.parametrize('mutation', [
    'r.first_round_id=string.rep("d",32)', 'r.source_id="UPPER"',
    'r.round_number=true', 'r.round_number="1"', 'r.round_id=string.rep("B",32)',
    'r.extra=true', 'r.match_id=nil',
])
def test_lua_rejects_bad_contract(lua, mutation):
    output = run_lua(lua, 'local r=' + declaration(FIRST) + '\n' + mutation
                     + '\nprint(pcall(identity.encode,r))')
    assert output.startswith('false\t'), output


@pytest.mark.parametrize('header', [HEADER.rsplit('\\', 1)[0], HEADER + '\\extra',
    HEADER + '\nextra', HEADER + '\r', HEADER.replace('\\1\\2\\1', '\\2\\2\\1'), 'x' * 3801])
def test_lua_rejects_unsupported_header(lua, header):
    output = run_lua(lua, 'print(pcall(identity.append_stats_header,'
                     + json.dumps(header) + ',' + declaration(FIRST) + '))')
    assert output.startswith('false\t'), output


@pytest.mark.parametrize('ending', ['', '\n', '\r\n'])
def test_lua_header_readable_in_python(lua, ending):
    output = run_lua(lua, 'io.write(identity.append_stats_header(' + json.dumps(HEADER + ending)
                     + ',' + declaration(FIRST) + '))')
    assert stats_header_identity(output) == FIRST
    assert output == HEADER + '\\' + FIRST.encode() + '\n'


@pytest.mark.parametrize('half', [1, 2])
def test_actual_corn_writer_extension_preserves_legacy_stats(lua, tmp_path, half):
    """Transform shipped SaveStats output with fake ET bindings; real parser.

    No engine deployment, FS durability, producer trust or ID allocation claimed.
    Only one c0rn writer + one legacy reader are covered, not every old tool.
    """
    from bot.community_stats_parser import C0RNP0RN3StatsParser
    from tests.unit.test_runtime_snapshot_pair import _without_timestamps

    source = (ROOT / 'vps_scripts/c0rnp0rn8.lua').read_text()
    body = source[source.index('function SaveStats('):source.index('function et_ShutdownGame(')]
    setup = r'''
local output = {}
et = {CS_SERVERINFO=1, CS_MULTI_INFO=2, CS_MULTI_MAPWINNER=3, FS_WRITE=1}
function et.trap_GetConfigstring(v) return v end
function et.Info_ValueForKey(_, key)
    if key == 'mapname' then return 'supply' end
    return key == 'd' and '1' or '0'
end
function et.trap_Cvar_Get(key)
    if key == 'g_currentRound' then return HALF == 1 and '1' or '0' end
    if key == 'timelimit' then return '20:00' end
    if key == 'g_nextTimeLimit' then return '10:00' end
    return 'x'
end
function et.trap_FS_FOpenFile(_) output = {}; return 1 end
function et.trap_FS_Write(bytes, count, _)
    assert(count == #bytes, 'original writer byte count mismatch')
    if #output == 0 and EXTENDED then
        bytes = identity.append_stats_header(bytes, ROUND)
        count = #bytes -- Test-side transformation, NOT a deployed writer hook.
    end
    output[#output+1] = bytes:sub(1, count) -- ET honors the supplied count.
    return count
end
function et.trap_FS_FCloseFile(_) end
function et.G_LogPrint(_) end
function ConvertTimelimit(value) return value end
function isEmpty(value) return value end
max_clients=0; roundStart=1000; roundEnd=611000; pausedTime={[3]=10000}
stats={['12345678']=[[12345678\Player\1\1\1 1 1 1 1 1
]]}
os.date=function(_) return '2026-09-25-120000-' end
'''
    outputs = []
    value = FIRST if half == 1 else SECOND
    for extended in (False, True):
        code = f'HALF={half}; EXTENDED={str(extended).lower()}; ROUND={declaration(value)}\n'
        raw = run_lua(lua, code + setup + body + '\nSaveStats(); io.write(table.concat(output))')
        directory = tmp_path / str(extended)
        directory.mkdir()
        path = directory / f'2026-09-25-120000-supply-round-{half}.txt'
        path.write_text(raw)
        header = raw.splitlines()[0]
        assert stats_header_identity(header) == (value if extended else None)
        parsed = C0RNP0RN3StatsParser().parse_regular_stats_file(str(path))
        assert parsed['success'] and len(parsed['players']) == 1
        normalized = _without_timestamps(parsed)
        assert normalized['side_parse_diagnostics'].pop('header_field_count') == (10 if extended else 9)
        outputs.append(normalized)
    assert outputs[0] == outputs[1]
    print(f'IDENTITY COMPATIBILITY: {Path(lua).name} R{half} SaveStats output -> test extension/count -> parser parity')
