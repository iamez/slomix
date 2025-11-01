# Archived Diagnostic Scripts

## ⚠️ Important: Path Adjustments Required

These scripts were moved from the root directory to `archive/diagnostics/`. 

**17 scripts** contain imports from project modules that need path adjustment to run from this location.

## 📋 Scripts with Import Dependencies

### Scripts importing from `bot/`:
1. `check_parser_output.py` - Imports `C0RNP0RN3StatsParser`
2. `debug_differential.py` - Imports `C0RNP0RN3StatsParser`
3. `parse_erdenberg_raw.py` - Imports `C0RNP0RN3StatsParser`
4. `retro_viz.py` - Imports parser classes
5. `show_objective_stats.py` - Imports `C0RNP0RN3StatsParser`
6. `test_bot_display.py` - Imports bot modules
7. `test_bot_scoring_integration.py` - Imports bot modules
8. `test_fiveeyes.py` - Imports `SynergyAnalytics` cog
9. `test_header_formats.py` - Imports parser
10. `test_import_single.py` - Imports parser
11. `test_manual_import.py` - Imports parser
12. `test_oct2_parse.py` - Imports parser
13. `test_parser_objective_stats.py` - Imports parser
14. `test_parser_tab23.py` - Imports parser

### Scripts importing from `tools/`:
1. `test_bot_display.py` - Imports `StopwatchScoring`
2. `test_bot_scoring_integration.py` - Imports `StopwatchScoring`
3. `verify_stopwatch_deployment.py` - Imports `StopwatchScoring`

## 🔧 How to Run These Scripts

### Option 1: Add Path Adjustment (Recommended)
Add these lines at the top of the script before the imports:

```python
import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

# Now imports will work
from bot.community_stats_parser import C0RNP0RN3StatsParser
from tools.stopwatch_scoring import StopwatchScoring
```

### Option 2: Run from Project Root
```bash
# Run the script from the project root directory
cd c:\Users\seareal\Documents\stats
python -m archive.diagnostics.check_parser_output

# Or specify Python path
PYTHONPATH=c:\Users\seareal\Documents\stats python archive\diagnostics\check_parser_output.py
```

### Option 3: Copy Back to Root (Temporary)
```powershell
# If you need to run a script frequently, copy it back temporarily
Copy-Item archive\diagnostics\check_parser_output.py .
python check_parser_output.py
# Delete after use
Remove-Item check_parser_output.py
```

## 📝 Example Fix

**Before (from root directory):**
```python
from bot.community_stats_parser import C0RNP0RN3StatsParser

parser = C0RNP0RN3StatsParser()
data = parser.parse_stats_file('local_stats/test.txt')
```

**After (from archive/diagnostics/):**
```python
import sys
import os

# Adjust path to find project modules
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(script_dir, "..", "..")
sys.path.insert(0, os.path.abspath(project_root))

# Now import works
from bot.community_stats_parser import C0RNP0RN3StatsParser

parser = C0RNP0RN3StatsParser()
data = parser.parse_stats_file('local_stats/test.txt')
```

## ✅ Scripts That Work Without Changes

The majority of archived scripts (194 out of 211) work fine because they only:
- Import standard library modules (`sqlite3`, `os`, `json`, etc.)
- Directly access database files (relative paths work from anywhere)
- Don't depend on project modules

## 🎯 Recommendation

**These scripts are ARCHIVED** - they were used for one-time debugging and analysis. They are kept for historical reference, but are **not expected to be run regularly**.

If you need to run one of these scripts:
1. Consider if the functionality is still relevant
2. Copy it back to root temporarily
3. Or add the path adjustment as shown above
4. Consider if this should be converted to a proper tool (move to `tools/` instead)

## 📊 Summary

- **Total archived scripts:** 211
- **Scripts with import dependencies:** 17 (8%)
- **Scripts that work as-is:** 194 (92%)
- **Impact:** Low - these are diagnostic scripts not used in production

**Status:** ✅ Documented - No action required unless you need to run one of these scripts.
