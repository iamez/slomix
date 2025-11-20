# Contributing to Slomix

Thank you for contributing to **Slomix**! This document outlines our development workflow and standards.

---

## 🚨 CRITICAL: Branch Policy (Version 1.0+)

**NEVER COMMIT DIRECTLY TO `main` BRANCH!**

Since the 1.0 release (November 20, 2025), all changes must go through feature branches.

---

## Development Workflow

### 1. Create a Feature Branch

```bash
# Always start from main
git checkout main
git pull origin main

# Create your feature branch with a descriptive name
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

### Branch Naming Convention:
- `feature/` - New features (e.g., `feature/new-leaderboard`)
- `fix/` - Bug fixes (e.g., `fix/session-timing`)
- `docs/` - Documentation updates (e.g., `docs/update-readme`)
- `refactor/` - Code refactoring (e.g., `refactor/cog-structure`)

### 2. Make Your Changes

```bash
# Make changes to your code
# Test thoroughly!

# Check what changed
git status
git diff

# Stage specific files (NOT git add -A)
git add bot/cogs/my_new_cog.py
git add docs/MY_FEATURE.md

# Commit with clear message
git commit -m "Add new feature: description

- Detailed change 1
- Detailed change 2"
```

### 3. Push Your Branch

```bash
# Push your feature branch
git push origin feature/your-feature-name
```

### 4. Test in Your Branch

Before merging:
- ✅ Test all functionality
- ✅ Verify no breaking changes
- ✅ Update documentation if needed
- ✅ Update `docs/CHANGELOG.md`

### 5. Merge to Main

**Option A: Pull Request (Recommended)**
```bash
# Create a pull request on GitHub
# Review the changes
# Merge via GitHub UI
```

**Option B: Direct Merge (Local)**
```bash
# Switch back to main
git checkout main

# Merge your feature branch
git merge feature/your-feature-name

# Push to GitHub
git push origin main

# Delete the feature branch (optional)
git branch -d feature/your-feature-name
git push origin --delete feature/your-feature-name
```

---

## Code Standards

### File Organization

**Root Directory** (12-15 files only):
- `README.md`
- `requirements.txt`
- `.env.example`
- `.gitignore`
- `postgresql_database_manager.py`
- Deployment scripts (`.sh` files)

**Bot Code** → `/bot/`
- All Python modules
- Cogs
- Core systems
- Services

**Documentation** → `/docs/`
- All `.md` files
- System documentation
- Guides and references

### What NOT to Commit

❌ **Never commit:**
- `.env` files (contains secrets!)
- `*.log` files
- `*.db` database files or backups
- `__pycache__/` directories
- Virtual environments (`.venv/`, `venv/`)
- Test scripts in root directory
- Temporary files
- Images/screenshots (unless essential for docs)
- PowerShell scripts (unless essential)

### Pre-Commit Checklist

Before every commit:
1. ✅ You're on a feature branch (NOT main)
2. ✅ Check `git status` for unwanted files
3. ✅ Review `git diff --cached --name-only`
4. ✅ Add files individually (avoid `git add -A`)
5. ✅ Test your changes thoroughly
6. ✅ Update `docs/CHANGELOG.md` if significant
7. ✅ Write clear commit message

---

## Commit Message Guidelines

### Format:
```
Brief description (50 chars or less)

More detailed explanation if needed. Wrap at 72 characters.

- Bullet point changes
- Another change
- Reference issues: Fixes #123
```

### Examples:

**Good:**
```
Add achievement badge for medics

- Created new badge for 1000+ revives
- Updated player_badge_service.py
- Added tests for badge calculation
```

**Bad:**
```
fixed stuff
```

---

## Testing Requirements

### Before Merging to Main:

1. **Run the bot locally**
   ```bash
   python -m bot.ultimate_bot
   ```

2. **Test affected commands**
   - Use Discord to test all modified commands
   - Check for errors in logs

3. **Verify database operations**
   - Ensure no data corruption
   - Check database logs

4. **Review documentation**
   - Update relevant docs
   - Ensure accuracy

---

## Database Changes

### If Modifying Database Schema:

1. Create migration script in `/migrations/` (if needed)
2. Update `docs/SYSTEM_ARCHITECTURE.md`
3. Test with actual database
4. Document in `docs/CHANGELOG.md`
5. **Test rollback procedure**

### Database Best Practices:
- Always use transactions
- Test with production data copy
- Never modify production DB directly
- Back up before schema changes

---

## Documentation Requirements

### For New Features:
1. Update `docs/COMMANDS.md` (if adding commands)
2. Create feature doc in `/docs/`
3. Update `README.md` if user-facing
4. Update `docs/CHANGELOG.md`
5. Update `.claude/init.md` if critical

### For Bug Fixes:
1. Document the fix in commit message
2. Update `docs/CHANGELOG.md`
3. Consider adding to `docs/archive/` if major

---

## Emergency Hotfixes

For critical production bugs:

```bash
# Create hotfix branch from main
git checkout main
git checkout -b hotfix/critical-bug-description

# Fix the issue
# Test quickly but thoroughly
git add <files>
git commit -m "HOTFIX: description"

# Merge immediately
git checkout main
git merge hotfix/critical-bug-description
git push origin main

# Clean up
git branch -d hotfix/critical-bug-description
```

---

## Pull Request Template

When creating a PR, include:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] New feature
- [ ] Bug fix
- [ ] Documentation update
- [ ] Refactoring

## Changes Made
- Change 1
- Change 2

## Testing Done
- Test 1 passed
- Test 2 passed

## Documentation Updated
- [ ] README.md
- [ ] docs/CHANGELOG.md
- [ ] Other docs (specify)

## Checklist
- [ ] Code follows project standards
- [ ] No trash files committed
- [ ] All tests pass
- [ ] Documentation updated
```

---

## Questions?

- Read `docs/AI_COMPREHENSIVE_SYSTEM_GUIDE.md` for system overview
- Check `docs/SYSTEM_ARCHITECTURE.md` for architecture
- Review `.claude/init.md` for critical rules
- Check `docs/archive/` for historical context

---

## Summary

**Golden Rule:** 🚨 **NEVER commit directly to `main`!** 🚨

1. Create feature branch
2. Make changes and test
3. Commit to your branch
4. Push to GitHub
5. Merge to main only when ready
6. Keep repository clean

Following these guidelines keeps Slomix maintainable and professional! 🎉

---

**Established**: November 20, 2025 (Version 1.0)
**Last Updated**: November 20, 2025
