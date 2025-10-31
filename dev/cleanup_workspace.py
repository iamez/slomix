#!/usr/bin/env python3
"""
🧹 Workspace Cleanup Script
===========================
Organizes the ET:Legacy Discord Bot workspace by moving development/test files
to a proper dev folder structure.
"""

import os
import shutil
from pathlib import Path

def create_dev_structure():
    """Create development folder structure"""
    dev_folders = [
        'dev',
        'dev/test_bots',
        'dev/diagnostics', 
        'dev/backups',
        'dev/analysis'
    ]
    
    for folder in dev_folders:
        Path(folder).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created folder: {folder}")

def move_files():
    """Move development files to appropriate dev folders"""
    
    # Files to move to dev/test_bots
    test_bot_files = [
        'working_bot_test.py',
        'cog_test.py', 
        'minimal_bot.py',
        'test_bot.py'
    ]
    
    # Files to move to dev/diagnostics
    diagnostic_files = [
        'debug_bot.py',
        'manual_test.py',
        'database_test.py',
        'inspect_db.py'
    ]
    
    # Files to move to dev/analysis
    analysis_files = [
        'TEST_REPORT.md'
    ]
    
    # Move test bot files
    for file in test_bot_files:
        if os.path.exists(file):
            dest = f'dev/test_bots/{file}'
            shutil.move(file, dest)
            print(f"📦 Moved {file} → {dest}")
    
    # Move diagnostic files
    for file in diagnostic_files:
        if os.path.exists(file):
            dest = f'dev/diagnostics/{file}'
            shutil.move(file, dest)
            print(f"🔧 Moved {file} → {dest}")
    
    # Move analysis files
    for file in analysis_files:
        if os.path.exists(file):
            dest = f'dev/analysis/{file}'
            shutil.move(file, dest)
            print(f"📊 Moved {file} → {dest}")

def backup_original_bot():
    """Backup the original bot before replacing"""
    if os.path.exists('bot/ultimate_bot.py'):
        timestamp = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f'dev/backups/ultimate_bot_original_{timestamp}.py'
        shutil.copy2('bot/ultimate_bot.py', backup_name)
        print(f"💾 Backed up original bot → {backup_name}")

def replace_main_bot():
    """Replace the main bot with the working fixed version"""
    if os.path.exists('bot/ultimate_bot_fixed.py'):
        # Backup original
        backup_original_bot()
        
        # Replace with fixed version
        shutil.copy2('bot/ultimate_bot_fixed.py', 'bot/ultimate_bot.py')
        print(f"✅ Replaced bot/ultimate_bot.py with working Cog-based version")
        
        # Move the fixed version to dev folder
        shutil.move('bot/ultimate_bot_fixed.py', 'dev/backups/ultimate_bot_fixed.py')
        print(f"📦 Moved fixed version to dev/backups/")

def create_dev_readme():
    """Create README for dev folder"""
    readme_content = '''# 🛠️ Development Folder

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
'''
    
    with open('dev/README.md', 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"📝 Created dev/README.md")

def main():
    """Run the workspace cleanup"""
    print("🧹 Starting workspace cleanup...")
    print()
    
    # Create folder structure
    create_dev_structure()
    print()
    
    # Move files
    print("📦 Moving development files...")
    move_files()
    print()
    
    # Replace main bot
    print("🔄 Replacing main bot with working version...")
    replace_main_bot()
    print()
    
    # Create dev documentation
    create_dev_readme()
    print()
    
    print("✅ Workspace cleanup complete!")
    print()
    print("📁 Clean workspace structure:")
    print("   bot/ultimate_bot.py           - Main production bot (Cog-based, working)")
    print("   dev/test_bots/               - Test implementations")
    print("   dev/diagnostics/             - Debug tools")
    print("   dev/backups/                 - Backup versions")
    print("   dev/analysis/                - Reports and documentation")
    print()
    print("🚀 You can now run: python bot/ultimate_bot.py")

if __name__ == "__main__":
    main()