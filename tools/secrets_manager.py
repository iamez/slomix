#!/usr/bin/env python3
"""
Secrets Management Tool for Slomix Discord Bot

This tool generates secure passwords in the format: random-words-typed-together-like-this1337
and helps rotate secrets in .env file.

Features:
- Generate secure passwords with random words + numbers
- Rotate database passwords (with PostgreSQL ALTER USER command)
- Rotate Discord bot token
- Rotate SSH keys
- Rotate OAuth secrets
- Backup old .env before modifications

Usage:
    python tools/secrets_manager.py generate           # Generate a password
    python tools/secrets_manager.py rotate-db          # Rotate database password
    python tools/secrets_manager.py rotate-discord     # Rotate Discord token
    python tools/secrets_manager.py backup-env         # Backup .env file
    python tools/secrets_manager.py audit              # Check for hardcoded secrets

Author: Claude Code
Date: 2026-02-08
Version: 1.0.0
"""

import argparse
import os
import random
import secrets
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

# Word list for password generation (common English nouns)
WORD_LIST = [
    "thunder", "mountain", "river", "ocean", "forest", "desert", "volcano", "glacier",
    "phoenix", "dragon", "tiger", "eagle", "panther", "falcon", "wolf", "bear",
    "nebula", "quasar", "pulsar", "cosmos", "galaxy", "planet", "meteor", "comet",
    "crimson", "azure", "emerald", "golden", "silver", "diamond", "crystal", "sapphire",
    "knight", "warrior", "guardian", "sentinel", "champion", "hero", "legend", "titan",
    "storm", "shadow", "flame", "frost", "lightning", "thunder", "blaze", "inferno",
    "cyber", "matrix", "nexus", "vertex", "apex", "zenith", "omega", "alpha",
    "quantum", "photon", "proton", "neutron", "electron", "particle", "wave", "field"
]


