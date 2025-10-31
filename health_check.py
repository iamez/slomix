"""
Health Check Script for ET:Legacy Stats Bot
Quickly verifies system is working correctly
"""

import sqlite3
import os
import sys

def check_bot_file():
    """Check bot file exists and is valid"""
    bot_path = "bot/ultimate_bot.py"
    
    if not os.path.exists(bot_path):
        print("❌ Bot file missing!")
        return False
    
    size = os.path.getsize(bot_path)
    print(f"✅ Bot file exists: {size:,} bytes")
    
    # Check syntax
    try:
        with open(bot_path, encoding='utf-8') as f:
            compile(f.read(), bot_path, 'exec')
        print("✅ Bot syntax valid")
        return True
    except SyntaxError as e:
        print(f"❌ Bot syntax error: {e}")
        return False

def check_database():
    """Check database exists and has correct schema"""
    db_path = "etlegacy_production.db"
    
    if not os.path.exists(db_path):
        print("❌ Database missing!")
        return False
    
    size = os.path.getsize(db_path)
    print(f"✅ Database exists: {size / 1024 / 1024:.2f} MB")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check schema
        cursor.execute("PRAGMA table_info(player_comprehensive_stats)")
        cols = cursor.fetchall()
        col_count = len(cols)
        
        if col_count == 53:
            print(f"✅ Schema: {col_count} columns (correct!)")
        else:
            print(f"⚠️ Schema: {col_count} columns (expected 53)")
            return False
        
        # Check records
        cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
        count = cursor.fetchone()[0]
        print(f"✅ Records: {count:,} player records")
        
        # Check integrity
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        
        if result == "ok":
            print("✅ Database integrity: OK")
        else:
            print(f"⚠️ Database integrity: {result}")
            return False
        
        # Check key tables exist
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = [
            'sessions',
            'player_comprehensive_stats',
            'weapon_comprehensive_stats',
            'player_links',
            'player_aliases'
        ]
        
        missing_tables = [t for t in required_tables if t not in tables]
        
        if missing_tables:
            print(f"⚠️ Missing tables: {', '.join(missing_tables)}")
            return False
        else:
            print(f"✅ All {len(required_tables)} required tables exist")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def check_backups():
    """Check if backups exist"""
    backup_files = [
        "bot/ultimate_bot.py.backup_GOOD_20251005",
        "etlegacy_production.db.backup_GOOD_20251005"
    ]
    
    all_exist = True
    for backup in backup_files:
        if os.path.exists(backup):
            size = os.path.getsize(backup)
            print(f"✅ Backup exists: {backup} ({size / 1024:.1f} KB)")
        else:
            print(f"⚠️ Backup missing: {backup}")
            all_exist = False
    
    return all_exist

def main():
    """Run all health checks"""
    print("=" * 60)
    print("🏥 ET:Legacy Stats Bot - Health Check")
    print("=" * 60)
    print()
    
    print("📋 Checking Bot File...")
    bot_ok = check_bot_file()
    print()
    
    print("📋 Checking Database...")
    db_ok = check_database()
    print()
    
    print("📋 Checking Backups...")
    backups_ok = check_backups()
    print()
    
    print("=" * 60)
    print("🎯 System Status:")
    print("=" * 60)
    
    if bot_ok and db_ok:
        print("✅ SYSTEM HEALTHY - Ready to run!")
        print()
        print("Start bot with: python bot/ultimate_bot.py")
        return 0
    else:
        print("❌ SYSTEM NEEDS ATTENTION")
        print()
        
        if not bot_ok:
            print("🔧 Bot Issue: Restore from backup")
            print("   Copy-Item bot/ultimate_bot.py.backup_GOOD_20251005 bot/ultimate_bot.py -Force")
        
        if not db_ok:
            print("🔧 Database Issue: Restore from backup")
            print("   Copy-Item etlegacy_production.db.backup_GOOD_20251005 etlegacy_production.db -Force")
        
        if not backups_ok:
            print("🔧 Missing Backups: Create them now!")
            print("   Copy-Item bot/ultimate_bot.py bot/ultimate_bot.py.backup_GOOD_20251005")
            print("   Copy-Item etlegacy_production.db etlegacy_production.db.backup_GOOD_20251005")
        
        return 1

if __name__ == "__main__":
    sys.exit(main())
