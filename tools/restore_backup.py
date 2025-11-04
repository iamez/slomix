"""
Restore Database from Backup
=============================
Restores the database from a backup file.
"""

import sys
import shutil
from pathlib import Path


def restore_backup(backup_file):
    """Restore database from backup"""
    backup_path = Path(backup_file)
    
    if not backup_path.exists():
        print(f"❌ Error: Backup file not found: {backup_file}")
        return False
    
    print(f"\n📦 Restoring from backup: {backup_file}")
    print("⚠️  This will overwrite the current database!")
    
    response = input("\nType 'YES' to continue: ")
    if response != 'YES':
        print("\n❌ Aborted. No changes made.")
        return False
    
    # Create safety backup of current state
    safety_backup = 'etlegacy_production_before_restore.db'
    print(f"\n💾 Creating safety backup: {safety_backup}")
    shutil.copy2('etlegacy_production.db', safety_backup)
    
    # Restore
    print(f"\n♻️  Restoring {backup_file}...")
    shutil.copy2(backup_file, 'etlegacy_production.db')
    
    print("✅ Database restored successfully!")
    print(f"💾 Previous state saved as: {safety_backup}")
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/restore_backup.py <backup_file>")
        print("\nExample:")
        print("  python tools/restore_backup.py etlegacy_production_backup_20251006_120000.db")
        return
    
    backup_file = sys.argv[1]
    restore_backup(backup_file)


if __name__ == '__main__':
    main()
