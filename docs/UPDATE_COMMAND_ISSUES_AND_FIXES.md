# ET:Legacy Update Command - Critical Issues & Proposed Fixes

## 🚨 CRITICAL ISSUES IN CURRENT IMPLEMENTATION

### Issue #1: Config File Destruction
**Location:** `server_control.py:548`
```bash
cp -r * /home/et/etlegacy-v2.83.1-x86_64/
```
**Problem:** Blindly copies ALL files, overwriting critical configs
**Impact:** ❌ Loses `vektor.cfg`, `server.cfg`, custom map rotations

**Fix Required:**
```bash
# Copy ONLY binaries and pk3s, PRESERVE configs
cp -f etlded.x86_64 $INSTALL_PATH/
cp -f legacy/*.pk3 $INSTALL_PATH/legacy/
cp -rf libs $INSTALL_PATH/ 2>/dev/null || true
# DO NOT copy *.cfg files
```

---

### Issue #2: Version Hardcoded to v2.83.1
**Location:** `server_control.py:527, 560`
```bash
find /home/et/etlegacy-v2.83.1-x86_64/legacy/ -name "legacy_v2.83.1-*.pk3"
```
**Problem:** Won't work when updating to v2.83.2 or any other version
**Impact:** ❌ Search fails, can't find new pk3 file

**Fix Required:**
```bash
# Version-agnostic search using wildcard
find $INSTALL_PATH/legacy/ -name "legacy_v*.pk3" -type f
```

---

### Issue #3: Incomplete Backup
**Location:** `server_control.py:526-530`
```bash
# Only backs up pk3 files, nothing else
find ... -name "legacy_v2.83.1-*.pk3" -exec mv {} ~/legacyupdate/backup/
```
**Problem:** Doesn't backup binaries, libraries, or other critical files
**Impact:** ❌ Cannot rollback if update fails

**Fix Required:**
```bash
# Create timestamped comprehensive backup
BACKUP_DIR=~/etlegacy_backups/backup_$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR/{binaries,legacy,libs}
cp etlded.x86_64 $BACKUP_DIR/binaries/
cp legacy/*.pk3 $BACKUP_DIR/legacy/
cp -r libs $BACKUP_DIR/libs/ 2>/dev/null || true
```

---

### Issue #4: No Rollback Capability
**Location:** `server_control.py:620-625`
```bash
# Deletes everything immediately after "success"
rm -f etlegacy-update.tar.gz
rm -rf etlegacy-v*
```
**Problem:** If server fails to start properly after update, no way to roll back
**Impact:** ❌ Broken server with no recovery path

**Fix Required:**
- Keep backups for 7 days
- Add `!et_rollback` command
- Only delete temp files, NOT backups
- Automatic rollback on server start failure

---

### Issue #5: Unnecessary Downtime
**Location:** `server_control.py:538-542`
```bash
# Step 5: Stop server
# Step 6: Copy new files (AFTER stopping)
```
**Problem:** Stops server BEFORE downloading/extracting
**Impact:** ❌ 2+ minutes of downtime instead of ~30 seconds

**Fix Required:**
```
1. Download → Extract → Backup (server STILL RUNNING)
2. Stop server
3. Copy files (30 seconds)
4. Start server
```

---

### Issue #6: No Verification
**Location:** `server_control.py:627-628`
```python
await self._start_server_after_update(ctx, status_msg)
await self._update_progress(status_msg, "✅ Update completed successfully!", ...)
```
**Problem:** Assumes success without verifying server actually works
**Impact:** ❌ False positive if server fails to start

**Fix Required:**
```python
# Start server
# Wait 5 seconds
# Check screen session exists
# Check process is running
# Optional: RCON ping test
# If ANY fail → AUTOMATIC ROLLBACK
```

---

### Issue #7: No Transaction-like Behavior
**Problem:** Partial failures leave system in broken state
**Impact:** ❌ Could have new binaries but old pk3, or vice versa

