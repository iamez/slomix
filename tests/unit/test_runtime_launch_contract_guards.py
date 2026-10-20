"""Release budgets and shutdown observations must match the admitted launch."""
import pytest

from scripts import apply_migrations as migrations
from scripts import runtime_game_supervisor as supervisor
from tests.unit.test_release_operator_tool_boundaries import approved_release_config


@pytest.mark.parametrize('name,value', [('CONNECT', '3599'), ('COMMAND', '1'),
                                        ('STATEMENT', '1'), ('LOCK', '3599')])
def test_release_omitted_budgets_ignore_ambient_values(tmp_path, monkeypatch, name, value):
    approved_release_config(tmp_path, monkeypatch)
    for key in ('CONNECT', 'COMMAND', 'STATEMENT', 'LOCK'):
        monkeypatch.delenv(f'MIGRATION_{key}_TIMEOUT_SECONDS', raising=False)
    monkeypatch.setenv(f'MIGRATION_{name}_TIMEOUT_SECONDS', value)
    assert migrations.get_timeout_kwargs() == {
        'timeout': 10, 'command_timeout': 600,
        'server_settings': {'application_name': 'slomix-migrations',
                            'lock_timeout': '5s', 'statement_timeout': '300s'},
    }


def test_legacy_explicit_ambient_budgets_still_work(tmp_path, monkeypatch):
    monkeypatch.setattr(migrations, '_REPO_ROOT', tmp_path)
    monkeypatch.delenv('SLOMIX_ENV_FILE', raising=False)
    for name, value in {'CONNECT': 2, 'COMMAND': 5, 'STATEMENT': 3, 'LOCK': 1}.items():
        monkeypatch.setenv(f'MIGRATION_{name}_TIMEOUT_SECONDS', str(value))
    assert migrations.get_timeout_kwargs()['timeout'] == 2
    assert migrations.get_timeout_kwargs()['server_settings']['lock_timeout'] == '1s'


@pytest.mark.parametrize('port', [27963, 1024, 65535, True, '27962'])
def test_shutdown_never_admits_a_different_port(monkeypatch, port):
    monkeypatch.setattr(supervisor, 'unit_properties', lambda *args: pytest.fail('Wrong port reached host inspection'))
    with pytest.raises(ValueError, match='fixed launched'):
        supervisor.verify_stopped('slomix-et-proof-1234abcd.service', port, 'a' * 32)


def test_launch_passes_the_same_fixed_port_to_recipe(tmp_path, monkeypatch):
    from unittest.mock import Mock

    monkeypatch.setattr(supervisor, 'require_containment', lambda *args: {'InvocationID': 'a' * 32})
    monkeypatch.setattr(supervisor, 'validate_launch_commands', lambda *args: None)
    monkeypatch.setattr(supervisor, 'verify_source', lambda *args: None)
    recipe = Mock(side_effect=ValueError('fixture stops before launch'))
    monkeypatch.setattr(supervisor, 'startup_recipe', recipe)
    monkeypatch.setattr(supervisor.subprocess, 'Popen', lambda *args, **kw: pytest.fail('Engine launched'))
    with pytest.raises(ValueError, match='fixture stops'):
        supervisor.run(tmp_path, 'slomix-et-proof-1234abcd.service', 'b' * 40)
    assert recipe.call_args.kwargs['port'] == supervisor.REHEARSAL_PORT


def test_wrong_port_child_cli_refuses_before_host_inspection():
    import json
    import subprocess
    import sys

    result = subprocess.run([sys.executable, '-I', '-B', supervisor.__file__, 'verify-stopped',
                             '--unit', 'slomix-et-proof-1234abcd.service', '--invocation-id', 'a' * 32,
                             '--port', '27963'], capture_output=True, text=True, timeout=10)
    assert result.returncode == 1 and result.stdout == ''
    assert json.loads(result.stderr) == {'status': 'refused_or_failed', 'error_type': 'ValueError',
                                         'shutdown_verified': False, 'evidence_retained': True}
