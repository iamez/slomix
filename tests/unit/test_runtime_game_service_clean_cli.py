"""A native offline CLI invocation must leave the source payload byte-for-byte intact."""
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path


def test_help_without_bytecode_flags_preserves_source(tmp_path):
    repository = Path(__file__).resolve().parents[2]
    source = tmp_path / 'source'
    for package in ('scripts', 'shared'):
        shutil.copytree(repository / package, source / package,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    def inventory():
        return {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in source.rglob('*') if p.is_file()}
    before = inventory()
    result = subprocess.run([sys.executable, str(source / 'scripts/prepare_runtime_game_service.py'), '--help'],
                            cwd=source, env={'PATH': '/usr/bin:/bin'},
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert '--destination' in result.stdout
    assert not list(source.rglob('*.pyc'))
    assert inventory() == before
