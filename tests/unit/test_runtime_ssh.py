"""SSH ownership proofs without any network access or real credentials."""

from dataclasses import replace
from unittest.mock import Mock

import paramiko
import pytest

from shared.runtime_ssh import RuntimeSSHConfig, open_runtime_sftp


@pytest.fixture
def config(tmp_path):
    """Only fixture paths and a reserved invalid hostname are configured."""
    return RuntimeSSHConfig('fixture.invalid', 2222, 'fixture', tmp_path / 'key', tmp_path / 'hosts')


@pytest.mark.parametrize('phase', ['success', 'hosts', 'connect', 'sftp', 'timeout', 'body', 'close'])
def test_phase_failure_cleanup_and_explicit_auth(config, monkeypatch, phase):
    """Every acquired resource closes, including after SFTP cleanup failure."""
    events = []
    client = Mock()
    sftp = client.open_sftp.return_value
    client.close.side_effect = lambda: events.append('ssh-close')
    def close():
        events.append('sftp-close')
        if phase == 'close':
            raise OSError('fixture close')
    sftp.close.side_effect = close
    targets = {'hosts': client.load_host_keys, 'connect': client.connect,
               'sftp': client.open_sftp, 'timeout': sftp.get_channel.return_value.settimeout}
    if phase in targets:
        targets[phase].side_effect = OSError('fixture ' + phase)
    monkeypatch.setattr(paramiko, 'SSHClient', lambda: client)
    def run():
        with open_runtime_sftp(config) as actual:
            assert actual is sftp
            if phase == 'body':
                raise OSError('fixture body')
    if phase == 'success':
        run()
    else:
        with pytest.raises(OSError, match='fixture ' + phase):
            run()
    assert events == (['ssh-close'] if phase in {'hosts', 'connect', 'sftp'}
                      else ['sftp-close', 'ssh-close'])
    assert isinstance(client.set_missing_host_key_policy.call_args.args[0], paramiko.RejectPolicy)
    client.load_host_keys.assert_called_once_with(str(config.known_hosts))
    if phase != 'hosts':
        client.connect.assert_called_once_with(
            hostname='fixture.invalid', port=2222, username='fixture',
            key_filename=str(config.key_path), allow_agent=False, look_for_keys=False,
            timeout=10.0, banner_timeout=10.0, auth_timeout=10.0, channel_timeout=10.0,
        )


def test_real_paramiko_rejects_unknown_host(config, monkeypatch):
    """Actual RejectPolicy rejects an untrusted generated key without a socket."""
    config.known_hosts.write_text('')
    client = paramiko.SSHClient()
    key = paramiko.RSAKey.generate(2048)
    monkeypatch.setattr(client, '_log', Mock())  # No transport exists in this offline proof.
    # Connect seam executes real policy against a real SSHClient/HostKeys object.
    def connect(**kwargs):
        client._policy.missing_host_key(client, 'fixture.invalid', key)  # noqa: SLF001 - exercise installed policy
    monkeypatch.setattr(client, 'connect', connect)
    close = Mock(wraps=client.close)
    monkeypatch.setattr(client, 'close', close)
    monkeypatch.setattr(paramiko, 'SSHClient', lambda: client)
    with pytest.raises(paramiko.SSHException, match='not found in known_hosts'), open_runtime_sftp(config):
        pytest.fail('Unknown host was accepted')
    assert len(client.get_host_keys()) == 0
    assert config.known_hosts.read_text() == ''
    close.assert_called_once()
    print('SSH policy proof: actual Paramiko RejectPolicy refuses unknown key; hosts unchanged; client closed')


@pytest.mark.parametrize('field,value', [
    ('host', ''), ('user', ' '), ('port', True), ('port', 0), ('port', 65536),
    ('connect_timeout', 0), ('auth_timeout', float('nan')), ('banner_timeout', float('inf')),
    ('channel_timeout', 61), ('read_timeout', True), ('known_hosts', 'relative'),
])
def test_invalid_configuration_rejected(config, field, value):
    """Invalid endpoints or unbounded phase budgets fail before any SSH work."""
    with pytest.raises(ValueError):
        replace(config, **{field: value})
