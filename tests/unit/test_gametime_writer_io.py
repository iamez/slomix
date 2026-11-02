"""Execute shipped Lua writer body; real files + ENOSPC, no ET/network/service."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from bot.runtime_gametime_source import parse_verified_gametime
from tests.unit.test_runtime_gametime_source import NAME, document


@pytest.fixture(params=['lua5.1', 'lua5.4'])
def lua(request):
    executable = shutil.which(request.param)
    if executable is None and request.param == 'lua5.1':
        pytest.skip('Optional Lua5.1 compatibility interpreter not installed')
    assert executable is not None, 'Lua5.4 is required for producer contract proof'
    return executable


def run_writer(lua, tmp_path, fault='none', *, start=1700000000):
    source = (Path(__file__).resolve().parents[2] / 'vps_scripts/stats_discord_webhook.lua').read_text()
    body_start = source.index('local function write_gametime_file(')
    body_end = source.index('\n-- ============================================================================', body_start)
    harness = r'''
local fault = arg[2]
local messages = {}
configuration = {gametimes_enabled=fault ~= 'disabled'}
function get_gametimes_dir() return arg[1] end
function ensure_dir(_) end
function log(message) table.insert(messages, message) end
function json_escape(s) return s end
et = {trap_Cvar_Get=function(_) return '' end}
local real_open = io.open
io.open = function(name, mode)
    if fault == 'open' then return nil, 'fixture open failure' end
    if fault == 'full-write' or fault == 'full-close' then
        local file = assert(real_open('/dev/full', mode))
        assert(file:setvbuf(fault == 'full-write' and 'no' or 'full', 4096))
        return {
            write=function(_, bytes)
                local result, message, code = file:write(bytes)
                print('WRITE_OK=' .. tostring(result ~= nil))
                return result, message, code
            end,
            close=function(_)
                local result, message, code = file:close()
                print('CLOSE_OK=' .. tostring(result ~= nil))
                return result, message, code
            end
        }
    end
    if fault == 'none' then return real_open(name, mode) end
    return {
        write=function(self, _)
            if fault == 'write-return' then return nil, 'fixture write failure', 28 end
            if fault == 'write-raise' then error('fixture write failure') end
            return self
        end,
        close=function(_)
            print('CLOSE_ATTEMPT')
            if fault == 'close-return' then return nil, 'fixture close failure', 28 end
            if fault == 'close-raise' then error('fixture close failure') end
            return true
        end
    }
end
'''
    body = document()['payload']
    for entry in body['embeds'][0]['fields']:
        if entry['name'] == 'Lua_RoundStart':
            entry['value'] = str(start)
        elif entry['name'] == 'Lua_RoundEnd':
            entry['value'] = str(start + 610)
    payload = json.dumps(body)
    harness += source[body_start:body_end] + '\nlocal result = write_gametime_file([=[' + payload + ']=], {'
    harness += f"mapname='supply',round=1,round_start_unix={start},round_end_unix={start + 610},"
    harness += "actual_duration_seconds=600,pause_seconds=10,pause_count=1,spawn_stats_json='[]'})\n"
    harness += "print('RESULT=' .. tostring(result))\nprint(table.concat(messages, '\\n'))\n"
    result = subprocess.run([lua, '-', str(tmp_path), fault], input=harness, text=True,
                            capture_output=True, timeout=10, check=True)
    assert result.stderr == ''
    return result.stdout


@pytest.mark.parametrize('fault', ['write-return', 'close-return', 'write-raise', 'close-raise'])
def test_failed_write_or_close_never_reports_success(lua, tmp_path, fault):
    output = run_writer(lua, tmp_path, fault)
    assert 'RESULT=false' in output, output
    assert 'Failed to write gametime data:' in output
    assert f"fixture {fault.split('-')[0]} failure" in output
    assert 'Gametime file written:' not in output
    assert 'CLOSE_ATTEMPT' in output  # Cleanup attempted even after write failure.


@pytest.mark.parametrize('fault', ['full-write', 'full-close'])
def test_real_enospc_write_and_flush_failure(lua, tmp_path, fault):
    assert Path('/dev/full').exists(), 'Linux ENOSPC test device required'
    output = run_writer(lua, tmp_path, fault)
    assert 'WRITE_OK=' + str(fault == 'full-close').lower() in output
    assert ('CLOSE_OK=false' if fault == 'full-close' else 'WRITE_OK=false') in output
    assert 'RESULT=false' in output, output
    assert 'Failed to write gametime data:' in output
    assert 'Gametime file written:' not in output
    print(f'GAMETIME REAL IO: {Path(lua).name}/{fault} -> failure, no success log')


def test_real_file_closed_then_admitted(lua, tmp_path):
    output = run_writer(lua, tmp_path)
    assert 'RESULT=true' in output and 'Gametime file written:' in output
    path = tmp_path / NAME
    raw = path.read_bytes()
    stored = json.loads(raw)
    assert stored['meta']['actual_duration_seconds'] == 600
    with path.open('rb') as stream:
        timing = parse_verified_gametime(stream.fileno(), source_id='fixture-server',
            generation='a' * 32, filename=NAME, expected_size=len(raw),
            expected_sha256=hashlib.sha256(raw).hexdigest())
    assert timing.actual_duration_seconds == 600 and timing.total_pause_seconds == 10
    assert timing.round_end_unix - timing.round_start_unix == 610
    print(f'GAMETIME REAL IO: {Path(lua).name}/closed file -> sealed admission 600s+10s')


@pytest.mark.parametrize('fault', ['disabled', 'open'])
def test_disabled_or_open_failure_never_claims_write(lua, tmp_path, fault):
    output = run_writer(lua, tmp_path, fault)
    assert 'RESULT=false' in output
    assert 'Gametime file written:' not in output
    assert not (tmp_path / NAME).exists()
