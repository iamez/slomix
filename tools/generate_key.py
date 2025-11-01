#!/usr/bin/env python3
"""
generate_key.py

Generate an ed25519 key pair (no passphrase) using Paramiko and write to ~/.ssh/etlegacy_bot
This avoids PowerShell ssh-keygen quoting issues on Windows.
"""
from pathlib import Path
import sys

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
except Exception:
    print("Missing dependency: cryptography is required. Install into venv: pip install cryptography")
    raise


def main():
    home = Path.home()
    ssh_dir = home / '.ssh'
    ssh_dir.mkdir(mode=0o700, exist_ok=True)

    priv = ssh_dir / 'etlegacy_bot'
    pub = ssh_dir / 'etlegacy_bot.pub'

    try:
        private_key = ed25519.Ed25519PrivateKey.generate()

        # Private key in OpenSSH format (no encryption)
        priv_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.OpenSSH,
            encryption_algorithm=serialization.NoEncryption(),
        )

        # Public key in OpenSSH public key format (ssh-ed25519 AAAA...)
        public_key = private_key.public_key()
        pub_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH,
        )

        # Write files
        priv.write_bytes(priv_bytes)
        # Ensure private key perms (best-effort on Windows)
        try:
            priv.chmod(0o600)
        except Exception:
            pass

        pub.write_bytes(pub_bytes + b"\n")

        print(f"OK: generated {priv} and {pub}")

    except Exception as e:
        print('ERROR generating key:', e)
        sys.exit(2)


if __name__ == '__main__':
    main()
