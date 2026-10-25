"""Actual cog audit writes use external logs without a network or Discord client."""
import subprocess
import sys
from pathlib import Path


def test_native_server_control_writes_external_audit(tmp_path):
    root = Path(__file__).resolve().parents[2]
    payload = tmp_path / 'payload'
    payload.mkdir()
    logs = tmp_path / 'external-logs'
    code = '''
import asyncio, sys
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
from bot.cogs.server_control import ServerControl
control = ServerControl(SimpleNamespace(admin_channel_id=0))
asyncio.run(control.log_action(SimpleNamespace(author=SimpleNamespace(id=123)), 'LOCAL_ONLY_PROOF'))
'''
    result = subprocess.run([sys.executable, '-I', '-B', '-c', code, str(root)], cwd=payload,
                            env={'PATH': '/usr/bin:/bin', 'BOT_LOG_DIR': str(logs),
                                 'SSH_KEY_PATH': str(tmp_path / 'absent-key')},
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert 'LOCAL_ONLY_PROOF' in (logs / 'server_control_access.log').read_text()
    assert list(payload.iterdir()) == []
