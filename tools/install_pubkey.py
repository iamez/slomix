#!/usr/bin/env python3
"""install_pubkey.py

Upload/append a local SSH public key to a remote user's ~/.ssh/authorized_keys.

Features:
- Reads defaults from a .env file (SSH_HOST, SSH_PORT, SSH_USER, SSH_KEY_PATH) if available.
- Accepts CLI overrides for host/port/user/pubkey path.
- Tries key-based auth first (using the private key), falls back to password auth (prompted) if needed.
- Avoids duplicating the same public key in authorized_keys.
- Ensures ~/.ssh and authorized_keys have correct permissions.

Usage (simple):
    python tools/install_pubkey.py

Or specify overrides (example):
    python tools/install_pubkey.py --host puran.hehe.si --port 48101 --user et --pub C:/Users/you/.ssh/etlegacy_bot.pub

Note: Use forward slashes in examples to avoid accidental escape sequences on Windows.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

try:
    import paramiko
except Exception as e:
    print("Missing dependency: paramiko is required. Install it into your venv: pip install paramiko")
    raise

try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv():
        return


def read_env_defaults():
    load_dotenv()
    return {
        "host": os.getenv("SSH_HOST"),
        "port": int(os.getenv("SSH_PORT")) if os.getenv("SSH_PORT") else None,
        "user": os.getenv("SSH_USER"),
        "pub": os.path.expanduser(os.getenv("SSH_KEY_PATH") + ".pub") if os.getenv("SSH_KEY_PATH") else None,
    }


def build_parser():
    p = argparse.ArgumentParser(description="Upload/append local public key to remote authorized_keys")
    p.add_argument("--host", help="SSH host (fallback: SSH_HOST in .env)")
    p.add_argument("--port", type=int, help="SSH port (fallback: SSH_PORT in .env)")
    p.add_argument("--user", help="SSH user (fallback: SSH_USER in .env)")
    p.add_argument("--pub", help="Path to public key file (defaults to ~/.ssh/etlegacy_bot.pub or SSH_KEY_PATH + .pub from .env)")
    p.add_argument("--priv", help="Path to private key (used to try key auth). Optional.")
    return p


def load_pubkey(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Public key not found at {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Public key file {path} is empty")
    return text


def connect_ssh(host: str, port: int, user: str, privkey_path: str | None, password: str | None):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs = {
        "hostname": host,
        "port": port,
        "username": user,
        "timeout": 10,
    }

    if privkey_path:
        connect_kwargs["key_filename"] = privkey_path

    if password:
        connect_kwargs["password"] = password

    client.connect(**connect_kwargs)
    return client


def ensure_remote_ssh_dir(sftp: paramiko.SFTPClient):
    try:
        sftp.chdir('.ssh')
    except IOError:
        # create .ssh
        try:
            sftp.mkdir('.ssh', mode=0o700)
        except Exception:
            # Some servers ignore mode here; we'll fix perms with chmod after
            pass


def remote_append_key(ssh_client: paramiko.SSHClient, sftp: paramiko.SFTPClient, pubkey_text: str):
    home = None
    try:
        # try to get home via SFTP's current working directory
        home = sftp.getcwd()
    except Exception:
        home = None

    remote_ssh_dir = '.ssh'
    remote_auth = f"{remote_ssh_dir}/authorized_keys"

    # Ensure .ssh exists
    ensure_remote_ssh_dir(sftp)

    # Read existing keys if present
    existing = ""
    try:
        with sftp.open(remote_auth, 'r') as f:
            existing = f.read().decode('utf-8') if isinstance(f.read(), bytes) else f.read()
    except IOError:
        existing = ""

    if pubkey_text.strip() in existing:
        return False  # already present

    # Append and write back
    new_content = existing.rstrip() + "\n" + pubkey_text.strip() + "\n"
    # write
    with sftp.open(remote_auth, 'w') as f:
        # paramiko SFTPFile wants bytes or str; ensure bytes
        if isinstance(new_content, str):
            f.write(new_content)
        else:
            f.write(new_content.encode('utf-8'))

    try:
        sftp.chmod(remote_auth, 0o600)
    except Exception:
        # ignore if server doesn't allow
        pass

    try:
        sftp.chmod(remote_ssh_dir, 0o700)
    except Exception:
        pass

    return True


def main():
    parser = build_parser()
    args = parser.parse_args()

    defaults = read_env_defaults()

    host = args.host or defaults.get('host')
    port = args.port or defaults.get('port') or 22
    user = args.user or defaults.get('user') or getpass.getuser()
    pub = args.pub or defaults.get('pub') or str(Path.home() / '.ssh' / 'etlegacy_bot.pub')
    priv = args.priv or None

    pub_path = Path(pub).expanduser()

    try:
        pubkey_text = load_pubkey(pub_path)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(2)

    if not host:
        print("ERROR: SSH host not provided (use --host or set SSH_HOST in .env)")
        sys.exit(2)

    print(f"Host: {host}  Port: {port}  User: {user}")

    # Try to connect with key auth first if priv provided or derived from pub
    tried_password = False
    password = None
    priv_path = priv or (str(pub_path.with_suffix('')) if pub_path.with_suffix('.pub') else None)

    client = None
    try:
        if priv_path and Path(priv_path).expanduser().exists():
            print(f"Trying key auth with {priv_path}...")
            try:
                client = connect_ssh(host, port, user, str(Path(priv_path).expanduser()), None)
            except paramiko.ssh_exception.AuthenticationException:
                client = None

        if client is None:
            # prompt for password
            password = getpass.getpass(prompt=f"Password for {user}@{host} (will not be echoed; press Enter to cancel): ")
            if not password:
                print("No password provided; aborting.")
                sys.exit(3)
            tried_password = True
            client = connect_ssh(host, port, user, None, password)

        # Open SFTP and append key
        sftp = client.open_sftp()
        appended = remote_append_key(client, sftp, pubkey_text)
        sftp.close()
        client.close()

        if appended:
            print("OK: public key appended to remote authorized_keys")
        else:
            print("OK: public key already present on remote (no changes made)")

    except paramiko.ssh_exception.AuthenticationException:
        print("Authentication failed. Wrong password or key refused.")
        sys.exit(4)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(5)


if __name__ == '__main__':
    main()
