# ET:Legacy Update Command - Critical Bugs Found & Fixed

## Executive Summary

During end-to-end code review, **2 critical bugs** were discovered that would cause the update command to malfunction. Both have been fixed.

---

## 🐛 BUG #1: Stale Extracted Directories (Medium Severity)

### The Problem
```bash
# If a previous update failed, old directories remain:
~/legacyupdate/temp/
├── etlegacy-v2.83.1-x86_64/  ← From previous failed update
├── etlegacy-v2.83.2-x86_64/  ← Just extracted (correct)
└── etlegacy-update.tar.gz
```

When finding the extracted directory:
```bash
find . -maxdepth 1 -type d -name 'etlegacy-v*' | head -n 1
```

**Problem:** Might return the OLD directory instead of the new one!

**Impact:**
- Update copies files from wrong (old) extracted directory
- User thinks they're updating to v2.83.2 but actually reinstalling v2.83.1
- Waste of time, no actual update happens

### The Fix
**Location:** `/home/user/slomix/bot/cogs/server_control.py:819-820`

**Before:**
```bash
cd ~/legacyupdate/temp
tar -zxf etlegacy-update.tar.gz 2>&1
```

**After:**
```bash
cd ~/legacyupdate/temp
# Remove old extracted directories from previous failed attempts
rm -rf etlegacy-v* 2>/dev/null || true
tar -zxf etlegacy-update.tar.gz 2>&1
```

Now we **always** clean up old directories before extracting, ensuring `find` returns the correct one.

---

## 🚨 BUG #2: Duplicate PK3 Files (CRITICAL SEVERITY)

### The Problem
The install phase was **adding** new pk3 files without **removing** old ones!

**Before update:**
```
/home/et/etlegacy-v2.83.1-x86_64/legacy/
└── legacy_v2.83.1-34-ga127043.pk3  (old)
```

**After update:**
```
/home/et/etlegacy-v2.83.1-x86_64/legacy/
├── legacy_v2.83.1-34-ga127043.pk3  ← OLD FILE STILL HERE!
└── legacy_v2.83.2-275-g36c31ba.pk3  ← NEW FILE
```

**Impact:**
1. **Version detection confusion:** `find legacy_v*.pk3 | head -n 1` might return the old file
   - Bot thinks update failed (version unchanged)
   - Or unpredictable behavior depending on filesystem order

2. **Server confusion:** ET:Legacy might:
   - Load the wrong pk3 version
   - Be confused about which version to use
   - Have unpredictable behavior

3. **Disk space waste:** Old pk3 files accumulate over time (each is ~300MB)

4. **Rollback issues:** When rolling back, which pk3 file is "current"?

### The Fix
**Location:** `/home/user/slomix/bot/cogs/server_control.py:897-900`

**Before:**
```bash
if [ -d legacy ]; then
    mkdir -p {server_path}/legacy
    cp -f legacy/*.pk3 {server_path}/legacy/ 2>&1  # Just copies!
fi
```

**After:**
```bash
if [ -d legacy ]; then
    mkdir -p {server_path}/legacy
    # Remove old legacy pk3 files (keeps pak*.pk3 and custom maps)
    rm -f {server_path}/legacy/legacy_v*.pk3
    # Copy new pk3 files
    cp -f legacy/*.pk3 {server_path}/legacy/ 2>&1
fi
```

Now we **remove old** `legacy_v*.pk3` files before copying new ones, matching the rollback behavior!

**Important:** We only remove `legacy_v*.pk3` files, NOT `pak*.pk3` (base game files) or custom map files.

---

## ✅ What We Validated

### Correct Behavior Confirmed:

