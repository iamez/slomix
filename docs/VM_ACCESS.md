# VM Access & Identity

> **Created:** 2026-02-20
> **Scope:** SSH access, identity, and security for the production VM
> **Rule:** No private keys or passwords in this file or in the repo.

---

## VM Identity

| Field | Value |
|-------|-------|
| **Hostname** | (not set; referred to as "slomix-vm") |
| **IP Address** | `192.168.64.159` (LAN) |
| **OS** | Debian 13.3 (Trixie) |
| **Host** | Proxmox VM |
| **Domain** | `https://www.slomix.fyi` (via Cloudflare Tunnel) |
| **Python** | 3.13.5 |
| **PostgreSQL** | 14 |

## Users

| User | Purpose | Shell | Home |
|------|---------|-------|------|
| `slomix` | Human login / deploy operations | `/bin/bash` | `/home/slomix` |
| `slomix_bot` | Bot service runtime (non-login) | `/usr/sbin/nologin` | N/A |
| `slomix_web` | Web service runtime (non-login) | `/usr/sbin/nologin` | N/A |
| `root` | System administration | `/bin/bash` | `/root` |

**Deploy operations** use the `slomix` user, then `sudo` for service restarts.

## Systemd Services

| Service | Unit File | Working Dir | Run As | Exec |
|---------|-----------|-------------|--------|------|
| `slomix-bot` | `/etc/systemd/system/slomix-bot.service` | `/opt/slomix` | `slomix_bot` | `python3 -m bot.ultimate_bot` |
| `slomix-web` | `/etc/systemd/system/slomix-web.service` | `/opt/slomix/website` | `slomix_web` | `uvicorn backend.main:app --host 127.0.0.1 --port 7000 --workers 2` |

Both services use `EnvironmentFile=/opt/slomix/.env`.

## Directory Layout

```
/opt/slomix/                    # Project root
├── .env                        # All secrets (DB, Discord, OAuth, CORS)
├── bot/                        # Bot package
├── website/                    # Website package
│   ├── backend/                # FastAPI app
│   ├── js/                     # Frontend JS (27 files)
│   ├── migrations/             # SQL migration files
│   └── index.html              # SPA entry point
├── tools/                      # CLI utilities
├── proximity/                  # Proximity subsystem
├── greatshot/                  # Greatshot subsystem
├── docs/                       # Documentation
├── venv-bot/                   # Bot Python venv
├── venv-web/                   # Web Python venv
├── logs/                       # Application logs
│   ├── bot.log
│   ├── webhook.log
│   ├── errors.log
│   └── web.log
├── backups/                    # DB dump backups
├── requirements.txt            # Bot dependencies
└── website/requirements.txt    # Web dependencies
```

## Network

| Port | Service | Access |
|------|---------|--------|
| 22 | SSH | LAN only |
| 5432 | PostgreSQL | localhost only |
| 7000 | Uvicorn (web) | localhost only (Cloudflare Tunnel proxies HTTPS -> 7000) |

External access is exclusively through Cloudflare Tunnel -> `https://www.slomix.fyi`.

---

## SSH Access Setup

### Step 1: Generate an Ed25519 Key Pair (On Your Dev Machine)

```bash
# Generate key (use a passphrase for security)
ssh-keygen -t ed25519 -C "slomix-vm-deploy" -f ~/.ssh/slomix_vm_ed25519

# This creates:
#   ~/.ssh/slomix_vm_ed25519       (private key - NEVER share or commit)
#   ~/.ssh/slomix_vm_ed25519.pub   (public key - safe to share)
```

### Step 2: Add Public Key to VM

```bash
# Option A: Copy key using ssh-copy-id (requires password auth temporarily)
ssh-copy-id -i ~/.ssh/slomix_vm_ed25519.pub slomix@192.168.64.159

# Option B: Manual (if ssh-copy-id unavailable)
cat ~/.ssh/slomix_vm_ed25519.pub
# Then SSH to VM with password and append to ~/.ssh/authorized_keys:
# ssh slomix@192.168.64.159
# mkdir -p ~/.ssh && chmod 700 ~/.ssh
# echo '<paste public key>' >> ~/.ssh/authorized_keys
# chmod 600 ~/.ssh/authorized_keys
```

### Step 3: Test Key-Based Login

```bash
ssh -i ~/.ssh/slomix_vm_ed25519 slomix@192.168.64.159 "echo 'Key auth works'"
```

### Step 4: Add SSH Config Entry (Convenience)

Add to `~/.ssh/config`:
```
Host slomix-vm
    HostName 192.168.64.159
    User slomix
    IdentityFile ~/.ssh/slomix_vm_ed25519
    IdentitiesOnly yes
```

Now you can just: `ssh slomix-vm`

### Step 5: Harden SSH on VM (After Key Auth Confirmed Working)

**Proposal only - do NOT run until key auth is verified:**

```bash
# On the VM, edit SSH hardening config:
sudo tee /etc/ssh/sshd_config.d/90-hardening.conf << 'EOF'
PasswordAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
MaxAuthTries 3
X11Forwarding no
AllowUsers slomix
EOF

sudo systemctl reload sshd
```

