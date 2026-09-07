"""Exercise build provenance and the actual dev preflight without real services."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/spa_artifact.py"
DEPLOY = ROOT / "scripts/dev_deploy.sh"


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.STDOUT).decode().strip()


@pytest.fixture
def fixture(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    git(source, "init", "-b", "main")
    git(source, "config", "user.name", "Artifact test")
    git(source, "config", "user.email", "artifact@example.invalid")
    git(source, "config", "core.hooksPath", str(tmp_path / "empty-hooks"))
    files = {
        ".gitignore": "website/static/\nnode_modules/\nwebsite/frontend/src/api/generated/\n",
        "website/frontend/package.json": (ROOT / "website/frontend/package.json").read_text(),
        "website/frontend/package-lock.json": "{}\n",
        "website/frontend/vite.app.config.ts": "export default {};\n",
        "website/frontend/src/app/main.ts": "console.log('app');\n",
        "docs/api/openapi.json": "{}\n",
        "scripts/spa_artifact.py": HELPER.read_text(),
    }
    for relative, content in files.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    git(source, "add", "--", *files)
    git(source, "commit", "-m", "source")
    generated = source / "website/frontend/src/api/generated/openapi.d.ts"
    generated.parent.mkdir(parents=True)
    generated.write_text("export interface paths {}\n")
    # Mock only Vite's executable; the actual provenance wrapper runs unchanged.
    vite = source / "website/frontend/node_modules/vite/bin/vite.js"
    vite.parent.mkdir(parents=True)
    vite.write_text("const fs = require('fs'); fs.mkdirSync('../static/app/assets', {recursive:true}); "
                    "fs.writeFileSync('../static/app/app.html', '<script src=assets/a.js></script>'); "
                    "fs.writeFileSync('../static/app/assets/a.js', 'console.log(1);');\n")
    run = tmp_path / "run"
    git(source, "clone", "--quiet", str(source), str(run))
    existing = run / "website/static/app/app.html"
    existing.parent.mkdir(parents=True)
    existing.write_text("previous active bundle")
    return source, run


def build(source, check=True):
    result = subprocess.run([sys.executable, str(source / "scripts/spa_artifact.py"),
                             "build", "--source", str(source)], text=True, capture_output=True)
    if check:
        assert result.returncode == 0, result.stderr
    return result


def preflight(source, run, target="HEAD", extra=None):
    # A real git wrapper records any forbidden preflight mutation before failing.
    mocks = source.parent / "mocks"
    mocks.mkdir(exist_ok=True)
    git_executable = shutil.which("git")
    log = source.parent / "mutations"
    wrapper = mocks / "git"
    wrapper.write_text(f'#!/bin/bash\nfor x in "$@"; do case "$x" in fetch|checkout) '
                       f'echo "$x" >> "{log}"; exit 88;; esac; done\nexec "{git_executable}" "$@"\n')
    wrapper.chmod(0o755)
    for name in ["sudo", "systemctl"]:
        stub = mocks / name
        stub.write_text(f'#!/bin/bash\necho "{name}" >> "{log}"\nexit 89\n')
        stub.chmod(0o755)
    env = dict(os.environ, DEV_SRC_DIR=str(source), DEV_RUN_DIR=str(run),
               DEV_PREFLIGHT_ONLY="1", PATH=f"{mocks}:{os.environ['PATH']}")
    env.update(extra or {})
    before = git(run, "rev-parse", "HEAD"), (run / "website/static/app/app.html").read_bytes()
    result = subprocess.run(["bash", str(DEPLOY), target], env=env, text=True, capture_output=True)
    assert not log.exists(), "preflight attempted fetch/checkout/service action"
    assert before == (git(run, "rev-parse", "HEAD"), (run / "website/static/app/app.html").read_bytes())
    assert not list(source.parent.glob(".slomix-artifact.*"))
    return result


def test_valid_build_workflow_and_safe_preflight(fixture):
    source, run = fixture
    build(source)
    record = json.loads((source / "website/static/app/.slomix-build.json").read_text())
    assert record["source_commit"] == git(source, "rev-parse", "HEAD")
    assert "website/frontend/package-lock.json" in record["inputs"]
    assert "website/frontend/vite.app.config.ts" in record["inputs"]
    assert "assets/a.js" in record["outputs"]
    scripts = json.loads((source / "website/frontend/package.json").read_text())["scripts"]
    assert scripts["build:app"] == "python3 ../../scripts/spa_artifact.py build"
    assert scripts["prebuild:app"] == "npm run generate:api"
    result = preflight(source, run)
    assert result.returncode == 0, result.stderr
    assert "run checkout and services unchanged" in result.stdout


@pytest.mark.parametrize("failure", ["missing", "corrupt", "dirty", "wrong-target", "stale",
                                     "generated", "untracked", "skip", "env", "symlink"])
def test_invalid_artifact_never_touches_run_clone_or_services(fixture, failure):
    source, run = fixture
    build(source)
    extra, target = {}, "HEAD"
    if failure == "missing":
        (source / "website/static/app/.slomix-build.json").unlink()
    elif failure == "corrupt":
        (source / "website/static/app/assets/a.js").write_text("corrupted")
    elif failure in {"dirty", "stale"}:
        (source / "website/frontend/vite.app.config.ts").write_text("export default {base:'/other'};\n")
        if failure == "stale":
            git(source, "add", "website/frontend/vite.app.config.ts")
            git(source, "commit", "-m", "new source")
    elif failure == "wrong-target":
        git(source, "commit", "--allow-empty", "-m", "another target")
        target = "HEAD^"
    elif failure == "generated":
        (source / "website/frontend/src/api/generated/openapi.d.ts").write_text("different types")
    elif failure == "untracked":
        (source / "website/frontend/src/app/extra.ts").write_text("untracked")
    elif failure == "skip":
        extra["SKIP_STATIC"] = "1"
    elif failure == "env":
        extra["VITE_TEST_OVERRIDE"] = "1"
    elif failure == "symlink":
        (source / "website/static/app/assets/link.js").symlink_to("a.js")
    result = preflight(source, run, target=target, extra=extra)
    assert result.returncode != 0, result.stdout


def test_failed_build_invalidates_previous_proof(fixture):
    source, _ = fixture
    build(source)
    vite = source / "website/frontend/node_modules/vite/bin/vite.js"
    vite.write_text("process.exit(7);\n")
    assert build(source, check=False).returncode != 0
    assert not (source / "website/static/app/.slomix-build.json").exists()


def test_source_change_during_build_cannot_be_certified(fixture):
    source, _ = fixture
    vite = source / "website/frontend/node_modules/vite/bin/vite.js"
    vite.write_text("require('fs').writeFileSync('src/app/main.ts', 'changed during build');\n")
    result = build(source, check=False)
    assert result.returncode != 0
    assert not (source / "website/static/app/.slomix-build.json").exists()


def test_disposable_activation_uses_verified_stage_and_preserves_previous(fixture):
    source, run = fixture
    build(source)
    legacy = run / "website/static/modern/route-host.js"
    legacy.parent.mkdir()
    legacy.write_text("existing legacy")
    env = dict(os.environ, DEV_SRC_DIR=str(source), DEV_RUN_DIR=str(run), SKIP_RESTART="1")
    result = subprocess.run(["bash", str(DEPLOY), "HEAD"], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert git(run, "rev-parse", "HEAD") == git(source, "rev-parse", "HEAD")
    assert (run / "website/static/app/assets/a.js").read_text() == "console.log(1);"
    backups = list(source.parent.glob(".slomix-app-previous.*/app/app.html"))
    assert len(backups) == 1
    assert backups[0].read_text() == "previous active bundle"
    assert legacy.read_text() == "existing legacy"
    assert "legacy static/modern preserved" in result.stderr


def test_copy_corruption_is_detected_in_staged_bytes(fixture, monkeypatch):
    source, _ = fixture
    build(source)
    spec = importlib.util.spec_from_file_location("spa_artifact_test", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = module.shutil.copytree
    def corrupt_copy(src, dest, *args, **kwargs):
        result = original(src, dest, *args, **kwargs)
        asset = Path(dest) / "assets/a.js"
        if asset.exists():
            asset.write_text("corrupt during copy")
        return result
    monkeypatch.setattr(module.shutil, "copytree", corrupt_copy)
    monkeypatch.setattr(sys, "argv", [str(HELPER), "stage", "--source", str(source),
                        "--target", git(source, "rev-parse", "HEAD"), "--stage", str(source.parent / "stage")])
    with pytest.raises(ValueError, match="integrity check failed"):
        module.main()
