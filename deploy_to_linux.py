#!/usr/bin/env python3
"""
Automated Linux VPS Deployment Script for ET:Legacy Discord Bot
Reads configuration from .env file and deploys everything automatically.
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from dotenv import load_dotenv

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_step(message):
    print(f"\n{Colors.OKCYAN}{Colors.BOLD}▶ {message}{Colors.ENDC}")

def print_success(message):
    print(f"{Colors.OKGREEN}✓ {message}{Colors.ENDC}")

def print_error(message):
    print(f"{Colors.FAIL}✗ {message}{Colors.ENDC}")

def print_warning(message):
    print(f"{Colors.WARNING}⚠ {message}{Colors.ENDC}")

def run_ssh_command(host, user, key_path, command, verbose=True):
    """Execute command via SSH"""
    ssh_cmd = [
        'ssh',
        '-i', key_path,
        '-o', 'StrictHostKeyChecking=no',
        '-p', '22',
        f'{user}@{host}',
        command
    ]
    
    if verbose:
        print(f"  Running: {command}")
    
    try:
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0 and verbose:
            print_warning(f"Command returned non-zero: {result.stderr}")
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        print_error(f"Command timed out: {command}")
        return False, "", "Timeout"
    except Exception as e:
        print_error(f"SSH command failed: {e}")
        return False, "", str(e)

def run_scp_upload(local_path, host, user, key_path, remote_path):
    """Upload file via SCP"""
    scp_cmd = [
        'scp',
        '-i', key_path,
        '-o', 'StrictHostKeyChecking=no',
        local_path,
        f'{user}@{host}:{remote_path}'
    ]
    
    print(f"  Uploading: {local_path} → {remote_path}")
    
    try:
        result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=120)
        return result.returncode == 0
    except Exception as e:
        print_error(f"SCP upload failed: {e}")
        return False

def main():
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}")
    print(f"  ET:Legacy Discord Bot - Automated Linux Deployment")
    print(f"{'='*70}{Colors.ENDC}\n")
    
    # Load environment variables
    print_step("Loading configuration from .env file...")
    load_dotenv()
    
    # Read configuration
    config = {
        'discord_token': os.getenv('DISCORD_BOT_TOKEN'),
        'guild_id': os.getenv('GUILD_ID'),
        'ssh_host': os.getenv('SSH_HOST'),
        'ssh_user': os.getenv('SSH_USER', 'samba'),
        'ssh_key_path': os.path.expanduser(os.getenv('SSH_KEY_PATH', '~/.ssh/id_rsa')),
        'remote_deploy_path': '/slomix',
        'pg_host': 'localhost',
        'pg_port': '5432',
        'pg_database': 'etlegacy',
        'pg_user': 'etlegacy_user',
        'pg_password': 'etlegacy_secure_2025',
        'remote_stats_path': os.getenv('REMOTE_STATS_PATH', '/home/et/.etlegacy/legacy/gamestats'),
    }
    
    # Validate configuration
    if not config['discord_token']:
        print_error("DISCORD_BOT_TOKEN not found in .env file!")
        sys.exit(1)
    
    if not config['ssh_host']:
        print_error("SSH_HOST not found in .env file!")
        sys.exit(1)
    
    print_success("Configuration loaded successfully")
    print(f"  SSH Target: {config['ssh_user']}@{config['ssh_host']}")
    print(f"  Deploy Path: {config['remote_deploy_path']}")
    print(f"  SSH Key: {config['ssh_key_path']}")
    
    # Check if SSH key exists
    if not os.path.exists(config['ssh_key_path']):
        print_error(f"SSH key not found: {config['ssh_key_path']}")
        print_warning("Please ensure your SSH key exists and is configured in .env")
        sys.exit(1)
    
    # Confirm deployment
    print(f"\n{Colors.WARNING}This will deploy the bot to: {config['ssh_user']}@{config['ssh_host']}:{config['remote_deploy_path']}{Colors.ENDC}")
    response = input(f"{Colors.BOLD}Continue? (yes/no): {Colors.ENDC}").strip().lower()
    if response != 'yes':
        print("Deployment cancelled.")
        sys.exit(0)
    
    # ==================== STEP 1: Test SSH Connection ====================
    print_step("Step 1: Testing SSH connection...")
    success, stdout, stderr = run_ssh_command(
        config['ssh_host'], 
        config['ssh_user'], 
        config['ssh_key_path'],
        'echo "SSH connection successful"'
    )
    
    if not success:
        print_error("SSH connection failed!")
        print(f"Error: {stderr}")
        sys.exit(1)
    
    print_success("SSH connection established")
    
    # ==================== STEP 2: Install System Dependencies ====================
    print_step("Step 2: Installing system dependencies...")
    
    commands = [
        "sudo apt-get update -qq",
        "sudo apt-get install -y -qq postgresql-16 postgresql-contrib python3 python3-pip python3-venv git",
        "sudo apt-get install -y -qq python3-dev libpq-dev"
    ]
    
    for cmd in commands:
        success, stdout, stderr = run_ssh_command(
            config['ssh_host'],
            config['ssh_user'],
            config['ssh_key_path'],
            cmd,
            verbose=False
        )
        if not success and 'already' not in stderr.lower():
            print_warning(f"Command may have issues: {cmd}")
    
    print_success("System dependencies installed")
    
    # ==================== STEP 3: Setup PostgreSQL ====================
    print_step("Step 3: Setting up PostgreSQL database...")
    
    # Create PostgreSQL user and database
    pg_commands = [
        f"sudo -u postgres psql -c \"CREATE USER {config['pg_user']} WITH PASSWORD '{config['pg_password']}';\" 2>/dev/null || echo 'User exists'",
        f"sudo -u postgres psql -c \"CREATE DATABASE {config['pg_database']} OWNER {config['pg_user']};\" 2>/dev/null || echo 'DB exists'",
        f"sudo -u postgres psql -c \"GRANT ALL PRIVILEGES ON DATABASE {config['pg_database']} TO {config['pg_user']};\"",
        f"sudo -u postgres psql -d {config['pg_database']} -c \"GRANT ALL ON SCHEMA public TO {config['pg_user']};\"",
    ]
    
    for cmd in pg_commands:
        run_ssh_command(
            config['ssh_host'],
            config['ssh_user'],
            config['ssh_key_path'],
            cmd,
            verbose=False
        )
    
    print_success("PostgreSQL configured")
    
    # ==================== STEP 4: Clone/Update Repository ====================
    print_step("Step 4: Setting up repository...")
    
    # Check if directory exists
    success, stdout, stderr = run_ssh_command(
        config['ssh_host'],
        config['ssh_user'],
        config['ssh_key_path'],
        f"test -d {config['remote_deploy_path']} && echo 'exists' || echo 'not exists'"
    )
    
    if 'exists' in stdout:
        print("  Repository directory exists, updating...")
        run_ssh_command(
            config['ssh_host'],
            config['ssh_user'],
            config['ssh_key_path'],
            f"cd {config['remote_deploy_path']} && git fetch origin && git checkout vps-network-migration && git pull origin vps-network-migration"
        )
    else:
        print("  Cloning repository...")
        run_ssh_command(
            config['ssh_host'],
            config['ssh_user'],
            config['ssh_key_path'],
            f"git clone -b vps-network-migration https://github.com/iamez/slomix.git {config['remote_deploy_path']}"
        )
    
    print_success("Repository ready")
    
    # ==================== STEP 5: Create bot/config.json ====================
    print_step("Step 5: Creating bot configuration...")
    
    bot_config = {
        "token": config['discord_token'],
        "database_type": "postgresql",
        "db_config": {
            "host": config['pg_host'],
            "port": int(config['pg_port']),
            "database": config['pg_database'],
            "user": config['pg_user'],
            "password": config['pg_password']
        }
    }
    
    # Create local temp config file
    temp_config_path = 'temp_bot_config.json'
    with open(temp_config_path, 'w') as f:
        json.dump(bot_config, f, indent=2)
    
    # Upload config
    success = run_scp_upload(
        temp_config_path,
        config['ssh_host'],
        config['ssh_user'],
        config['ssh_key_path'],
        f"{config['remote_deploy_path']}/bot/config.json"
    )
    
    # Clean up temp file
    os.remove(temp_config_path)
    
    if not success:
        print_error("Failed to upload bot configuration")
        sys.exit(1)
    
    print_success("Bot configuration created")
    
    # ==================== STEP 6: Install Python Dependencies ====================
    print_step("Step 6: Installing Python dependencies...")
    
    venv_commands = [
        f"cd {config['remote_deploy_path']} && python3 -m venv venv",
        f"cd {config['remote_deploy_path']} && venv/bin/pip install --upgrade pip setuptools wheel",
        f"cd {config['remote_deploy_path']} && venv/bin/pip install discord.py asyncpg matplotlib numpy python-dotenv",
    ]
    
    for cmd in venv_commands:
        success, stdout, stderr = run_ssh_command(
            config['ssh_host'],
            config['ssh_user'],
            config['ssh_key_path'],
            cmd,
            verbose=False
        )
    
    print_success("Python dependencies installed")
    
    # ==================== STEP 7: Initialize Database ====================
    print_step("Step 7: Initializing database with stats...")
    
    print("  This may take a few minutes...")
    success, stdout, stderr = run_ssh_command(
        config['ssh_host'],
        config['ssh_user'],
        config['ssh_key_path'],
        f"cd {config['remote_deploy_path']} && venv/bin/python3 postgresql_database_manager.py",
        verbose=True
    )
    
    if success:
        print_success("Database populated with stats")
    else:
        print_warning("Database population may have had issues - check manually")
    
    # ==================== STEP 8: Create Systemd Service ====================
    print_step("Step 8: Creating systemd service...")
    
    systemd_service = f"""[Unit]
