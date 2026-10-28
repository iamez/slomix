"""Archive rejection and inspect-only shell side-effect boundaries."""
import hashlib
import io
import os
import shlex
import struct
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from scripts.etl_update_preflight import EXPECTED_LUA, inspect_archive, verify_lua_log

ROOT = 'etlegacy-v2.86.2-17-g74fdd6a-x86_64'


def archive_fixture(tmp_path, defect=None):
    def elf(kind, machine=62):
        value = bytearray(64)
        value[:7] = b'\x7fELF\x02\x01\x01'
        struct.pack_into('<HH', value, 16, kind, machine)
        return bytes(value)

    path = tmp_path / 'release.tar.gz'
    entries = {
        ROOT + '/etlded.x86_64': elf(2),
        ROOT + '/legacy/qagame.mp.x86_64.so': elf(3, 183 if defect == 'arm' else 62),
        ROOT + '/legacy/legacy_v2.86.2-17-g74fdd6a.pk3': b'fixture',
        ROOT + '/etmain/legacy.cfg': b'upstream configuration',
        ROOT + '/legacy/omni-bot/et/scripts/et_botnames_ext.gm': b'upstream bot names',
    }
    if defect == 'missing_module':
        entries.pop(ROOT + '/legacy/qagame.mp.x86_64.so')
    if defect == 'traversal':
        entries[ROOT + '/../escape'] = b'bad'
    if defect == 'extra_package':
        entries[ROOT + '/legacy/legacy_v2.84.0.pk3'] = b'old'
    with tarfile.open(path, 'w:gz') as tar:
        for name, data in entries.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            tar.addfile(member, io.BytesIO(data))
        if defect == 'link':
            member = tarfile.TarInfo(ROOT + '/outside-link')
            member.type = tarfile.SYMTYPE
            member.linkname = '/etc/passwd'
            tar.addfile(member)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize('defect', ['arm', 'missing_module', 'traversal', 'extra_package', 'link'])
def test_unsafe_or_incomplete_archive_refused(tmp_path, defect):
    path, digest = archive_fixture(tmp_path, defect)
    with pytest.raises(ValueError):
        inspect_archive(path, digest)


def test_wrong_digest_refused_without_extraction(tmp_path):
    path, _ = archive_fixture(tmp_path)
    with pytest.raises(ValueError, match='SHA256 mismatch'):
        inspect_archive(path, '0' * 64)
    assert set(tmp_path.iterdir()) == {path}


def test_valid_archive_is_inspected_without_unpacking(tmp_path):
    path, digest = archive_fixture(tmp_path)
    assert inspect_archive(path, digest)['root'] == ROOT
    assert set(tmp_path.iterdir()) == {path}


@pytest.mark.parametrize('defect', ['missing', 'extra', 'error', None])
def test_lua_load_set_and_error_gate(tmp_path, defect):
    names = sorted(EXPECTED_LUA)
    if defect == 'missing':
        names.pop()
    if defect == 'extra':
        names.append('luascripts/wolfadmin/main.lua')
    log = tmp_path / 'console.log'
    text = ''.join(f"0 Lua 5.4 API: file '{name}' loaded into Lua VM\n" for name in names)
    if defect == 'error':
        text += 'Lua: attempt to index a nil value\n'
    log.write_text(text)
    if defect:
        with pytest.raises(ValueError):
            verify_lua_log(log)
    else:
        assert len(verify_lua_log(log)['modules']) == 6


def test_shell_inspect_never_invokes_mutating_commands(tmp_path):
    path, digest = archive_fixture(tmp_path)
    commands = tmp_path / 'commands'
    commands.mkdir()
    (commands / 'python3').symlink_to(sys.executable)
    touched = tmp_path / 'forbidden-action'
    for name in ['mktemp', 'screen', 'pkill', 'wget', 'curl', 'ssh', 'cp', 'tar']:
        command = commands / name
        command.write_text(f'#!/bin/sh\ntouch "{touched}"\nexit 90\n')
        command.chmod(0o700)
    script = Path(__file__).resolve().parents[2] / 'scripts/etl_update.sh'
    result = subprocess.run(['/bin/bash', str(script), '--inspect', str(path), digest],
                            capture_output=True, text=True,
                            env=dict(os.environ, PATH=str(commands) + os.pathsep + os.environ['PATH']))
    assert result.returncode == 0, result.stderr
    assert 'archive_verified_not_activated' in result.stdout
    assert not touched.exists()


