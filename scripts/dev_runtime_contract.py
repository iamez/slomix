"""Prepare exact DEV unit files OFFLINE. Never installs, starts or migrates.

The JSON contract contains hashes and paths, never dotenv contents. It covers
the existing DEV bot/web pair, not the independent future ingestion controller.
Dependency package inventories and state-copy completeness are separate gates.
"""
from __future__ import annotations

import argparse
import json
import os
import pwd
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.release_manifest import file_hash, verify_release  # noqa: E402
from shared.runtime_environment import read_external_environment  # noqa: E402

IDENTITIES = {
    "bot": ("192.168.64.116", "5432", "etlegacy", "etlegacy_user"),
    "web": ("localhost", "5432", "etlegacy", "website_app"),
}
BOOTSTRAP = {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"}


def canonical(path: Path, *, interpreter=False) -> Path:
    path = Path(path)
    if (not re.fullmatch(r"/[A-Za-z0-9_./-]+", str(path))
            or (path.parent.resolve(strict=True) != path.parent if interpreter
                else path.resolve(strict=True) != path)):
        raise ValueError("Expected existing canonical path without systemd metacharacters")
    return path


def service_uid() -> int:
    """Preparation must inspect access as the actual DEV service account."""
    try:
        return pwd.getpwnam("samba").pw_uid
    except KeyError:
        raise ValueError("DEV service account is unavailable") from None


def require_state_access(path: Path, *, directory=True) -> None:
    """ReadWritePaths does not grant Unix permissions; inspect effective access."""
    if os.geteuid() != service_uid():
        raise ValueError("Prepare the DEV contract as its service account")
    if directory and not path.is_dir():
        raise ValueError("State path must be a directory")
    for parent in path.parents:
        if not os.access(parent, os.X_OK, effective_ids=True):
            raise ValueError("Service account cannot traverse state ancestors")
    mode = os.R_OK | os.W_OK | (os.X_OK if directory else 0)
    if not os.access(path, mode, effective_ids=True):
        raise ValueError("Service account cannot read/write external state")


def state_paths(state: Path, role: str) -> dict[str, Path]:
    paths = {"BOT_LOG_DIR": state / "logs/bot", "WEB_LOG_DIR": state / "logs/web",
             "XDG_CACHE_HOME": state / "cache" / role,
             "MPLCONFIGDIR": state / "cache" / role / "matplotlib",
             "GREATSHOT_STORAGE_ROOT": state / "data/greatshot",
             "UPLOAD_STORAGE_ROOT": state / "data/uploads"}
    if role == "web":
        paths["RETRO_VIZ_ROOT"] = state / "data/retro-viz"
    if role == "bot":
        paths.update({"STATS_DIRECTORY": state / "data/stats",
                      "LOCAL_STATS_PATH": state / "data/stats",
                      "LOCAL_GAMETIMES_PATH": state / "data/gametimes",
                      "PROXIMITY_LOCAL_PATH": state / "data/proximity",
                      "BACKUP_DIRECTORY": state / "data/processed",
                      "METRICS_DB_PATH": state / "logs/bot/metrics/metrics.db"})
    return paths


def build_contract(release: Path, state: Path, bot_python: Path, web_python: Path,
                   bot_env: Path, web_env: Path) -> dict:
    release, state = canonical(release), canonical(state)
    record = verify_release(release)
    required = {"scripts/dev_runtime_contract.py", "scripts/dev_schema_preflight.py",
                "bot/ultimate_bot.py", "website/backend/main.py"}
    if not required <= record["files"].keys():
        raise ValueError("Release is missing clean-startup entrypoints")
    if (release.parent.name != "releases" or release.name != record["source_commit"]
            or state != release.parent.parent / "shared"):
        raise ValueError("Expected releases/<SHA> and sibling shared state directory")
    services = {}
    for role, python, env in (("bot", bot_python, bot_env), ("web", web_python, web_env)):
        # Preserve bin/python's lexical path so Python can find pyvenv.cfg.
        # Only this leaf may be a link; the venv/bin ancestors stay canonical.
        python, env = canonical(python, interpreter=True), canonical(env)
        venv = python.parent.parent
        if (python.name != "python" or python.parent.name != "bin" or venv.name != role
                or not venv.is_relative_to(release.parent.parent / "envs")
                or not python.is_file() or not os.access(python, os.X_OK)
                or not canonical(venv / "pyvenv.cfg").is_file()):
            raise ValueError("Expected external final-path BOT/WEB virtual environment")
        if env.parent != state / "config" or env.name != f"{role}.env":
            raise ValueError("Expected explicit shared/config role env")
        env_digest = file_hash(env)
        values = read_external_environment(env, root=release, expected_digest=env_digest)
        reserved = {*BOOTSTRAP, "PATH", "SLOMIX_ENV_FILE", "SLOMIX_ENV_SHA256", "PYTHONPATH", "PYTHONHOME",
                    "LD_PRELOAD", "LD_LIBRARY_PATH", "LD_AUDIT"}
        if reserved & values.keys() or any(key.startswith("PYTHON") for key in values):
            raise ValueError("Bootstrap variables belong in the unit, not dotenv")
        if values.get("BOT_ENVIRONMENT") != "dev" or values.get("DATABASE_TYPE") != "postgresql":
            raise ValueError("Only explicit DEV PostgreSQL configuration is supported")
        identity = tuple(values.get("POSTGRES_" + key) for key in ("HOST", "PORT", "DATABASE", "USER"))
        if identity != IDENTITIES[role] or values.get("POSTGRES_SSL_MODE") != "disable":
            raise ValueError("Database identity differs from this DEV host/role contract")
        password = values.get("POSTGRES_PASSWORD")
        if not password or password != password.strip() or re.search(r"\s#", password):
            raise ValueError("Explicit credential must survive application normalization unchanged")
        if role == "bot" and values.get("MAINTENANCE_RETENTION_ENABLED") != "false":
            raise ValueError("DEV state handover requires maintenance retention disabled")
        for name, path in state_paths(state, role).items():
            if values.get(name) != str(path):
                raise ValueError(f"Expected dedicated external path for {name}")
            selected = canonical(path.parent if name == "METRICS_DB_PATH" else path)
            require_state_access(selected)
            if name == "METRICS_DB_PATH" and (path.exists() or path.is_symlink()):
                if not canonical(path).is_file():
                    raise ValueError("Metrics database must be a regular state file")
                require_state_access(path, directory=False)
        # The config files never enter writable scopes. Shared data is explicitly
        # mutable; archived backups and old installations must stay outside it.
        writable = [str(state / "data"), str(state / "logs" / role), str(state / "cache" / role)]
        cwd = release if role == "bot" else release / "website"
        # Preserve the existing DEV bind in offline unit text; no socket is opened.
        argv = ([str(python), "bot/ultimate_bot.py"] if role == "bot" else
                [str(python), "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"])  # noqa: S104  # nosec B104
        pre = [str(python), "-I", "-B", str(release / "scripts/dev_schema_preflight.py"), "--release-mode",
               "--env-file", str(env), "--expected-env-sha256", env_digest,
               "--expected-host", identity[0], "--expected-port", identity[1],
               "--expected-database", identity[2], "--expected-user", identity[3],
               "--migrations-dir", str(release / "migrations")]
        services[f"etlegacy-{role}"] = {
            "cwd": str(cwd), "argv": argv, "pre_argv": pre, "user": "samba", "group": "samba",
            "environment": dict(BOOTSTRAP, SLOMIX_ENV_FILE=str(env), SLOMIX_ENV_SHA256=env_digest,
                                PATH=f"{python.parent}:/usr/local/bin:/usr/bin:/bin"),
            "read_only": [str(release), str(venv), str(env)], "read_write": writable,
            "env_sha256": env_digest, "python_sha256": file_hash(python),
            "venv_config_sha256": file_hash(venv / "pyvenv.cfg"),
            "memory_max": "1G" if role == "bot" else "512M",
            "cpu_quota": "200%" if role == "bot" else "100%",
        }
    return {"version": 1, "release": str(release), "state": str(state),
            "revision": record["source_commit"], "services": services}


def load_contract(path: Path) -> dict:
    try:
        saved = json.loads(Path(path).read_text())
        bot, web = saved["services"]["etlegacy-bot"], saved["services"]["etlegacy-web"]
        fresh = build_contract(Path(saved["release"]), Path(saved["state"]),
                               Path(bot["argv"][0]), Path(web["argv"][0]),
                               Path(bot["environment"]["SLOMIX_ENV_FILE"]),
                               Path(web["environment"]["SLOMIX_ENV_FILE"]))
    except (KeyError, TypeError, IndexError):
        raise ValueError("Invalid startup contract structure") from None
    if saved != fresh:
        raise ValueError("Prepared startup contract has drifted")
    return fresh


def render_unit(name: str, service: dict) -> str:
    environment = "\n".join(f'Environment="{key}={value}"'
                            for key, value in service["environment"].items())
    return f"""# Prepared offline. Installation/restart requires owner approval.
[Unit]
Description=Slomix clean DEV {name}
After=network-online.target postgresql.service
Wants=network-online.target
Requires=postgresql.service

[Service]
Type=simple
User={service['user']}
Group={service['group']}
WorkingDirectory={service['cwd']}
{environment}
ExecStartPre={' '.join(service['pre_argv'])}
ExecStart={' '.join(service['argv'])}
Restart=always
RestartSec=10
MemoryMax={service['memory_max']}
CPUQuota={service['cpu_quota']}
StandardOutput=journal
StandardError=journal
SyslogIdentifier={name}
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadOnlyPaths={' '.join(service['read_only'])}
ReadWritePaths={' '.join(service['read_write'])}

[Install]
WantedBy=multi-user.target
"""


def prepare(output: Path, **paths) -> dict:
    contract = build_contract(**paths)
    output = Path(output)
    parent = canonical(output.parent)
    if (output.exists() or output.is_symlink() or not re.fullmatch(r"[A-Za-z0-9_-]+", output.name)
            or parent.is_relative_to(Path(contract["release"]))
            or any((p / ".git").exists() for p in (parent, *parent.parents))):
        raise ValueError("Output must be NEW and outside code/Git")
    output.mkdir(mode=0o700)
    for name, service in contract["services"].items():
        with (output / f"{name}.service").open("x") as stream:
            stream.write(render_unit(name, service))
    with (output / "contract.json").open("x") as stream:
        json.dump(contract, stream, indent=2, sort_keys=True)
        stream.write("\n")
    load_contract(output / "contract.json")
    return {"status": "prepared_not_installed", "revision": contract["revision"], "output": str(output)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("release", "state", "bot-python", "web-python", "bot-env", "web-env", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    try:
        print(json.dumps(prepare(**vars(parser.parse_args(argv))), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        # Path/JSON/OS exceptions can expose user-supplied values. Never echo them.
        print(json.dumps({"status": "refused", "error": "Invalid or changed DEV startup inputs; partial output retained"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
