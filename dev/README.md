# 🛠️ Development Folder

This folder contains development, testing, and analysis files for the ET:Legacy Discord Bot project.

## 📁 Folder Structure

- **`test_bots/`** - Test bot implementations and experiments
- **`diagnostics/`** - Diagnostic scripts and debugging tools  
- **`backups/`** - Backup versions of bot files
- **`analysis/`** - Analysis reports and documentation

## 🧹 Cleanup History

This folder was created to organize development files that were cluttering the main workspace.
The main bot files remain in the root `bot/` directory for production use.

## 📝 Files

### Test Bots
- `working_bot_test.py` - Minimal test bot for command registration testing
- `cog_test.py` - Cog pattern testing bot  
- `minimal_bot.py` - Basic bot structure test
- `test_bot.py` - General testing bot

### Diagnostics  
- `debug_bot.py` - Bot debugging and inspection tools
- `manual_test.py` - Manual command registration testing
- `database_test.py` - Database connectivity testing
- `inspect_db.py` - Database structure inspection

### Analysis
- `TEST_REPORT.md` - Comprehensive testing and analysis report

### Backups
- `ultimate_bot_original_*.py` - Backup of original bot before fixes
- `ultimate_bot_fixed.py` - Working Cog-based bot version
