# 🎯 VS Code Terminal & PowerShell Setup - Complete Guide

**Date:** October 6, 2025  
**Problem:** Windows PowerShell encoding issues with UTF-8 files  
**Solution:** VS Code settings + convenience wrapper scripts

---

## 🔍 The Problem You Asked About

### Why `$env:PYTHONIOENCODING='utf-8'` everywhere?

**Root cause:** Windows PowerShell defaults to **CP1252** (legacy Windows encoding), but:
- ET:Legacy stats files are **UTF-8** encoded
- Player names contain special characters (ñ, ö, ü, etc.)
- Python outputs UTF-8 by default
- **Mismatch = encoding errors** 💥

### Example of the Problem

```powershell
# Without UTF-8 setting:
python tools/simple_bulk_import.py
# ❌ UnicodeDecodeError: 'charmap' codec can't decode byte 0x8f...

# With UTF-8 setting:
$env:PYTHONIOENCODING='utf-8'; python tools/simple_bulk_import.py
# ✅ Works fine
```

---

## ✅ Solutions Implemented

### 1. VS Code Settings (Permanent Fix)

**File:** `.vscode/settings.json`

```json
{
  "terminal.integrated.env.windows": {
    "PYTHONIOENCODING": "utf-8"
  }
}
```

**What this does:**
- ✅ Sets UTF-8 encoding for ALL VS Code terminal sessions
- ✅ Applies automatically when opening new terminals
- ✅ Works for integrated terminal only (not external PowerShell)

**How to use:**
1. Reload VS Code window: `Ctrl+Shift+P` → "Reload Window"
2. Open new terminal: `` Ctrl+` ``
3. Run commands normally:
   ```powershell
   # No need for $env:PYTHONIOENCODING anymore!
   python tools/simple_bulk_import.py
   python validate_schema.py
   ```

### 2. PowerShell Wrapper Scripts (Convenience + Error Handling)

**Why create scripts when settings work?**
- ✅ Formatted output with progress indicators
- ✅ Interactive confirmations (rebuild process)
- ✅ Error handling and validation
- ✅ Work in external PowerShell (not just VS Code)
- ✅ Hide verbose output (show last N lines)

**Available scripts:**

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `validate.ps1` | Check schema | Before every import |
| `import_stats.ps1` | Bulk import | After validation passes |
| `rebuild_database.ps1` | Complete rebuild | Full database reset |
| `start_bot.ps1` | Start Discord bot | After import complete |

---

## 📊 When to Use What

### Scenario 1: Daily Development in VS Code ✅

**Best approach:** Use VS Code settings + direct commands

```powershell
# After reloading VS Code window:
python validate_schema.py
python tools/simple_bulk_import.py
python check_duplicates.py
```

**Pros:**
- Fast and simple
- See all output
- No wrapper overhead

### Scenario 2: One-off Operations 🎯

**Best approach:** Use wrapper scripts

```powershell
# Quick validation
.\validate.ps1

# Import with progress
.\import_stats.ps1

# Full rebuild with confirmations
.\rebuild_database.ps1
```

**Pros:**
- Formatted output
- Progress indicators
- Interactive confirmations
- Error handling

### Scenario 3: External PowerShell (not VS Code) 🔧

**Required:** Use wrapper scripts OR manual `$env:` setting

```powershell
# Option A: Wrapper scripts (recommended)
.\validate.ps1

# Option B: Manual setting
$env:PYTHONIOENCODING='utf-8'
python tools/simple_bulk_import.py
```

**Why:** VS Code settings don't apply to external terminals

### Scenario 4: Debugging Issues 🐛

**Best approach:** Direct commands with full output

```powershell
# See everything
python tools/simple_bulk_import.py 2>&1 | Tee-Object import.log

# Check specific files
python tools/simple_bulk_import.py local_stats/2025-10-06*.txt
```

**Pros:**
- Full error messages
- Can log output
- More control

---

## 🎓 Why I Created Scripts Instead of Just Settings

You asked a great question! Here's my reasoning:

### 1. **Progressive Enhancement**
- Settings = baseline (works 80% of time)
- Scripts = enhanced experience (handles edge cases)

### 2. **Error Handling**
Scripts validate preconditions:
```powershell
# start_bot.ps1 checks:
- Database exists? ✅
- .env file exists? ✅  
- UTF-8 encoding set? ✅
# Then starts bot
```

Direct commands don't check preconditions.

### 3. **Interactive Workflows**
`rebuild_database.ps1` asks:
- "Continue with rebuild?"
- "Proceed with import?"

Can't do that with direct commands.

### 4. **Filtered Output**
```powershell
# Script shows last 100 lines (clean)
.\import_stats.ps1