**WARNING:** Only disable password auth AFTER confirming key auth works. Otherwise you lock yourself out.

### Step 6: Add VM to Known Hosts

```bash
# On first connect, verify the host fingerprint matches
ssh-keyscan -H 192.168.64.159 >> ~/.ssh/known_hosts
```

---

## Secrets Management

| Secret | Location | Access |
|--------|----------|--------|
| DB password | `/opt/slomix/.env` on VM | `slomix` user, `slomix_bot`, `slomix_web` via EnvironmentFile |
| Discord bot token | `/opt/slomix/.env` on VM | Same |
| Discord OAuth credentials | `/opt/slomix/.env` on VM | Same |
| Session secret | `/opt/slomix/.env` on VM | Same |
| SSH private key (game server) | `/home/slomix_bot/.ssh/etlegacy_bot` | `slomix_bot` user only |
| Deploy SSH key | `~/.ssh/slomix_vm_ed25519` on dev machine | Developer only |

### Rules

- **Never commit** `.env`, private keys, or passwords to git
- `.env.example` in repo has the template (no real values)
- Rotate secrets by editing `/opt/slomix/.env` on VM directly, then restart services
- Keep a secure backup of secrets outside the repo (password manager, encrypted note)

---

## Verified State (Feb 20, 2026)

All items below were verified via `ssh slomix-vm` on 2026-02-20.

| Item | Status | Details |
|------|--------|---------|
| SSH key auth (Samba -> VM) | **WORKING** | Key: `/home/samba/.ssh/slomix_vm_ed25519`, alias: `ssh slomix-vm` |
| Password auth | Still enabled | `PasswordAuthentication yes` in hardening config; disable after all devs have key access |
| SSH hardening | Strong | Mozilla Modern ciphers, ed25519/rsa-sha2 host keys, no root login, no X11/TCP forwarding, verbose logging |
| Git on VM | **Installed** | `git version 2.47.3` |
| Code source on VM | **Git clone from GitHub** | `/opt/slomix` is a git repo on `main` branch at `8dca0e1` (same as GitHub `origin/main`) |
| Both services | **Active** | `slomix-bot` and `slomix-web` both `active` |
| Python | 3.13.5 | Both venvs (`venv-bot`, `venv-web`) use same version |
| Disk | 55 GB free | 6% used on 61 GB root partition |
| `.env` keys | 46 keys configured | DB, Discord, OAuth, SSH, CORS, Redis, session, automation |

### SSH Hardening Details (Verified)

The file `/etc/ssh/sshd_config.d/90-hardening.conf` is comprehensive:
- **Auth:** `PermitRootLogin no`, `AllowUsers slomix`, `MaxAuthTries 4`, `PermitEmptyPasswords no`
- **Crypto:** curve25519-sha256 KEX, chacha20-poly1305/aes256-gcm ciphers, hmac-sha2-512-etm MACs
- **Session:** `X11Forwarding no`, `AllowTcpForwarding no`, `AllowAgentForwarding no`
- **Idle:** `ClientAliveInterval 300`, `ClientAliveCountMax 2` (5 min timeout)
- **Only remaining action:** Change `PasswordAuthentication yes` to `no` after all devs have key access

### Paramiko Cipher Incompatibility (Important)

The VM's SSH uses Mozilla Modern cipher suite (chacha20-poly1305, aes256-gcm only). The old `paramiko 3.4.0` on Samba couldn't negotiate ciphers with this config. **Fixed:** Upgraded to `paramiko 4.0.0` on Samba. This means `tools/vm_ssh.py` and `tools/sync_from_samba.py` now work again (if needed as fallback), but native `ssh slomix-vm` is preferred.

## Quick Access Commands

```bash
# SSH to VM (preferred method)
ssh slomix-vm

# Check service status
ssh slomix-vm "systemctl is-active slomix-bot slomix-web"

# View recent bot logs
ssh slomix-vm "journalctl -u slomix-bot -n 50 --no-pager"

# View recent web logs
ssh slomix-vm "journalctl -u slomix-web -n 50 --no-pager"

# Check deployed commit
ssh slomix-vm "cd /opt/slomix && git log --oneline -3"

# API health check (from anywhere on LAN)
curl -s https://www.slomix.fyi/api/status

# Disk space
ssh slomix-vm "df -h /"
```

---

## Legacy Access (Deprecated)

The old access method via `tools/vm_ssh.py` and `tools/sync_from_samba.py` used hardcoded passwords. These tools remain in the repo for reference but should NOT be used for production operations:

| Tool | Concern |
|------|---------|
| `tools/vm_ssh.py` | Contains `VM_PASS = "123"` and `ROOT_PASS = "123"` in source |
| `tools/sync_from_samba.py` | Contains Samba password and VM passwords in source |

**Action items:**
1. Change VM passwords after key auth is established
2. Remove hardcoded passwords from these scripts (replace with key-only auth or environment variables)
3. Consider adding these files to `.gitignore` or moving credentials to env vars

---

*See also: `docs/DEPLOYMENT_RUNBOOK.md` for deploy steps.*
*See also: `docs/DEVELOPMENT_WORKFLOW.md` for branch/PR/release process.*