1. **✅ Version-agnostic detection** - Uses wildcards, works with any version
2. **✅ Config preservation** - Only copies .pk3, not .cfg files
3. **✅ Smart backup** - Inspects first, backs up only what's needed
4. **✅ Daemon lifecycle** - Properly stops daemon before server, restarts after
5. **✅ SSH background process** - Uses setsid to avoid hanging
6. **✅ Rollback logic** - Removes old pk3s before restoring (this is what inspired the fix!)
7. **✅ Installation path** - Hardcoded path is correct (user updates in place, doesn't create new directories)

### Edge Cases Handled:

1. **Download failure** - Aborts early, no changes made
2. **Extraction failure** - Aborts early, no changes made
3. **Backup failure** - Aborts for safety, no changes made
4. **Installation failure** - Triggers rollback
5. **Server start failure** - Triggers rollback
6. **Rollback failure** - Alerts user for manual intervention

---

## 📋 Testing Checklist

### Before Testing:
- [ ] Bot is running with latest code
- [ ] SSH credentials configured
- [ ] Admin channel set up
- [ ] Server is running normally
- [ ] **Take manual backup of entire server directory**

### Test Scenarios:

#### Scenario 1: Normal Update (Happy Path)
```
!et_update https://www.etlegacy.com/.../etlegacy-v2.83.2-x86_64.tar.gz
```

**Expected:**
1. Detects current version correctly
2. Downloads and extracts
3. Creates smart backup
4. Stops daemon and server
5. Installs new files
6. **OLD pk3 file is removed**
7. **ONLY new pk3 file exists**
8. Detects NEW version correctly
9. Daemon restarts successfully
10. Server starts within 70s
11. Uploads pk3 to Discord
12. Reports success

**Verify After:**
```bash
# Should have ONLY one pk3 file (the new one)
ls -la ~/etlegacy-v2.83.1-x86_64/legacy/legacy_v*.pk3

# Should show new version
screen -r vektor  # (Ctrl+A+D to detach)
```

#### Scenario 2: Simulated Failed Update (Old Directories)
**Setup:**
```bash
# Manually create old extracted directory
cd ~/legacyupdate/temp
wget OLD_VERSION_URL -O old.tar.gz
tar -zxf old.tar.gz
# Leave it there
```

**Run:**
```
!et_update https://www.etlegacy.com/.../etlegacy-v2.83.2-x86_64.tar.gz
```

**Expected:**
- Old directory is cleaned up before extraction
- Update proceeds with NEW version
- **Not** confused by old directory

#### Scenario 3: Manual Duplicate PK3 Test
**Setup:**
```bash
# Manually create duplicate pk3 (simulate old bug)
cd ~/etlegacy-v2.83.1-x86_64/legacy/
cp legacy_v2.83.1-34-ga127043.pk3 legacy_v2.83.0-fake.pk3
```

**Run:**
```
!et_update https://www.etlegacy.com/.../etlegacy-v2.83.2-x86_64.tar.gz
```

**Expected:**
- Both fake and real old pk3s are removed
- Only new pk3 exists after update

#### Scenario 4: Rollback Test
**Trigger rollback by killing daemon:**
```bash
# Right after update stops server, prevent daemon from starting
rm ~/etlegacy-v2.83.1-x86_64/etdaemon.sh  # Temporarily
```

**Expected:**
- Server fails to start within 70s
- Automatic rollback triggered
- Old version restored
- Old pk3 file restored
- Server starts with old version

---

## 🔍 Post-Update Verification Commands

After successful update, verify:

```bash
# 1. Check pk3 files (should be ONLY one legacy_v*.pk3)
ls -la ~/etlegacy-v2.83.1-x86_64/legacy/legacy_v*.pk3
# Expected: ONE file with new version

# 2. Check server is running
screen -ls | grep vektor
# Expected: vektor session exists

# 3. Check daemon is running
ps aux | grep etdaemon.sh
# Expected: process exists

# 4. Check server process
ps aux | grep etlded
# Expected: etlded.x86_64 process exists

# 5. Check backup was created
ls -la ~/etlegacy_backups/
# Expected: backup_TIMESTAMP directory exists

# 6. Check temp directory is clean
ls -la ~/legacyupdate/temp/
# Expected: etlegacy-update.tar.gz removed, extracted directories removed
```

---

## 🚀 Summary

**Bugs Fixed:**
1. ✅ Stale extracted directories cleaned before extraction
2. ✅ Duplicate pk3 files - old ones removed before installing new ones

**Result:** The update command should now work reliably without:
- Version confusion
- Duplicate files
- Wrong directory selection

**Status:** Ready for testing with actual snapshot URL

**Recommendation:** Test with a snapshot URL and verify all checks pass before considering production-ready.