# Direct command shows everything (verbose)
python tools/simple_bulk_import.py
```

### 5. **Portability**
Scripts work:
- ✅ VS Code terminal
- ✅ External PowerShell
- ✅ Task Scheduler
- ✅ Remote sessions

Settings only work in VS Code terminal.

---

## 🔧 Best Practices

### ✅ DO:

1. **Use VS Code settings for daily work**
   ```powershell
   python validate_schema.py
   python tools/simple_bulk_import.py
   ```

2. **Use wrapper scripts for:**
   - One-off operations
   - Interactive workflows
   - External PowerShell
   - Automated tasks

3. **Check validation before import**
   ```powershell
   .\validate.ps1  # Always run first!
   ```

4. **Log output when debugging**
   ```powershell
   python tools/simple_bulk_import.py 2>&1 | Tee-Object import.log
   ```

### ❌ DON'T:

1. **Don't forget to reload VS Code after changing settings**
   - Settings don't apply to existing terminals
   - Must reload window or open new terminal

2. **Don't use wrapper scripts when debugging**
   - They filter output
   - Use direct commands to see everything

3. **Don't run import without validation**
   ```powershell
   # ❌ BAD:
   python tools/simple_bulk_import.py
   
   # ✅ GOOD:
   .\validate.ps1
   .\import_stats.ps1
   ```

---

## 🚀 Quick Start

### First Time Setup

1. **Reload VS Code window**
   - `Ctrl+Shift+P` → "Reload Window"
   - Or restart VS Code

2. **Open new terminal**
   - `` Ctrl+` ``
   - Verify UTF-8 is set:
     ```powershell
     $env:PYTHONIOENCODING  # Should show: utf-8
     ```

3. **Test it works**
   ```powershell
   python validate_schema.py  # No manual $env: needed!
   ```

### Daily Workflow

```powershell
# Validate
python validate_schema.py

# Import
python tools/simple_bulk_import.py

# Verify
python check_duplicates.py

# Start bot
python bot/ultimate_bot.py
```

### Using Wrapper Scripts

```powershell
# Quick validation
.\validate.ps1

# Import with progress
.\import_stats.ps1

# Full rebuild (interactive)
.\rebuild_database.ps1

# Start bot (with checks)
.\start_bot.ps1
```

---

## 📝 Summary

| Approach | Pros | Cons | Best For |
|----------|------|------|----------|
| **VS Code Settings** | Automatic, transparent | VS Code only | Daily work |
| **Wrapper Scripts** | Enhanced UX, portable | Extra files | One-off ops |
| **Manual `$env:`** | Full control | Tedious | Debugging |

**My recommendation:**
1. Use VS Code settings for 90% of work
2. Use wrapper scripts for special operations
3. Use manual `$env:` only when debugging

---

## 🎯 Answer to Your Original Question

> "do we setup our env like this all the time in vs code?"

**Short answer:** Not anymore! I fixed it. 🎉

**Long answer:**
- ✅ VS Code settings now set UTF-8 automatically
- ✅ Wrapper scripts handle edge cases
- ✅ You can use direct commands 90% of the time
- ✅ Manual `$env:` only needed when debugging

**Why I made scripts:**
- Error handling (check preconditions)
- Interactive workflows (confirmations)
- Enhanced UX (progress, formatting)
- Portability (works outside VS Code)

**Not because** settings don't work - they do! Scripts are just **nice to have** for special operations.

---

**Last Updated:** October 6, 2025  
**Files Modified:**
- `.vscode/settings.json` - UTF-8 by default
- `validate.ps1` - Schema validation wrapper
- `import_stats.ps1` - Import wrapper
- `rebuild_database.ps1` - Full rebuild workflow
- `start_bot.ps1` - Bot starter with checks

**Status:** ✅ Complete - encoding issues solved!
