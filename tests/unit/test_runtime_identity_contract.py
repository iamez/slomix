"""Versioned wire contract and actual Lua/Python header compatibility."""

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