@pytest.mark.parametrize('fail_backup', [False, True])
def test_owner_flow_with_stubbed_controls_preserves_state_or_refuses(tmp_path, fail_backup):
    """Exercise the real shell workflow without game processes, network or HOME changes."""
    path, digest = archive_fixture(tmp_path)
    project = Path(__file__).resolve().parents[2]
    game, state, backups, commands = [tmp_path / x for x in ['game', 'state', 'backups', 'commands']]
    for directory in [game / 'legacy', game / 'etmain', state, commands]:
        directory.mkdir(parents=True, exist_ok=True)
    (game / 'etlded.x86_64').write_bytes(b'old engine')
    (game / 'legacy/qagame.mp.x86_64.so').write_bytes(b'old module')
    (game / 'legacy/legacy_v2.84.0.pk3').write_bytes(b'old package')
    (game / 'etmain/legacy.cfg').write_bytes(b'owner configuration')
    names = game / 'legacy/omni-bot/et/scripts/et_botnames_ext.gm'
    names.parent.mkdir(parents=True)
    names.write_bytes(b'owner bot names')
    (state / 'client01.json').write_text('{"fixture": true}')
    console = state / 'etconsole.log'
    console.write_text('old console')
    script_text = (project / 'scripts/etl_update.sh').read_text()
    replacements = {'GAME_DIR="$HOME/etlegacy-v2.83.1-x86_64"': 'GAME_DIR=' + shlex.quote(str(game)),
                    'BACKUP_ROOT="$HOME/backups"': 'BACKUP_ROOT=' + shlex.quote(str(backups)),
                    'HOME_STATE="$HOME/.etlegacy/legacy"': 'HOME_STATE=' + shlex.quote(str(state)),
                    'ETCONSOLE="$HOME/.etlegacy/legacy/etconsole.log"': 'ETCONSOLE=' + shlex.quote(str(console))}
    for before, after in replacements.items():
        assert before in script_text
        script_text = script_text.replace(before, after)
    script = tmp_path / 'etl_update.sh'
    script.write_text(script_text)
    (tmp_path / 'etl_update_preflight.py').write_bytes((project / 'scripts/etl_update_preflight.py').read_bytes())
    stub = commands / 'stub'
    stub.write_text(f'''#!{sys.executable}
import os,sys,time,shutil,subprocess
from pathlib import Path
name=Path(sys.argv[0]).name
args=sys.argv[1:]
flag=Path(os.environ['ET_TEST_STARTED'])
if name=='wget': shutil.copyfile(os.environ['ET_TEST_ARCHIVE'],args[args.index('-O')+1])
elif name=='strings': print('ET Legacy v2.86.2-17-g74fdd6a')
elif name=='sleep': time.sleep(0.15)
elif name=='pkill': Path(os.environ['ET_TEST_STOPPED']).write_text('stubbed control only')
elif name=='screen':
 if '-ls' in args: print('123.vektor' if flag.exists() else '')
elif name=='pgrep': sys.exit(0 if flag.exists() else 1)
elif name=='nohup':
 Path(os.environ['ET_TEST_CONSOLE']).write_text(os.environ['ET_TEST_LUA_LINES'])
 flag.write_text('stubbed startup only')
elif name=='cp':
 if os.environ['ET_TEST_FAIL_BACKUP']=='1' and any('pre-update-' in a for a in args): sys.exit(1)
 sys.exit(subprocess.call(['/usr/bin/cp',*args]))
''')
    stub.chmod(0o700)
    for name in ['wget', 'strings', 'sleep', 'pkill', 'screen', 'pgrep', 'nohup', 'cp']:
        (commands / name).symlink_to(stub)
    stopped, started = tmp_path / 'stopped', tmp_path / 'started'
    lines = ''.join(f"0 file '{name}' loaded into Lua VM\n" for name in sorted(EXPECTED_LUA))
    env = dict(os.environ, PATH=str(commands) + os.pathsep + os.environ['PATH'],
               ET_TEST_ARCHIVE=str(path), ET_TEST_STARTED=str(started), ET_TEST_STOPPED=str(stopped),
               ET_TEST_CONSOLE=str(console), ET_TEST_LUA_LINES=lines,
               ET_TEST_FAIL_BACKUP='1' if fail_backup else '0')
    result = subprocess.run(['/bin/bash', str(script), 'snapshot', 'https://fixture.invalid/release', digest],
                            input='y\n', capture_output=True, text=True, env=env, timeout=15)
    if fail_backup:
        assert result.returncode != 0
        assert 'engine backup failed' in result.stderr
        assert not stopped.exists()
        assert (game / 'etlded.x86_64').read_bytes() == b'old engine'
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert stopped.exists() and started.exists()
        assert (game / 'etmain/legacy.cfg').read_bytes() == b'owner configuration'
        assert names.read_bytes() == b'owner bot names'
        backup = next(backups.glob('pre-update-*'))
        with tarfile.open(backup / 'game-base.tar') as tar:
            assert tar.extractfile('./etlded.x86_64').read() == b'old engine'
        with tarfile.open(backup / 'home-state.tar') as tar:
            assert tar.extractfile('./client01.json').read() == b'{"fixture": true}'