**Fix Required:**
Implement atomic-like updates:
1. Prepare all files
2. Verify downloads complete
3. Create verified backup
4. Stop server
5. Copy all files at once
6. Verify all copies succeeded
7. Start server
8. Verify server works
9. If ANY step fails → ROLLBACK

---

## ✅ PROPOSED SOLUTION

### New Update Process Flow

```
1. PRE-UPDATE PHASE (Server Running)
   ├── Detect current version (version-agnostic)
   ├── Download snapshot tarball
   ├── Extract and verify contents
   ├── List files that will be replaced
   ├── Check disk space
   └── Display pre-update summary

2. BACKUP PHASE (Server Running)
   ├── Create timestamped backup dir: ~/etlegacy_backups/backup_YYYYMMDD_HHMMSS/
   ├── Backup binaries (etlded.x86_64, etl_bot.x86_64, etc.)
   ├── Backup ALL legacy/*.pk3 files
   ├── Backup libs/ directory
   ├── Save version info to backup_info.txt
   ├── Verify backup completed
   └── DO NOT backup configs (they stay in place)

3. UPDATE PHASE (Minimal Downtime)
   ├── STOP SERVER (downtime starts here)
   ├── Copy ONLY: binaries, pk3 files, libs
   ├── PRESERVE: all .cfg files, gamestats/, custom maps in etmain/
   ├── Set executable permissions on binaries
   ├── Verify all files copied successfully
   └── Detect new version

4. VERIFICATION PHASE
   ├── START SERVER
   ├── Wait 5 seconds for initialization
   ├── Check screen session exists
   ├── Check etlded process is running
   ├── Optional: RCON ping test
   └── If ANY check fails → AUTOMATIC ROLLBACK

5. SUCCESS PHASE
   ├── Download new pk3 to bot
   ├── Calculate MD5 hash
   ├── Upload to Discord (if <25MB)
   ├── Post summary with old→new version
   ├── Clean up temp download files (NOT backups)
   ├── Clean up backups older than 7 days
   └── Log success to audit log

6. FAILURE/ROLLBACK PHASE (If Update Fails)
   ├── Stop broken server
   ├── Restore binaries from backup
   ├── Restore pk3 files from backup
   ├── Restore libs from backup
   ├── Start server with old version
   ├── Verify rollback succeeded
   ├── Alert user: "Update failed, rolled back to vX.X.X"
   └── Keep backup for manual inspection
```

---

## 🔧 NEW COMMANDS TO ADD

### 1. `!et_update <url>` (Rewritten)
- Full backup before update
- Config preservation
- Version-agnostic
- Automatic rollback on failure
- 7-day backup retention

### 2. `!et_rollback` (NEW)
- List all available backups (last 7 days)
- Show version for each backup
- Allow manual rollback to any backup
- Verify rollback success

### 3. `!et_list_backups` (NEW - Optional)
- Show all backups with timestamps
- Show disk space used
- Allow cleanup of specific backups

---

## 📊 COMPARISON: OLD vs NEW

| Aspect | Current (BAD) | Proposed (GOOD) |
|--------|---------------|------------------|
| **Config Files** | ❌ Overwrites | ✅ Preserves |
| **Version Detection** | ❌ Hardcoded v2.83.1 | ✅ Auto-detects any version |
| **Backup** | ❌ PK3 only | ✅ Full (binaries+pk3+libs) |
| **Backup Retention** | ❌ None (deletes immediately) | ✅ 7 days |
| **Rollback** | ❌ None | ✅ Automatic + manual |
| **Downtime** | ❌ 2-5 minutes | ✅ 30-60 seconds |
| **Verification** | ❌ None | ✅ Full checks + auto-rollback |
| **Transaction Safety** | ❌ Partial failures possible | ✅ All-or-nothing |
| **Error Recovery** | ❌ Manual SSH needed | ✅ Automatic |

---

## 🚀 IMPLEMENTATION STATUS

