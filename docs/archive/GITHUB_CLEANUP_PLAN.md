# GitHub Repository Cleanup Plan

## Current Situation
- **690 files** tracked in git (way too many!)
- Lots of documentation, temp files, backups in repo
- Bot files: ~346 files (~300MB) - this is what we actually need

## Clean Repository Structure

### Keep Only:
```
slomix/
├── bot/                    # All bot code (346 files, 300MB)
├── postgresql_database_manager.py
├── main.py
├── requirements.txt
├── README.md              # Comprehensive new readme
├── .gitignore
├── .env.example           # Template for environment vars
└── docs/                  # Only essential docs (4-5 files)
    ├── DATA_PIPELINE_EXPLAINED.txt
    ├── AUTOMATION_SETUP_GUIDE.md
    ├── VPS_DEPLOYMENT_GUIDE.md
    └── COMPLETE_SYSTEM_RUNDOWN.md
```

**Total: ~350-360 files** (down from 690!)

### Delete Everything Else:
- All `.md` backup files (`*.md.backup`)
- All `.py` backup files (`*.py.backup`)
- Analysis/validation output files (`*.txt` logs)
- 100+ documentation files (keep only 4 essential ones)
- Test/dev/temp directories
- Database backup schemas
- All the refactoring logs, bug reports, session notes

## Cleanup Commands

### Option 1: Clean Rewrite (RECOMMENDED)
```bash
# Create new orphan branch (fresh start)
git checkout --orphan clean-main

# Remove everything from staging
git rm -rf .

# Copy only essential files
# (manual step - see below)

# Add and commit
git add .
git commit -m "Clean repository - bot v2.0"

# Force push to branch
git push origin clean-main --force

# Delete old branch and rename
git branch -D vps-network-migration
git branch -m clean-main vps-network-migration
git push origin vps-network-migration --force
```

### Option 2: Incremental Cleanup
```bash
# Remove all markdown files except essential ones
git rm *.md
git rm **/*.md
git checkout -- README.md
git checkout -- docs/DATA_PIPELINE_EXPLAINED.txt
git checkout -- docs/AUTOMATION_SETUP_GUIDE.md
git checkout -- docs/VPS_DEPLOYMENT_GUIDE.md
git checkout -- docs/COMPLETE_SYSTEM_RUNDOWN.md

# Remove backup files
git rm *.backup
git rm **/*.backup

# Remove temp files
git rm -r temp/ tmp/ archive/ asdf/ analytics/ dev/ test_suite/ tools/

# Commit
git commit -m "Clean up repository"
git push
```

## Files to Keep Checklist

### Core Bot Files ✅
- [x] `bot/` directory (all 346 files)
- [x] `main.py`
- [x] `postgresql_database_manager.py`
- [x] `requirements.txt`

### Configuration ✅
- [x] `.gitignore` (new comprehensive one)
- [x] `.env.example` (template)

### Documentation ✅
- [x] `README.md` (new comprehensive one)
- [x] `docs/DATA_PIPELINE_EXPLAINED.txt`
- [x] `docs/AUTOMATION_SETUP_GUIDE.md`
- [x] `docs/VPS_DEPLOYMENT_GUIDE.md`
- [x] `docs/COMPLETE_SYSTEM_RUNDOWN.md`

## Execution Steps

1. **Backup Current State**
   ```bash
   git branch backup-before-cleanup
   ```

2. **Create .gitignore**
   - Already created
   - Prevents accidental commits

3. **Create Clean README**
   - Already created (CLEAN_README.md)
   - Replace old README.md

4. **Create Fresh Branch**
   - Checkout orphan branch
   - Add only essential files
   - Commit and push

5. **Verify**
   - Check file count: should be ~360 files
   - Check repo size: should be ~300MB
   - Test clone on fresh system

## Size Comparison

**Before:**
- Files: 690
- Size: Unknown (lots of docs, backups, test files)

**After:**
- Files: ~360
- Size: ~300MB (mostly bot code)
- 47% reduction in file count
- Much cleaner, easier to navigate

## Benefits

✅ **Cleaner Repository**
- No confusion about what files matter
- Easy to navigate
- Professional appearance

✅ **Faster Operations**
- Faster clones
- Faster checkouts
- Less disk space

✅ **Better Maintenance**
- Clear what's code vs docs
- No old backup files
- No temp/test files

✅ **Easier Deployment**
- Simple to see what's needed
- Clear structure
- Good for new contributors
