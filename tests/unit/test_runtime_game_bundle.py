"""Offline game-Lua assembly; no game, install or service launch in these tests."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import prepare_runtime_game_bundle as bundle
from shared.release_manifest import MANIFEST
from shared.runtime_match_listener import _listener
from shared.runtime_socket_path import validate_socket_path
from tests.unit.test_spa_artifact_preflight import git

ROOT = Path(__file__).resolve().parents[2]


def compile_library(path, code, *flags):
    subprocess.run(['/usr/bin/cc', '-shared', '-fPIC', '-x', 'c', '-',
                    *flags, '-o', str(path)], input=code, text=True, check=True,
                   capture_output=True, timeout=15, env=bundle.TOOL_ENV)
    path.chmod(0o644)


@pytest.fixture
def inputs(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    git(source, 'init', '-b', 'fixture')
    git(source, 'config', 'user.name', 'Game fixture')
    git(source, 'config', 'user.email', 'fixture@example.invalid')
    git(source, 'config', 'core.hooksPath', str(tmp_path / 'absent-hooks'))
    (source / 'vps_scripts').mkdir()
    names = [f'vps_scripts/{name}.lua' for name in bundle.MODULES]
    for name in names:
        (source / name).write_text('-- committed fixture\nreturn {}\n')
    (source / 'LICENSE').write_text('fixture license\n')
    git(source, 'add', '--', 'LICENSE', *names)
    git(source, 'commit', '-m', 'fixture modules')
    native = tmp_path / 'unix.so'
    # Real ELF metadata but intentionally NO Lua implementation: packaging is
    # not ABI proof. Only the separate explicitly selected engine probe is that.
    compile_library(native, '#include <stdio.h>\nvoid fixture(void) { puts("fixture"); }\n',
                    '-Wl,-soname,liblua5.4-socket-unix.so.2')
    engine = tmp_path / 'qagame.so'
    compile_library(engine, 'void engine_fixture(void) {}\n', '-nostdlib')
    license_file = tmp_path / 'copyright'
    license_file.write_text('fixture dependency license\n')
    license_file.chmod(0o644)
    return dict(source=source, revision=git(source, 'rev-parse', 'HEAD'),
                destination=tmp_path / 'prepared', unix_library=native,
                unix_sha256=hashlib.sha256(native.read_bytes()).hexdigest(), unix_license=license_file,
                engine_library=engine, engine_sha256=hashlib.sha256(engine.read_bytes()).hexdigest(),
                source_id='local-et285', socket_path='/private/proof/stats.sock')


def test_offline_bundle_is_committed_closed_inventory_and_never_overwritten(inputs):
    dirty = inputs['source'] / 'vps_scripts/c0rnp0rn8.lua'
    dirty.write_text('error("DIRTY MUST NOT SHIP")\n')
    before = dirty.read_bytes()
    result = bundle.prepare(**inputs)
    root = inputs['destination']
    assert result['status'] == 'game_lua_bundle_verified_not_activated'
    assert result['activation_ready'] is False and 'real_engine_lua_abi' in result['not_checked']
    assert result['files'] == len(bundle.FILES) == 18
    assert os.stat(root).st_mode & 0o777 == 0o700
    assert (root / 'legacy/c0rnp0rn8.lua').read_text() == '-- committed fixture\nreturn {}\n'
    assert dirty.read_bytes() == before
    record = json.loads((root / MANIFEST).read_bytes())
    assert record['source_commit'] == inputs['revision']
    for name, expected in record['files'].items():
        assert subprocess.check_output(['sha256sum', str(root / name)], text=True).split()[0] == expected
    with pytest.raises(ValueError, match='NEW'):
        bundle.prepare(**inputs)
    assert bundle.verify(root) == result


@pytest.mark.parametrize('length', [64, 65])
def test_bundle_and_native_listener_agree_on_basename_bound(inputs, tmp_path_factory, length):
    # Use the short basetemp itself, not the long parametrized test directory.
    parent = tmp_path_factory.getbasetemp()
    parent.chmod(0o700)
    path = parent / ('s' * length)
    assert len(os.fsencode(path)) <= 107, 'Run with a shorter outside-Git basetemp'
    inputs['socket_path'] = str(path)
    if length == 65:
        with pytest.raises(ValueError, match='socket pathname'):
            bundle.prepare(**inputs)
        with pytest.raises(ValueError, match='socket pathname'), _listener(path):
            pytest.fail('Listener admitted the overlong name')
        assert not inputs['destination'].exists() and not path.exists()
    else:
        assert bundle.prepare(**inputs)['activation_ready'] is False
        with _listener(path) as (_, verify):
            assert path.is_socket()
            verify()
        assert bundle.verify(inputs['destination'])['activation_ready'] is False


@pytest.mark.parametrize('value', [None, '', '/', '//host/s', '/a/../b', '/a//b',
                                  '/a/./b', '/a/b/', '/a/č', 'relative', '/a/' + 's' * 65,
                                  '/' + 'p' * 42 + '/' + 's' * 64])
def test_shared_socket_contract_refuses_noncanonical_or_overlong_paths(value):
    with pytest.raises(ValueError, match='socket pathname'):
        validate_socket_path(value)


def test_shared_socket_contract_accepts_exact_107_bytes_without_existing_parent():
    value = '/' + 'p' * 41 + '/' + 's' * 64
    assert len(value.encode('ascii')) == 107
    validate_socket_path(value)


@pytest.mark.parametrize('relative,mode', [('.', 0o777), ('legacy', 0o755),
    ('legacy/lualibs', 0o770), ('legacy/lualibs/socket', 0o777), (MANIFEST, 0o666),
    (MANIFEST, 0o644), (bundle.ENTRY, 0o666), (bundle.NATIVE, 0o660)])
def test_private_bundle_permission_drift_refused_without_repair(inputs, relative, mode):
    bundle.prepare(**inputs)
    root = inputs['destination']
    target = root / relative
    target.chmod(mode)
    before = target.lstat()
    with pytest.raises(ValueError, match='owned and private'):
        bundle.verify(root)
    assert target.lstat() == before


def test_private_readonly_payload_and_manifest_still_verify(inputs):
    bundle.prepare(**inputs)
    root = inputs['destination']
    for name in bundle.FILES | {MANIFEST}:
        (root / name).chmod(0o400)
    assert bundle.verify(root)['activation_ready'] is False


@pytest.mark.parametrize('relative', ['.', 'legacy/lualibs/socket', MANIFEST, bundle.ENTRY])
def test_different_owner_evidence_is_refused(inputs, monkeypatch, relative):
    bundle.prepare(**inputs)
    root = inputs['destination']
    target = root / relative
    original = Path.lstat

    def other_owner(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if path == target:
            values = list(info)
            values[4] = info.st_uid + 1
            return os.stat_result(values)
        return info

    # Synthetic ownership evidence only; no privileged chown in this test.
    monkeypatch.setattr(Path, 'lstat', other_owner)
    with pytest.raises(ValueError, match='owned and private'):
        bundle.verify(root)


@pytest.mark.parametrize('damage', ['empty-dir', 'directory-link', 'manifest-link', 'manifest-fifo'])
def test_closed_private_inventory_covers_entries_omitted_by_payload_hashes(inputs, damage):
    bundle.prepare(**inputs)
    root = inputs['destination']
    if damage == 'empty-dir':
        (root / 'extra').mkdir(mode=0o700)
    else:
        target = root / ('legacy/lualibs/socket' if damage == 'directory-link' else MANIFEST)
        held = root.parent / 'retained'
        target.rename(held)
        if damage == 'manifest-fifo':
            os.mkfifo(target, 0o600)
        else:
            target.symlink_to(held, target_is_directory=held.is_dir())
    with pytest.raises(ValueError):
        bundle.verify(root)


@pytest.mark.parametrize('fault', ['hash', 'elf', 'mode', 'link', 'missing-module', 'git-link',
                                 'engine-hash', 'engine-soname', 'unix-soname'])
def test_bad_inputs_refuse_before_creating_output(inputs, fault):
    native = inputs['unix_library']
    if fault == 'hash':
        inputs['unix_sha256'] = '0' * 64
    elif fault == 'elf':
        native.write_bytes(b'not a shared library')
        inputs['unix_sha256'] = hashlib.sha256(native.read_bytes()).hexdigest()
    elif fault == 'mode':
        native.chmod(0o666)
    elif fault == 'link':
        alias = native.with_name('alias')
        alias.symlink_to(native)
        inputs['unix_library'] = alias
    elif fault == 'engine-hash':
        inputs['engine_sha256'] = '0' * 64
    elif fault == 'engine-soname':
        engine = inputs['engine_library']
        compile_library(engine, 'void fixture(void) {}\n', '-Wl,-soname,qagame.so')
        inputs['engine_sha256'] = hashlib.sha256(engine.read_bytes()).hexdigest()
    elif fault == 'unix-soname':
        compile_library(native, 'void fixture(void) {}\n', '-Wl,-soname,wrong.so')
        inputs['unix_sha256'] = hashlib.sha256(native.read_bytes()).hexdigest()
    else:
        module = inputs['source'] / 'vps_scripts/runtime_c0rn_host.lua'
        module.rename(module.with_suffix('.held'))
        if fault == 'git-link':
            module.symlink_to('runtime_c0rn_host.held')
        git(inputs['source'], 'add', '--', 'vps_scripts/runtime_c0rn_host.lua')
        git(inputs['source'], 'commit', '-m', 'fixture invalid committed module')
        inputs['revision'] = git(inputs['source'], 'rev-parse', 'HEAD')
    with pytest.raises((ValueError, OSError)):
        bundle.prepare(**inputs)
    assert not inputs['destination'].exists()


@pytest.mark.parametrize('changes', [dict(source_id='x"),attack()'), dict(source_id=''),
    dict(socket_path='/a/../b'), dict(socket_path='/a//b'), dict(socket_path='/a; b'),
    dict(socket_path='relative'), dict(socket_path='/' + 'x' * 107), dict(bootstrap_ms=True),
    dict(bootstrap_ms=0), dict(completion_ms=10001), dict(revision='HEAD')])
def test_restricted_contract_refuses_interpolation_and_invalid_deadlines(inputs, changes):
    with pytest.raises(ValueError):
        bundle.prepare(**(inputs | changes))
    assert not inputs['destination'].exists()


def test_checkout_destination_is_refused_without_changes(inputs):
    inputs['destination'] = inputs['source'] / 'prepared'
    with pytest.raises(ValueError, match='outside Git'):
        bundle.prepare(**inputs)
    assert not inputs['destination'].exists()


def test_ambient_compiler_flags_do_not_control_the_carrier(inputs, monkeypatch):
    for name in ('CC', 'CFLAGS', 'LDFLAGS', 'GCC_EXEC_PREFIX', 'LIBRARY_PATH'):
        monkeypatch.setenv(name, '/this-must-not-control-the-build')
    assert bundle.prepare(**inputs)['activation_ready'] is False


def test_compiler_failure_retains_partial_bundle_without_completion_manifest(inputs, monkeypatch):
    real_run = subprocess.run

    def unavailable(command, **kwargs):
        if command[0] == '/usr/bin/cc':
            raise FileNotFoundError('explicit compiler unavailable')
        return real_run(command, **kwargs)

    monkeypatch.setattr(subprocess, 'run', unavailable)
    with pytest.raises(FileNotFoundError, match='compiler unavailable'):
        bundle.prepare(**inputs)
    root = inputs['destination']
    assert (root / bundle.UNIX).is_file()
    assert not (root / MANIFEST).exists()
    with pytest.raises(ValueError, match='NEW'):
        bundle.prepare(**inputs)


@pytest.mark.parametrize('damage', ['bytes', 'extra', 'missing', 'link', 'contract', 'wrapper',
                                  'approved-hash', 'carrier', 'link-source', 'engine'])
def test_verifier_refuses_tampering_even_rehashed_contract_or_wrapper(inputs, damage):
    bundle.prepare(**inputs)
    root = inputs['destination']
    record = json.loads((root / MANIFEST).read_bytes())
    if damage == 'bytes':
        (root / 'legacy/c0rnp0rn8.lua').write_text('changed\n')
    elif damage == 'extra':
        (root / 'legacy/other.lua').write_text('return 1\n')
    elif damage == 'missing':
        (root / bundle.NATIVE).rename(root.parent / 'held-native')
    elif damage == 'link':
        target = root / bundle.NATIVE
        held = root.parent / 'held-native'
        target.rename(held)
        target.symlink_to(held)
    elif damage == 'engine':
        with inputs['engine_library'].open('ab') as stream:
            stream.write(b'changed')
    elif damage in ('carrier', 'link-source'):
        target = root / (bundle.NATIVE if damage == 'carrier' else bundle.LINK_SOURCE)
        if damage == 'carrier':
            # A valid new checksum must not conceal a different ELF closure.
            compile_library(target, 'void fixture(void) {}\n', '-nostdlib')
            target.chmod(0o600)  # Exercise ELF closure, not the permission gate.
        else:
            target.write_bytes(b'/* changed */\n')
        record['files'][target.relative_to(root).as_posix()] = hashlib.sha256(target.read_bytes()).hexdigest()
        (root / MANIFEST).write_text(json.dumps(record))
    else:
        target = root / (bundle.ENTRY if damage == 'wrapper' else bundle.CONTRACT)
        if damage == 'wrapper':
            target.write_text('require("c0rnp0rn8")\n')
        else:
            contract = json.loads(target.read_bytes())
            contract['activation_ready' if damage == 'contract' else 'socket_unix_sha256'] = (
                True if damage == 'contract' else '0' * 64)
            target.write_text(json.dumps(contract, sort_keys=True, indent=2) + '\n')
        record['files'][target.relative_to(root).as_posix()] = hashlib.sha256(target.read_bytes()).hexdigest()
        (root / MANIFEST).write_text(json.dumps(record))
    with pytest.raises(ValueError):
        bundle.verify(root)


def test_actual_shipped_bundle_loads_from_game_paths_without_connecting(inputs):
    explicit_engine = os.environ.get('SLOMIX_PROOF_QAGAME')
    approved_engine_hash = os.environ.get('SLOMIX_PROOF_QAGAME_SHA256')
    if not explicit_engine or not approved_engine_hash:
        pytest.skip('Explicit approved embedded ET2.85 library/hash required; no engine discovery')
    engine = Path(explicit_engine)
    lua = shutil.which('lua5.4')
    if not lua:
        pytest.skip('Lua5.4 required for native offline loader proof')
    discovered = subprocess.run([lua, '-e', 'print(assert(package.searchpath("socket.unix",package.cpath)))'],
                                text=True, capture_output=True, timeout=5)
    if discovered.returncode != 0:
        pytest.skip('Installed LuaSocket unix dependency required for native loader proof')
    native = Path(discovered.stdout.strip()).resolve(strict=True)
    # Use the real committed shipped modules; never execute synthetic source.
    result = bundle.prepare(**(inputs | dict(source=ROOT, revision=git(ROOT, 'rev-parse', 'HEAD'),
        engine_library=engine, engine_sha256=approved_engine_hash,
        unix_library=native, unix_sha256=hashlib.sha256(native.read_bytes()).hexdigest())))
    root = inputs['destination']
    probe = ROOT / 'tests/fixtures/runtime_game_lua_probe.py'
    observed = subprocess.run([sys.executable, str(probe), str(engine), str(root)],
                              text=True, capture_output=True, timeout=10, env=bundle.TOOL_ENV)
    assert observed.returncode == 0, observed.stdout + observed.stderr
    assert 'waiting_init' in observed.stdout
    assert bundle.verify(root) == result  # The offline load wrote no bundle bytes.
    print(observed.stdout.strip())
    # Negative control uses a NEW retained copy, never damages the good bundle.
    direct = root.with_name('direct-native-negative-control')
    shutil.copytree(root, direct)
    (direct / bundle.NATIVE).rename(direct / 'held-carrier.so')
    shutil.copyfile(native, direct / bundle.NATIVE)
    failed = subprocess.run([sys.executable, str(probe), str(engine), str(direct)],
                            text=True, capture_output=True, timeout=10, env=bundle.TOOL_ENV)
    assert failed.returncode != 0
    assert 'undefined symbol: lua_gettop' in failed.stderr
    print('NEGATIVE CONTROL:', failed.stderr.strip())
