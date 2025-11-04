# 🤖 AI Agent Prompt: Create Network Database Migration Script

## 📋 Task Overview
Create a PowerShell script that migrates the ET:Legacy Discord Bot's SQLite database from local storage to a network Samba share, enabling seamless workstation switching without database rebuilds.

## 🎯 Script Requirements

### Script Name
`Migrate-DatabaseToNetwork.ps1`

### What the Script Must Do

#### 1. Environment Detection
- Check if running on Windows (PowerShell)
- Verify Python environment exists
- Check if `.env` file exists
- Detect current database location from `.env` or default path

#### 2. User Input & Validation
Prompt user for:
- **Samba server IP/hostname** (default: `192.168.64.116`)
- **Share name** (default: `stats`)
- **Username** (if authentication required)
- **Password** (securely, using `Read-Host -AsSecureString`)
- **Drive letter for mapping** (default: `Z:`)
- **Remote directory name** (default: `etlegacy_bot`)

Validate:
- IP address format (or hostname)
- Drive letter not already in use
- Samba server is reachable (`Test-Connection`)

#### 3. Network Share Mounting
- Test if share is accessible: `Test-Path \\192.168.64.116\stats`
- Map network drive: `net use Z: \\192.168.64.116\stats /persistent:yes`
- Handle authentication if needed
- Verify mount succeeded
- Create remote directory if it doesn't exist

#### 4. Database Backup
Before copying to network:
- Create local backup: `bot/etlegacy_production.db.backup_YYYYMMDD_HHMMSS`
- Verify backup file was created
- Log backup location

#### 5. Database Migration
Copy files to network share:
- **Main database**: `bot/etlegacy_production.db` → `Z:\etlegacy_bot\etlegacy_production.db`
- **WAL file** (if exists): `bot/etlegacy_production.db-wal` → network
- **SHM file** (if exists): `bot/etlegacy_production.db-shm` → network
- **Processed files tracker**: `bot/processed_files.txt` → network (if exists)
- **Local stats cache**: Copy entire `local_stats/` directory to network (optional)

Handle:
- File locks (check if bot is running)
- Copy with progress indicator
- Verify file integrity (compare file sizes)

