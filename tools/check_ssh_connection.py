"""
Safe SSH connection checker.

- Loads SSH config from .env (via python-dotenv) if present.
- Checks that the SSH key file exists locally (expands ~).
- Attempts an SSH connection using paramiko with the private key.
- Runs a harmless command on the remote host (echo and ls remote stats dir) and prints the result.

This script will NOT print key contents or secrets.

Usage:
  .venv\Scripts\python.exe tools/check_ssh_connection.py

Exit codes:
 0 = success (connected and command ran)
 1 = failure (connection or setup issue)
"""
import os
import sys
import traceback
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:
    print("python-dotenv is not installed in the active environment. Install it first.")
    sys.exit(1)

try:
    import paramiko
except Exception:
    print("paramiko is not installed in the active environment. Install it first.")
    sys.exit(1)

# Load .env if present
ENV_PATH = Path(__file__).resolve().parents[1] / '.env'
if ENV_PATH.exists():
    load_dotenv(str(ENV_PATH))

SSH_HOST = os.getenv('SSH_HOST')
SSH_PORT = int(os.getenv('SSH_PORT', '22'))
SSH_USER = os.getenv('SSH_USER')
SSH_KEY_PATH = os.path.expanduser(os.getenv('SSH_KEY_PATH', '~/.ssh/id_rsa'))
REMOTE_STATS_PATH = os.getenv('REMOTE_STATS_PATH', '')

print(f"Checking SSH configuration (host={SSH_HOST}, port={SSH_PORT}, user={SSH_USER})")

# Basic validation
if not SSH_HOST or not SSH_USER:
    print("Missing SSH_HOST or SSH_USER in environment (.env). Aborting.")
    sys.exit(1)

key_path = Path(SSH_KEY_PATH)
print(f"Local key path: {key_path}")
if not key_path.exists():
    print(f"SSH key file not found at {key_path}.\nPlease create the key or update SSH_KEY_PATH in .env.")
    sys.exit(1)

# Try to load private key
pkey = None
try:
    # Try several key types that may be available in this Paramiko build.
    key_class_names = [
        'Ed25519Key',
        'RSAKey',
        'ECDSAKey',
        'DSSKey',
    ]
    for class_name in key_class_names:
        KeyClass = getattr(paramiko, class_name, None)
        if KeyClass is None:
            continue
        try:
            pkey = KeyClass.from_private_key_file(str(key_path))
            print(f"Loaded private key as {KeyClass.__name__}")
            break
        except paramiko.PasswordRequiredException:
            print("Private key is encrypted with a passphrase. This script does not handle passphrases.")
            sys.exit(1)
        except Exception:
            # try next
            continue
    if pkey is None:
        print("Unable to parse private key with known formats.")
        sys.exit(1)
except Exception as e:
    print("Error while loading private key:", str(e))
    traceback.print_exc()
    sys.exit(1)

# Attempt SSH connection
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"Connecting to {SSH_USER}@{SSH_HOST}:{SSH_PORT} ...")
    client.connect(hostname=SSH_HOST, port=SSH_PORT, username=SSH_USER, pkey=pkey, timeout=10)
    print("SSH connection established.")

    # Run harmless commands
    stdin, stdout, stderr = client.exec_command('echo connected && uname -a')
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    print("--- Remote echo/uname output ---")
    print(out)
    if err:
        print("--- Remote stderr ---")
        print(err)

    if REMOTE_STATS_PATH:
        print(f"Listing remote stats path: {REMOTE_STATS_PATH}")
        # Use ls -la safely; if path doesn't exist, show error
        cmd = f'ls -la "{REMOTE_STATS_PATH}"'
        stdin, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode(errors='replace')
        err = stderr.read().decode(errors='replace')
        print(out if out else '(no output)')
        if err:
            print('Remote ls error:', err)

    client.close()
    print("SSH check completed successfully.")
    sys.exit(0)
except Exception as e:
    print("SSH connection failed:", str(e))
    traceback.print_exc()
    sys.exit(1)