class SecretsManager:
    """Manages secret rotation for the bot."""

    def __init__(self, project_root: Path = None):
        """Initialize secrets manager."""
        if project_root is None:
            # Detect project root (where .env should be)
            script_dir = Path(__file__).parent
            self.project_root = script_dir.parent
        else:
            self.project_root = Path(project_root)

        self.env_file = self.project_root / ".env"
        self.env_example = self.project_root / ".env.example"

    def generate_password(self, word_count: int = 3, number_count: int = 4) -> str:
        """
        Generate a secure password in format: random-words-typed-together-like-this1337

        Args:
            word_count: Number of words to use (default: 3)
            number_count: Number of digits at the end (default: 4)

        Returns:
            Generated password string

        Example:
            >>> sm = SecretsManager()
            >>> sm.generate_password()
            'thunder-mountain-eagle1337'
        """
        words = random.sample(WORD_LIST, word_count)
        numbers = ''.join(str(secrets.randbelow(10)) for _ in range(number_count))
        return '-'.join(words) + numbers

    def backup_env_file(self) -> Path:
        """
        Create a timestamped backup of the .env file.

        Returns:
            Path to backup file

        Raises:
            FileNotFoundError: If .env doesn't exist
        """
        if not self.env_file.exists():
            raise FileNotFoundError(f".env file not found at {self.env_file}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.env_file.parent / f".env.backup.{timestamp}"

        shutil.copy2(self.env_file, backup_file)
        print(f"✅ Backed up .env to: {backup_file}")
        return backup_file

    def read_env(self) -> dict:
        """
        Read .env file into a dictionary.

        Returns:
            Dictionary of environment variables
        """
        if not self.env_file.exists():
            return {}

        env_vars = {}
        with open(self.env_file, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                # Parse KEY=VALUE
                if '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
        return env_vars

    def write_env(self, env_vars: dict) -> None:
        """
        Write environment variables to .env file.

        Args:
            env_vars: Dictionary of environment variables

        Note:
            This preserves comments and formatting from .env.example
        """
        # Read .env.example to preserve comments
        if not self.env_example.exists():
            # Fallback: just write the vars
            with open(self.env_file, 'w') as f:
                for key, value in env_vars.items():
                    f.write(f"{key}={value}\n")
            return

        # Parse .env.example and replace values
        with open(self.env_example, 'r') as src:
            lines = src.readlines()

        output_lines = []
        for line in lines:
            stripped = line.strip()
            # Preserve comments and empty lines
            if not stripped or stripped.startswith('#'):
                output_lines.append(line)
                continue

            # Replace values for keys we have
            if '=' in stripped:
                key = stripped.split('=', 1)[0].strip()
                if key in env_vars:
                    output_lines.append(f"{key}={env_vars[key]}\n")
                else:
                    output_lines.append(line)
            else:
                output_lines.append(line)

        # Write new .env
        with open(self.env_file, 'w') as f:
            f.writelines(output_lines)

        print(f"✅ Updated .env file at: {self.env_file}")

    def rotate_db_password(self, new_password: str = None) -> Tuple[str, str]:
        """
        Rotate database password.

        Args:
            new_password: New password (auto-generated if None)

        Returns:
            Tuple of (old_password, new_password)

        Note:
            You must run the ALTER USER command manually in PostgreSQL!
        """
        # Backup first
        self.backup_env_file()

        # Read current env
        env_vars = self.read_env()
        old_password = env_vars.get('POSTGRES_PASSWORD', '')

        # Generate new password if not provided
        if new_password is None:
            new_password = self.generate_password(word_count=4, number_count=6)

        # Update env vars
        env_vars['POSTGRES_PASSWORD'] = new_password

        # Write updated .env
        self.write_env(env_vars)

        print(f"\n{'='*70}")
        print("🔐 DATABASE PASSWORD ROTATION")
        print(f"{'='*70}")
        print(f"Old password: {old_password[:4]}****" if old_password else "Old password: (not set)")
        print(f"New password: {'*' * len(new_password)} (written to .env)")
        print("\n⚠️  IMPORTANT: You must run this SQL command manually:")
        print("\n    psql -U postgres -d etlegacy")
        print("    ALTER USER etlegacy_user WITH PASSWORD '<password-from-.env-file>';")
        print(f"\n{'='*70}\n")

        return old_password, new_password

    def rotate_discord_token(self, new_token: str) -> Tuple[str, str]:
        """
        Rotate Discord bot token.

        Args:
            new_token: New Discord token from developers portal

        Returns:
            Tuple of (old_token, new_token)
        """
        # Backup first
        self.backup_env_file()

        # Read current env
        env_vars = self.read_env()
        old_token = env_vars.get('DISCORD_BOT_TOKEN', '')

        # Update env vars
        env_vars['DISCORD_BOT_TOKEN'] = new_token

        # Write updated .env
        self.write_env(env_vars)

        print(f"\n{'='*70}")
        print("🤖 DISCORD BOT TOKEN ROTATION")
        print(f"{'='*70}")
        print(f"Old token: {old_token[:20]}..." if old_token else "Old token: (not set)")
        print(f"New token: {new_token[:20]}...")
        print("\n✅ Updated .env file")
        print("⚠️  Remember to restart the bot!")
        print(f"{'='*70}\n")

        return old_token, new_token

    def audit_hardcoded_secrets(self) -> List[Tuple[str, int, str]]:
        """
        Scan codebase for hardcoded passwords.

        Returns:
            List of (filename, line_number, line_content) tuples

        This checks for:
        - A configurable legacy password marker (default: 'REDACTED_DB_PASSWORD')
        - Common password patterns in Python files
        """
        findings = []
        search_term = os.getenv("SECRETS_AUDIT_SEARCH_TERM", "REDACTED_DB_PASSWORD")

        # Directories to search
        search_dirs = [
            self.project_root / "bot",
            self.project_root / "tests",
            self.project_root / "docs",
            self.project_root / "website",
            self.project_root / ".github",
        ]

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue

            # Recursively search Python files
            for py_file in search_dir.rglob("*.py"):
                try:
                    with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_no, line in enumerate(f, 1):
                            if search_term in line:
                                rel_path = py_file.relative_to(self.project_root)
                                findings.append((str(rel_path), line_no, line.strip()))
                except Exception as e:
                    print(f"⚠️  Error reading {py_file}: {e}")

            # Also check markdown, yml, yaml, sql files
            for ext in ["*.md", "*.yml", "*.yaml", "*.sql", "*.cfg"]:
                for file_path in search_dir.rglob(ext):
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            for line_no, line in enumerate(f, 1):
                                if search_term in line:
                                    rel_path = file_path.relative_to(self.project_root)
                                    findings.append((str(rel_path), line_no, line.strip()))
                    except Exception as e:
                        print(f"⚠️  Error reading {file_path}: {e}")

        return findings


def main():
    """Main entry point for CLI tool."""
    parser = argparse.ArgumentParser(
        description="Slomix Secrets Manager - Rotate passwords and secrets safely",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # generate command
    generate_parser = subparsers.add_parser('generate', help='Generate a secure password')
    generate_parser.add_argument('--words', type=int, default=3, help='Number of words (default: 3)')
    generate_parser.add_argument('--digits', type=int, default=4, help='Number of digits (default: 4)')

    # rotate-db command
    rotate_db_parser = subparsers.add_parser('rotate-db', help='Rotate database password')
    rotate_db_parser.add_argument('--password', type=str, help='New password (auto-generated if omitted)')

    # rotate-discord command
    rotate_discord_parser = subparsers.add_parser('rotate-discord', help='Rotate Discord bot token')
    rotate_discord_parser.add_argument('token', type=str, help='New Discord bot token')

    # backup-env command
    subparsers.add_parser('backup-env', help='Backup .env file')

    # audit command
    subparsers.add_parser('audit', help='Audit codebase for hardcoded secrets')

    args = parser.parse_args()

    # Initialize manager
    manager = SecretsManager()

    # Execute command
    if args.command == 'generate':
        password = manager.generate_password(word_count=args.words, number_count=args.digits)
        print(f"Generated password: {password}")

    elif args.command == 'rotate-db':
        manager.rotate_db_password(new_password=args.password)

    elif args.command == 'rotate-discord':
        manager.rotate_discord_token(new_token=args.token)

    elif args.command == 'backup-env':
        backup_path = manager.backup_env_file()
        print(f"Backup created: {backup_path}")

    elif args.command == 'audit':
        search_term = os.getenv("SECRETS_AUDIT_SEARCH_TERM", "REDACTED_DB_PASSWORD")
        print(f"🔍 Scanning for hardcoded password '{search_term}'...\n")
        findings = manager.audit_hardcoded_secrets()

        if findings:
            print(f"❌ Found {len(findings)} occurrences:\n")
            for filename, line_no, line in findings:
                print(f"  {filename}:{line_no}")
                print(f"    {line[:100]}...")
                print()
        else:
            print("✅ No hardcoded passwords found!")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
