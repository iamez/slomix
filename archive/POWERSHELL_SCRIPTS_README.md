# 🚀 PowerShell Wrapper Scripts

**Purpose:** Convenient UTF-8-safe wrappers for common operations

## 📋 Available Scripts

### 🔍 `validate.ps1`
**Purpose:** Validate database schema before import  
**Usage:**
```powershell
.\validate.ps1
```
**What it does:**
- Sets UTF-8 encoding automatically
- Runs schema validation
- Shows clear pass/fail result

---

### 📊 `import_stats.ps1`
**Purpose:** Bulk import stats files  
**Usage:**
```powershell
# Import all files
.\import_stats.ps1

# Import specific pattern
.\import_stats.ps1 -Pattern "local_stats/2025-10-*.txt"

# Show last 50 lines instead of 100
.\import_stats.ps1 -ShowLast 50
```
**What it does:**
- Sets UTF-8 encoding automatically
- Imports stats files
- Shows timing information
- Displays last N lines of output (default: 100)

**Example:**
```powershell
PS> .\import_stats.ps1

📊 ET:Legacy Stats Bulk Import
======================================================================
📁 Importing all files from local_stats/
🚀 Starting import...
======================================================================
[import output...]
======================================================================
⏱️  Duration: 02:34
✅ Import complete!
```

---

### 🔄 `rebuild_database.ps1`
**Purpose:** Complete database rebuild (all 6 steps)  
**Usage:**
```powershell
.\rebuild_database.ps1
```
**What it does:**
1. Validates current schema
2. Asks for confirmation
3. Clears database
4. Creates fresh schema
5. Validates new schema
6. Imports stats (with confirmation)
7. Verifies results (checks duplicates)

**Interactive prompts:**
- Confirms before clearing database
- Confirms before importing
- Safe to cancel at any step

---

### 🤖 `start_bot.ps1`
**Purpose:** Start Discord bot with proper encoding  
**Usage:**
```powershell
.\start_bot.ps1
```
**What it does:**
- Sets UTF-8 encoding
- Checks database exists
- Checks .env file exists
- Starts bot with error handling
- Shows clean shutdown message

---

## 🎯 Why These Scripts Exist

### The Encoding Problem

Windows PowerShell defaults to **CP1252 encoding**, which causes errors with:
- Player names with special characters (ñ, ö, ü, etc.)
- UTF-8 encoded stats files
- Unicode output from Python scripts

### The Solution

These wrapper scripts:
1. ✅ Set `PYTHONIOENCODING='utf-8'` automatically
2. ✅ Set console output encoding to UTF-8
3. ✅ Provide clean, formatted output
4. ✅ Handle errors gracefully
5. ✅ Add timing/progress information

### Alternative: VS Code Settings

We've also updated `.vscode/settings.json` to set UTF-8 by default in VS Code's integrated terminal.

**After restarting VS Code terminal**, you can use raw commands:
```powershell
# This will work now (after VS Code restart)
python tools/simple_bulk_import.py

# No need for:
$env:PYTHONIOENCODING='utf-8'; python tools/simple_bulk_import.py
```

---

## 🔧 When to Use What

### Use Wrapper Scripts When:
- ✅ You want formatted output with timing
- ✅ You want progress indicators
- ✅ You want interactive confirmations (rebuild_database.ps1)
- ✅ You want error handling
- ✅ You're running from external PowerShell (not VS Code)

### Use Direct Commands When:
- ✅ You want to see ALL output (scripts filter/format)
- ✅ You need to pass complex arguments
- ✅ You're debugging issues
- ✅ VS Code settings already set UTF-8

---

## 📝 Examples

### Quick Validation
```powershell
.\validate.ps1
```

### Import Yesterday's Stats
```powershell
$yesterday = (Get-Date).AddDays(-1).ToString('yyyy-MM-dd')
.\import_stats.ps1 -Pattern "local_stats/$yesterday-*.txt"
```

### Full Rebuild (Interactive)
```powershell
.\rebuild_database.ps1
# Follow prompts...
```

### Start Bot
```powershell
.\start_bot.ps1
```

---

## ⚙️ Advanced: Making Scripts Globally Available

To run from any directory:

```powershell
# Add to your PowerShell profile
$env:Path += ";G:\VisualStudio\Python\stats"

# Now you can run from anywhere:
cd ~
import_stats.ps1
```

---

## 🐛 Troubleshooting

### Script Won't Run
```powershell
# Check execution policy
Get-ExecutionPolicy

# If restricted, allow scripts:
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Still Getting Encoding Errors
```powershell
# Check current encoding
[Console]::OutputEncoding

# Manually set UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

### VS Code Settings Not Working
```powershell
# Restart VS Code terminal
# Or manually reload window: Ctrl+Shift+P -> "Reload Window"
```

---

## 📊 Comparison

| Method | Pros | Cons |
|--------|------|------|
| **Wrapper Scripts** | Clean output, error handling, interactive | Hides some details |
| **VS Code Settings** | Transparent, works everywhere | Need to restart terminal |
| **Manual `$env:`** | Full control, no setup | Tedious, easy to forget |

**Recommendation:** Use VS Code settings for daily work, wrapper scripts for one-off operations.

---

## 🎓 Best Practices

1. **Always validate before import**
   ```powershell
   .\validate.ps1
   ```

2. **Use rebuild script for full rebuild**
   ```powershell
   .\rebuild_database.ps1  # Includes all steps + verification
   ```

3. **Check logs when debugging**
   ```powershell
   # Use direct command to see full output
   python tools/simple_bulk_import.py 2>&1 | Tee-Object -FilePath import.log
   ```

4. **Test with small dataset first**
   ```powershell
   .\import_stats.ps1 -Pattern "local_stats/2025-10-01-*.txt"
   ```

---

**Last Updated:** October 6, 2025  
**Location:** `G:\VisualStudio\Python\stats\`
