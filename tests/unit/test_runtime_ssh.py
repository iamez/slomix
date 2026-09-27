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
        strategy = client.connect.call_args.kwargs['auth_strategy']
        assert isinstance(strategy, paramiko.auth_strategy.AuthStrategy)
        client.connect.assert_called_once_with(
            hostname='fixture.invalid', port=2222, username='fixture',
            auth_strategy=strategy,
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


@pytest.mark.parametrize('remaining', [['keyboard-interactive'], ['password'], []])
def test_partial_publickey_never_prompts_or_opens_sftp(config, monkeypatch, remaining):
    """Exercise installed legacy auth or the supplied strategy without a socket."""
    key = paramiko.RSAKey.generate(2048)
    key.write_private_key_file(str(config.key_path))
    config.known_hosts.write_text('')
    client = paramiko.SSHClient()
    transport = Mock()
    transport.auth_publickey.return_value = remaining
    transport.is_authenticated.return_value = False
    transport.auth_interactive_dumb.side_effect = AssertionError('Interactive authentication attempted')
    client._transport = transport  # noqa: SLF001 - offline installed-auth regression seam
    def connect(**kwargs):
        strategy = kwargs.get('auth_strategy')
        if strategy is not None:
            return strategy.authenticate(transport)
        return client._auth(kwargs['username'], None, None, [kwargs['key_filename']],  # noqa: SLF001
                            kwargs['allow_agent'], kwargs['look_for_keys'], None)
    monkeypatch.setattr(client, 'connect', connect)
    sftp = Mock()
    monkeypatch.setattr(client, 'open_sftp', sftp)
    monkeypatch.setattr(paramiko, 'SSHClient', lambda: client)
    with pytest.raises(paramiko.AuthenticationException), open_runtime_sftp(config):
        pytest.fail('Incomplete authentication accepted')
    transport.auth_publickey.assert_called_once()
    transport.auth_interactive_dumb.assert_not_called()
    transport.auth_password.assert_not_called()
    transport.close.assert_called_once()
    sftp.assert_not_called()


@pytest.mark.parametrize('kind,encoding', [
    ('rsa', 'pem'), ('rsa', 'openssh'), ('ecdsa', 'pem'),
    ('ecdsa', 'openssh'), ('ed25519', 'openssh'),
])
def test_installed_connect_key_formats_without_legacy_auth(config, monkeypatch, kind, encoding):
    """Real connect/host-key/loading/strategy path; only transport is synthetic."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa

    key = {'rsa': lambda: rsa.generate_private_key(public_exponent=65537, key_size=2048),
           'ecdsa': lambda: ec.generate_private_key(ec.SECP256R1()),
           'ed25519': ed25519.Ed25519PrivateKey.generate}[kind]()
    form = (serialization.PrivateFormat.OpenSSH if encoding == 'openssh'
            else serialization.PrivateFormat.TraditionalOpenSSL)
    config.key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, form,
                                                 serialization.NoEncryption()))
    host = paramiko.ECDSAKey.generate()
    keys = paramiko.HostKeys()
    keys.add('[fixture.invalid]:2222', host.get_name(), host)
    keys.save(str(config.known_hosts))
    client = paramiko.SSHClient()
    original_connect = client.connect
    transport = Mock()
    transport.get_security_options.return_value.key_types = ['ecdsa-sha2-nistp256']
    transport.get_remote_server_key.return_value = host
    transport.auth_publickey.return_value = []
    transport.is_authenticated.return_value = True
    def connect(**kwargs):
        return original_connect(**kwargs, sock=Mock(), transport_factory=lambda *a, **k: transport)
    monkeypatch.setattr(client, 'connect', connect)
    legacy = Mock(side_effect=AssertionError('Legacy auth must not run'))
    monkeypatch.setattr(client, '_auth', legacy)
    sftp = Mock()
    monkeypatch.setattr(client, 'open_sftp', lambda: sftp)
    monkeypatch.setattr(paramiko, 'SSHClient', lambda: client)
    with open_runtime_sftp(config) as actual:
        assert actual is sftp
    transport.auth_publickey.assert_called_once()
    username, loaded_key = transport.auth_publickey.call_args.args
    assert username == 'fixture'
    assert loaded_key.can_sign()
    assert loaded_key.asbytes() == paramiko.PKey.from_path(config.key_path).asbytes()
    legacy.assert_not_called()
    transport.auth_interactive_dumb.assert_not_called()
    transport.auth_password.assert_not_called()
    transport.close.assert_called_once()
    sftp.close.assert_called_once()
    print(f'Offline installed Paramiko connect proof: {kind}/{encoding}, strict host key, key-only auth, cleanup')


@pytest.mark.parametrize('kind', ['missing', 'malformed', 'encrypted'])
def test_unusable_explicit_key_fails_without_fallback(config, monkeypatch, kind):
    """No prompt, ambient key or password fallback on loading failure."""
    if kind == 'malformed':
        config.key_path.write_text('not a private key')
    elif kind == 'encrypted':
        paramiko.RSAKey.generate(2048).write_private_key_file(str(config.key_path), password='fixture-only')
    client = Mock()
    transport = Mock()
    client.connect.side_effect = lambda **kwargs: kwargs['auth_strategy'].authenticate(transport)
    monkeypatch.setattr(paramiko, 'SSHClient', lambda: client)
    with pytest.raises((OSError, ValueError, TypeError, paramiko.SSHException)), open_runtime_sftp(config):
        pytest.fail('Unusable key accepted')
    transport.auth_publickey.assert_not_called()
    transport.auth_interactive_dumb.assert_not_called()
    transport.auth_password.assert_not_called()
    client.open_sftp.assert_not_called()
    client.close.assert_called_once()
