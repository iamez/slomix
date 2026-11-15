"""Real process admission/retry/signal checks; no database server is started."""
import json
import os
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest


@pytest.mark.parametrize('component', ['team', 'cache'])
@pytest.mark.parametrize('stop_signal', [signal.SIGTERM, signal.SIGINT])
def test_unavailable_database_process_reports_and_drains(component, stop_signal, tmp_path):
    root = Path(__file__).resolve().parents[2]
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('POSTGRES_', 'RUNTIME_', 'DISCORD_'))}
    env.update(BOT_ENVIRONMENT='dev', EVENT_STREAM_ENABLED='true',
               RUNTIME_TEAM_EVENTS_ENABLED='true', RUNTIME_TEAM_WORKER_ENABLED='true',
               RUNTIME_TEAM_DEV_HANDOVER_CONFIRMED='true',
               RUNTIME_HTTP_CACHE_EVENTS_ENABLED='true', RUNTIME_HTTP_CACHE_WORKER_ENABLED='true',
               POSTGRES_HOST=str(tmp_path / 'missing-socket'), POSTGRES_PORT='5432',
               POSTGRES_DATABASE='fixture', POSTGRES_USER='fixture',
               PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(root))
    process = subprocess.Popen([sys.executable, '-u', '-m', f'shared.runtime_{component}_main'],
                               cwd=root, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    records = []
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                if selector.select(timeout=0.2):
                    line = process.stdout.readline()
                    if not line:
                        break
                    records.append(json.loads(line))
                    if records[-1]['status'] == 'unavailable':
                        break
        assert any(r['status'] == 'starting' for r in records), records
        assert records[-1]['status'] == 'unavailable', records
        assert records[-1]['last_success_age_seconds'] is None
        assert process.poll() is None, 'DB outage must retry rather than exit'
        process.send_signal(stop_signal)
        out, err = process.communicate(timeout=8)
        records.extend(json.loads(line) for line in out.splitlines())
        assert process.returncode == (1 if component == 'team' else 0), err
        assert records[-1]['status'] == 'stopped'
        assert str(tmp_path) not in err, 'Do not disclose database paths in diagnostics'
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.communicate(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=2)