#### 6. Environment File Update
- Read current `.env` file
- Check if `DATABASE_PATH` exists
- Update or add `DATABASE_PATH` line with network path
- Support both mapped drive (`Z:\`) and UNC path (`\\192.168.64.116\`)
- Preserve all other `.env` settings
- Create `.env.backup` before modifying
- Write updated `.env` file

Example transformation:
```
# Before
DATABASE_PATH=bot/etlegacy_production.db

# After
DATABASE_PATH=Z:\\etlegacy_bot\\etlegacy_production.db
# Alternative UNC path: \\\\192.168.64.116\\stats\\etlegacy_bot\\etlegacy_production.db
```

#### 7. Connection Testing
- Test database connectivity using Python
- Run query: `SELECT COUNT(*) FROM rounds`
- Verify write access with: `PRAGMA journal_mode=WAL`
- Report results to user

#### 8. Rollback Capability
If anything fails:
- Restore original `.env` from `.env.backup`
- Unmount network drive if it was just created
- Restore database from backup if copy failed
- Provide clear error messages

#### 9. Logging
- Create log file: `network_migration_YYYYMMDD_HHMMSS.log`
- Log all actions with timestamps
- Log errors with stack traces
- Display summary at the end

#### 10. Final Summary
Display:
```
✅ Migration Complete!

Database Location:
  Local:   bot/etlegacy_production.db (backed up)
  Network: Z:\etlegacy_bot\etlegacy_production.db
  UNC:     \\192.168.64.116\stats\etlegacy_bot\etlegacy_production.db

Backup Created:
  bot/etlegacy_production.db.backup_20251103_210000

Test Results:
  ✅ Network share accessible
  ✅ Database readable
  ✅ Database writable
  ✅ WAL mode enabled
  ✅ 2,152 rounds found

Next Steps:
  1. Start your bot: python bot/ultimate_bot.py
  2. On other workstation: Map Z: drive, update .env
  3. Never run bot on multiple PCs simultaneously!

To Rollback:
  1. Run: .\Rollback-NetworkDatabase.ps1
  2. Or manually: Copy backup back to bot/etlegacy_production.db
```

## 🛡️ Error Handling

### Must Handle These Scenarios:
1. **Bot is running** → Detect and ask user to stop it
2. **Network share unreachable** → Clear error, suggest troubleshooting
3. **Database locked** → Wait and retry, or abort
4. **Insufficient permissions** → Ask for credentials
5. **.env file missing** → Create new one with network path
6. **Database copy fails** → Rollback, keep local database
7. **Python test fails** → Report issue but don't rollback (might be fixable)

## 📝 Additional Features

### Optional Parameters
Support command-line parameters for automation:
```powershell
.\Migrate-DatabaseToNetwork.ps1 `
  -ServerIP "192.168.64.116" `
  -ShareName "stats" `
  -DriveLetter "Z:" `
  -RemoteDir "etlegacy_bot" `
  -SkipTest `
  -Confirm:$false
```

### Dry Run Mode
```powershell
.\Migrate-DatabaseToNetwork.ps1 -WhatIf
```
Show what would be done without actually doing it.

### Verbose Mode
```powershell
.\Migrate-DatabaseToNetwork.ps1 -Verbose
```
Show detailed progress and debugging info.

## 🧪 Testing Requirements

The script should be tested with:
- ✅ Fresh install (no .env file)
- ✅ Existing .env with local path
- ✅ Existing .env with network path (re-migration)
- ✅ Bot running (should detect and warn)
- ✅ Network share unreachable (should fail gracefully)
- ✅ Insufficient permissions (should prompt for credentials)

## 📚 Code Quality Requirements

### Must Include:
- **Comments**: Explain each major section
- **Help documentation**: Get-Help compatible
- **Parameter validation**: Use `[Parameter()]` attributes
- **Error handling**: Try-Catch blocks for all risky operations
- **Progress bars**: Show progress for long operations
- **Colors**: Use Write-Host with colors for better UX
  - 🟢 Green for success
  - 🔴 Red for errors
  - 🟡 Yellow for warnings
  - 🔵 Cyan for info

### PowerShell Best Practices:
- Use approved verbs (Verb-Noun naming)
- Use `[CmdletBinding()]` for advanced function features
- Support `-WhatIf` and `-Confirm` parameters
- Return objects, not just text
- Use proper scope for variables
- Exit codes: 0 for success, 1+ for errors

## 🔄 Companion Script: Rollback

Also create `Rollback-NetworkDatabase.ps1` that:
1. Restores `.env` from `.env.backup`
2. Copies database from backup to `bot/etlegacy_production.db`
3. Optionally unmounts network drive
4. Verifies local database works

## 📦 Deliverables

Create these files:
1. **`Migrate-DatabaseToNetwork.ps1`** - Main migration script
2. **`Rollback-NetworkDatabase.ps1`** - Rollback script (optional but recommended)
3. **`Test-NetworkDatabase.ps1`** - Standalone connection test script
4. **`README_NETWORK_SETUP.md`** - Documentation for end users

## 🎨 User Experience

### Interactive Mode (Default)
```
=============================================================
  ET:Legacy Bot - Network Database Migration
=============================================================

This script will move your SQLite database to a network
share, allowing you to switch workstations seamlessly.

Current database location: bot/etlegacy_production.db
Database size: 45.2 MB
Last modified: 2025-11-03 21:15:00

Network Share Configuration
----------------------------
Enter Samba server IP or hostname [192.168.64.116]: 192.168.64.116
Enter share name [stats]: stats
Enter drive letter [Z:]: Z:
Enter remote directory [etlegacy_bot]: etlegacy_bot

Testing network connectivity...
✅ Server 192.168.64.116 is reachable
✅ Share \\192.168.64.116\stats is accessible

Checking if bot is running...
✅ Bot is not running

Creating backup...
✅ Backup created: bot/etlegacy_production.db.backup_20251103_210000

Mapping network drive Z:...
✅ Drive Z: mapped successfully

Creating remote directory Z:\etlegacy_bot...
✅ Directory created

Copying database files...
[████████████████████████████████████████] 100%
✅ etlegacy_production.db (45.2 MB)
✅ etlegacy_production.db-wal (120 KB)
✅ processed_files.txt (2 KB)

Updating .env file...
✅ .env.backup created
✅ DATABASE_PATH updated

Testing database connection...
✅ Connection successful
✅ Found 2,152 sessions
✅ WAL mode enabled
✅ Write test passed

=============================================================
  ✅ Migration Complete!
=============================================================

Your database is now on the network at:
  Z:\etlegacy_bot\etlegacy_production.db

On other workstations:
  1. Map Z: to \\192.168.64.116\stats
  2. Update .env: DATABASE_PATH=Z:\\etlegacy_bot\\etlegacy_production.db
  3. Start bot normally

⚠️  WARNING: Do not run bot on multiple PCs simultaneously!

Press any key to exit...
```

## 🚨 Critical Warnings to Include

The script MUST warn users:

1. **⚠️ NEVER run bot on multiple workstations simultaneously!**
   - SQLite doesn't handle concurrent writes well over network
   - Can cause database corruption
   - Always stop bot on PC 1 before starting on PC 2

2. **⚠️ Network performance may be slower than local disk**
   - Acceptable for home gigabit network
   - May notice slight delay on queries

3. **⚠️ Network reliability is critical**
   - If Samba server goes down, bot stops working
   - Ensure Samba server is reliable
   - Consider UPS for Samba server

4. **⚠️ Backups are essential**
   - Set up automated backups on Samba server
   - Keep local backup before migration
   - Test restore process

## 🎓 Bonus Features (Optional)

If time allows, add:
- **Auto-detect other workstations** and show setup instructions
- **Check Samba server health** (disk space, uptime)
- **Benchmark network vs local performance** (read/write speed test)
- **Create scheduled task** for automated backups
- **Generate QR code** with connection details for easy mobile setup

## ✅ Acceptance Criteria

Script is complete when:
- [ ] Runs without errors on fresh Windows 10/11 install
- [ ] Successfully migrates database to network share
- [ ] Updates .env correctly
- [ ] Tests connection and reports results
- [ ] Creates backup before migration
- [ ] Handles all error scenarios gracefully
- [ ] Provides rollback capability
- [ ] Includes comprehensive help documentation
- [ ] Works with both mapped drives and UNC paths
- [ ] User-friendly output with colors and progress bars

## 🎯 Success Definition

A non-technical user should be able to:
1. Download the script
2. Run it in PowerShell
3. Answer a few prompts
4. Have a working network database in < 5 minutes

No manual file editing, no manual network drive mapping, no confusion.

---

## 📚 Reference Information

### Current .env Format
```bash
DISCORD_BOT_TOKEN=your_token
GUILD_ID=123456789
DATABASE_PATH=bot/etlegacy_production.db
SSH_ENABLED=true
# ... more settings
```

### Target .env Format
```bash
DISCORD_BOT_TOKEN=your_token
GUILD_ID=123456789
DATABASE_PATH=Z:\\etlegacy_bot\\etlegacy_production.db
SSH_ENABLED=true
# ... more settings
```

### Python Test Command
```python
import sqlite3
conn = sqlite3.connect('Z:\\etlegacy_bot\\etlegacy_production.db')
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM rounds")
print(cursor.fetchone()[0])
conn.close()
```

### Network Drive Mapping
```powershell
# Map with credentials
net use Z: \\192.168.64.116\stats /user:username password /persistent:yes

# Test if accessible
Test-Path Z:\
```

---

**START CODING NOW**

Create the PowerShell script(s) following all requirements above. Focus on robustness, user experience, and error handling. Make it production-ready.