Description=ET Legacy Discord Bot
After=network.target postgresql.service

[Service]
Type=simple
User={config['ssh_user']}
WorkingDirectory={config['remote_deploy_path']}
Environment="PATH={config['remote_deploy_path']}/venv/bin"
ExecStart={config['remote_deploy_path']}/venv/bin/python3 {config['remote_deploy_path']}/bot/ultimate_bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    
    # Create temp service file
    temp_service_path = 'temp_etlegacy_bot.service'
    with open(temp_service_path, 'w') as f:
        f.write(systemd_service)
    
    # Upload service file
    run_scp_upload(
        temp_service_path,
        config['ssh_host'],
        config['ssh_user'],
        config['ssh_key_path'],
        '/tmp/etlegacy-bot.service'
    )
    
    # Install service
    service_commands = [
        'sudo mv /tmp/etlegacy-bot.service /etc/systemd/system/etlegacy-bot.service',
        'sudo systemctl daemon-reload',
        'sudo systemctl enable etlegacy-bot',
    ]
    
    for cmd in service_commands:
        run_ssh_command(
            config['ssh_host'],
            config['ssh_user'],
            config['ssh_key_path'],
            cmd,
            verbose=False
        )
    
    # Clean up temp file
    os.remove(temp_service_path)
    
    print_success("Systemd service created")
    
    # ==================== STEP 9: Start the Bot ====================
    print_step("Step 9: Starting bot service...")
    
    run_ssh_command(
        config['ssh_host'],
        config['ssh_user'],
        config['ssh_key_path'],
        'sudo systemctl restart etlegacy-bot'
    )
    
    # Wait a moment and check status
    import time
    time.sleep(3)
    
    success, stdout, stderr = run_ssh_command(
        config['ssh_host'],
        config['ssh_user'],
        config['ssh_key_path'],
        'sudo systemctl status etlegacy-bot --no-pager'
    )
    
    if 'active (running)' in stdout:
        print_success("Bot is running!")
    else:
        print_warning("Bot service may not be running - check logs")
    
    # ==================== DEPLOYMENT COMPLETE ====================
    print(f"\n{Colors.OKGREEN}{Colors.BOLD}{'='*70}")
    print(f"  ✓ DEPLOYMENT COMPLETE!")
    print(f"{'='*70}{Colors.ENDC}\n")
    
    print(f"{Colors.BOLD}Next Steps:{Colors.ENDC}")
    print(f"  1. Check bot status: ssh {config['ssh_user']}@{config['ssh_host']} 'sudo systemctl status etlegacy-bot'")
    print(f"  2. View logs: ssh {config['ssh_user']}@{config['ssh_host']} 'sudo journalctl -u etlegacy-bot -f'")
    print(f"  3. Test Discord commands: !last_session, !session, !stats")
    print(f"\n{Colors.BOLD}Useful Commands:{Colors.ENDC}")
    print(f"  Restart bot: ssh {config['ssh_user']}@{config['ssh_host']} 'sudo systemctl restart etlegacy-bot'")
    print(f"  Stop bot: ssh {config['ssh_user']}@{config['ssh_host']} 'sudo systemctl stop etlegacy-bot'")
    print(f"  View full logs: ssh {config['ssh_user']}@{config['ssh_host']} 'sudo journalctl -u etlegacy-bot -n 100'")
    print()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Deployment cancelled by user{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Deployment failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