### Completed:
- ✅ Risk analysis document
- ✅ New update logic designed
- ✅ Backup/rollback system designed
- ✅ Version detection algorithm
- ✅ Started new server_control_new.py

### TODO:
- ⏳ Complete server_control_new.py with all commands
- ⏳ Add interactive rollback selection
- ⏳ Test on dev environment
- ⏳ Replace old server_control.py
- ⏳ Update documentation
- ⏳ Commit and push changes

---

## 🎯 RECOMMENDED NEXT STEPS

1. **Review this document** - Make sure approach is correct
2. **Test current version detection** - SSH to server and test commands
3. **Complete the rewrite** - Finish server_control_new.py
4. **Test in safe environment first** - Don't run on production immediately
5. **Create backup manually** - Before deploying new code
6. **Deploy and test** - Use a test snapshot URL first

---

## 📝 EXAMPLE: SAFE UPDATE FLOW

```bash
# User runs update
!et_update https://etlegacy.com/.../etlegacy-v2.83.2-275-g36c31ba-x86_64.tar.gz

# Bot responds:
🔍 Detecting current version...
📋 Current version: v2.83.1-258-g29a4f12
📦 Current pk3: legacy_v2.83.1-258-g29a4f12.pk3

📥 Downloading ET:Legacy snapshot...
📦 Extracting archive...

💾 Creating comprehensive backup...
✅ Backup created successfully!
📁 Location: ~/etlegacy_backups/backup_20251120_143022/
⏰ Retention: 7 days

🛑 Stopping server... (downtime starts)
📂 Installing new binaries and assets...
  ✓ etlded.x86_64 → updated
  ✓ legacy_v2.83.2-275-g36c31ba.pk3 → installed
  ✓ libs/ → updated
  ✓ PRESERVED: vektor.cfg, server.cfg, gamestats/

🔍 Detecting new version...
🆕 New version: v2.83.2-275-g36c31ba

🚀 Starting server...
✅ Server restarted successfully! (downtime ended - 42 seconds total)

📥 Downloading legacy_v2.83.2-275-g36c31ba.pk3 for Discord...
📤 Uploading to Discord...

✅ Update completed successfully!
📦 Old Version: v2.83.1-258-g29a4f12
🆕 New Version: v2.83.2-275-g36c31ba
💾 Backup Location: ~/etlegacy_backups/backup_20251120_143022/
[File attached: legacy_v2.83.2-275-g36c31ba.pk3]
```

---

## 🔄 EXAMPLE: ROLLBACK FLOW

```bash
# If update fails:
❌ Server failed to start! Initiating automatic rollback...
🔄 Restoring from backup: ~/etlegacy_backups/backup_20251120_143022/
  ✓ Restored etlded.x86_64
  ✓ Restored legacy_v2.83.1-258-g29a4f12.pk3
  ✓ Restored libs/
🚀 Starting server with old version...
✅ Rollback successful! Server restored to v2.83.1-258-g29a4f12

# Or manual rollback:
!et_rollback

💾 Available Backups (retained for 7 days)

Backup #1 - 20251120_143022
**Version:** v2.83.1-258-g29a4f12
**PK3:** legacy_v2.83.1-258-g29a4f12.pk3
**Path:** ~/etlegacy_backups/backup_20251120_143022/

Backup #2 - 20251119_092015
**Version:** v2.83.1-251-g19c7e89
**PK3:** legacy_v2.83.1-251-g19c7e89.pk3
**Path:** ~/etlegacy_backups/backup_20251119_092015/
```

---

## ⚠️ CRITICAL WARNINGS

1. **DO NOT** deploy the current `!et_update` command to production
2. **DO NOT** run it without testing the new version first
3. **CREATE MANUAL BACKUP** before testing new code
4. **TEST** on development environment or with dry-run first
5. **DOCUMENT** current server state before any changes

---

**Status:** Awaiting approval to proceed with full rewrite
**Author:** Claude
**Date:** 2025-11-20
**Priority:** CRITICAL
