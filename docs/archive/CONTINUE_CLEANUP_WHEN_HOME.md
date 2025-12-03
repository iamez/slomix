# 🏠 CONTINUE GIT CLEANUP - When You Get Home

## 📊 Current Status (as of Nov 3, 2025 - before going home)

### ✅ Progress So Far
**Started with:** 1,623 tracked files  
**Currently at:** 701 tracked files  
**Total removed:** 922 files (57% reduction!)  
**Target:** ~100-200 production-only files

### 🗑️ Cleanup Completed (3 waves)
1. **Wave 1**: Removed 173 debug/test scripts (check_*, debug_*, test_*, verify_*, analyze_*, etc.)
2. **Wave 2**: Removed 568 archive/test_suite/backups directories  
3. **Wave 3**: Removed 183 files (prompt_instructions/, fiveeyes/, test_files/, asdf/, tmp/)

### 📁 What's Left to Clean (701 files remaining)

**Current breakdown:**
- **bot/** - 264 files (may have old test files buried in subdirs)
- **tools/** - 118 files (likely contains debug scripts matching patterns)
- **dev/** - 115 files (likely contains debug scripts matching patterns)
- **docs/** - 35 files (production documentation - KEEP)
- **local_stats/** - 21 files (actual game stats - KEEP)
- **scripts/** - 5 files (production automation - likely KEEP)
- **server/** - 4 files (includes c0rnp0rn3.lua placeholder - KEEP)
- **analytics/** - 3 files (analytics cogs - KEEP)
- **database/** - 2 files (database utilities - KEEP)
- **tests/** - 8 files (actual test suite - review)
- Others - ~126 files (root level files, configs, etc.)

---

## 🎯 PROMPT FOR AI WHEN YOU GET HOME

**Copy/paste this to continue:**

```
I need to finish cleaning up the git repository to only track production files. We've already removed 922 files (57% reduction from 1,623 → 701).

CURRENT STATUS:
- 701 files still tracked
- Target: ~100-200 production-only files
- Need to remove debug scripts from tools/ (118 files), dev/ (115 files), and bot/ (264 files)

TASK: Continue git cleanup wave 4

1. CHECK tools/ directory:
   - List all files in tools/*.py
   - Identify which match debug patterns: check_*, debug_*, test_*, analyze_*, verify_*, validate_*, backfill_*, add_*, populate_*, fix_*, clean_*, compare_*, correct_*, demo_*, create_clean*, create_unified*, cross_reference*, comprehensive*
   - Remove debug scripts from git tracking
   - Keep production tools (stopwatch_scoring.py and other utilities)

2. CHECK dev/ directory:
   - List all files in dev/*.py
   - Identify which match debug patterns (same as above)
   - Remove debug scripts from git tracking
   - Keep production tools (bulk_import_stats.py is PRODUCTION)

3. CHECK bot/ directory:
   - Look for any check_*.py, test_*.py, debug_*.py in bot/ subdirs
   - Remove them from git tracking

4. VERIFY final count:
   - Should be ~100-200 files
   - Run: git ls-files | Measure-Object

5. TEST git archive:
   - Run: git archive --format=zip --output=slomix-review.zip HEAD
   - Check size (should be ~500KB-1MB)

6. COMMIT and PUSH:
   - Commit: "🧹 Final cleanup wave 4: Remove remaining debug scripts"
   - Push to GitHub

REFERENCE FILES TO KEEP:
- database_manager.py (THE consolidated DB tool)
- dev/bulk_import_stats.py (production importer)
- tools/stopwatch_scoring.py (production scoring)
- All files in bot/cogs/ and bot/core/
- All .md documentation files
- server/c0rnp0rn3.lua (placeholder - will upload actual file later)
```

---

## 📋 Additional Tasks After Cleanup

### 1. Upload Actual c0rnp0rn3.lua
- Current: `server/c0rnp0rn3.lua` is a placeholder
- TODO: Replace with actual Lua script from game server
- Then commit and push

### 2. Prepare for Claude Opus Code Review
- **Method**: Use git archive to create clean ZIP
- **Command**: `git archive --format=zip --output=slomix-review.zip HEAD`
- **Files**: ~40-50 production files (~9,365 lines)
- **Guide**: See `PRODUCTION_FILES_FOR_REVIEW.md` for what to review

### 3. Code Review Prompt for Claude Opus
```
I have an ET:Legacy stats Discord bot with ~9,365 lines of production code. 
Please perform a comprehensive code review focusing on:

1. Architecture & Design Patterns
2. Security Issues (SQL injection, etc.)
3. Performance & Optimization
4. Error Handling & Edge Cases
5. Code Maintainability & Technical Debt
6. Database Schema & Queries
7. Discord API Usage & Rate Limits

Files included:
- bot/ultimate_bot.py (~5,000 lines) - Main Discord bot
- bot/community_stats_parser.py (970 lines) - Stats parser
- dev/bulk_import_stats.py (873 lines) - Bulk importer
- 15 cogs in bot/cogs/
- 9 core modules in bot/core/
- 5-10 tools and utilities
- Database schema & configs

Please provide:
- Critical issues (must fix)
- Important improvements (should fix)
- Suggestions (nice to have)
- Code examples for fixes where applicable
```

---

## 🔧 Quick Reference Commands

### Check what's left
```powershell
# Total count
git ls-files | Measure-Object

# By directory
git ls-files | ForEach-Object { $_.Split('/')[0] } | Group-Object | Sort-Object Count -Descending

# List tools/
git ls-files tools/*.py

# List dev/
git ls-files dev/*.py
```

### Remove files matching pattern
```powershell
# Example: Remove all check_*.py from tools/
git rm --cached tools/check_*.py

# Remove entire directory
git rm -r --cached directory_name/
```

### Commit and push
```powershell
git add .gitignore
git commit -m "🧹 Final cleanup: Description here"
git push
```

### Test git archive
```powershell
git archive --format=zip --output=slomix-review.zip HEAD
```

---

## 📝 Repository Info
- **Repo**: iamez/slomix
- **Branch**: team-system
- **Current state**: 701 files tracked, 3 cleanup waves complete
- **All changes pushed**: Yes (as of leaving for home)

---

## ✨ Key Files Already Created/Updated
- ✅ `database_manager.py` - THE consolidated database tool (800+ lines)
- ✅ `DISASTER_RECOVERY.md` - Complete recovery guide
- ✅ `PRODUCTION_FILES_FOR_REVIEW.md` - Files list for Claude Opus
- ✅ `.gitignore` - Comprehensive exclusions for debug/test files
- ✅ `server/c0rnp0rn3.lua` - Placeholder (need actual file)
- ✅ Fixed `dev/bulk_import_stats.py` - Now has 51 fields + transactions + UNIQUE constraints

---

## 🎯 Success Criteria
When cleanup is complete, you should have:
- ✅ ~100-200 tracked files (down from 1,623)
- ✅ No debug/test scripts in git tracking
- ✅ `git archive` creates clean ~500KB-1MB package
- ✅ Only production code + docs tracked
- ✅ All changes committed and pushed

---

**Good luck when you get home! The hard work is done - just need to identify and remove the remaining debug scripts from tools/, dev/, and bot/. 🚀**
