#!/usr/bin/env python3
"""
Check Implementation Status - Complete system validation
Tests all components and reports current state
"""

import sqlite3
import os
import sys
from pathlib import Path

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def check_database():
    """Check production database status"""
    print("\n" + "="*60)
    print("DATABASE STATUS")
    print("="*60)
    
    db_path = "etlegacy_production.db"
    if not os.path.exists(db_path):
        print("❌ Production database NOT FOUND")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        sessions = cur.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        players = cur.execute("SELECT COUNT(*) FROM player_comprehensive_stats").fetchone()[0]
        weapons = cur.execute("SELECT COUNT(*) FROM weapon_comprehensive_stats").fetchone()[0]
        processed = cur.execute("SELECT COUNT(*) FROM processed_files").fetchone()[0]
        links = cur.execute("SELECT COUNT(*) FROM player_links").fetchone()[0]
        
        print(f"✅ Database exists: {db_path}")
        print(f"   Sessions: {sessions:,}")
        print(f"   Players: {players:,}")
        print(f"   Weapons: {weapons:,}")
        print(f"   Processed Files: {processed:,}")
        print(f"   Discord Links: {links:,}")
        
        # Check for Round 2 with 0:00
        zero_time = cur.execute("""
            SELECT COUNT(*) FROM sessions 
            WHERE round_number = 2 AND next_time_limit = '0:00'
        """).fetchone()[0]
        print(f"   Round 2 with 0:00: {zero_time:,}")
        
        conn.close()
        
        if sessions == 0:
            print("\n⚠️  Database is empty - needs data import")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def check_parser():
    """Check parser functionality"""
    print("\n" + "="*60)
    print("PARSER STATUS")
    print("="*60)
    
    try:
        from bot.community_stats_parser import C0RNP0RN3StatsParser
        parser = C0RNP0RN3StatsParser()
        print("✅ Parser imported successfully")
        
        # Find test files
        local_stats = Path("local_stats")
        if not local_stats.exists():
            print("❌ local_stats directory not found")
            return False
        
        test_files = list(local_stats.glob("*.txt"))[:5]
        if not test_files:
            print("❌ No test files found in local_stats/")
            return False
        
        print(f"   Testing with {len(test_files)} files...")
        
        errors = []
        for test_file in test_files:
            try:
                result = parser.parse_stats_file(str(test_file))
                if result:
                    print(f"   ✅ {test_file.name}")
                else:
                    print(f"   ❌ {test_file.name} - returned None")
                    errors.append(test_file.name)
            except Exception as e:
                print(f"   ❌ {test_file.name} - {str(e)[:50]}")
                errors.append(test_file.name)
        
        if errors:
            print(f"\n⚠️  Parser had {len(errors)} errors")
            return False
        else:
            print(f"\n✅ Parser working correctly")
            return True
            
    except Exception as e:
        print(f"❌ Parser import error: {e}")
        return False

def check_bot():
    """Check Discord bot status"""
    print("\n" + "="*60)
    print("DISCORD BOT STATUS")
    print("="*60)
    
    try:
        from bot.ultimate_bot import UltimateETLegacyBot
        print("✅ Bot code imported successfully")
        
        bot = UltimateETLegacyBot()
        print(f"   Bot object created")
        print(f"   Commands registered: {len(bot.commands)}")
        
        if len(bot.commands) == 0:
            print("\n⚠️  No commands registered yet")
            return False
        else:
            print(f"\n✅ Bot has commands")
            for cmd in bot.commands:
                print(f"      /{cmd.name}")
            return True
            
    except Exception as e:
        print(f"❌ Bot import error: {e}")
        return False

def check_documentation():
    """Check documentation status"""
    print("\n" + "="*60)
    print("DOCUMENTATION STATUS")
    print("="*60)
    
    dev_dir = Path("dev")
    docs = {
        "PROJECT_COMPREHENSIVE_CONTEXT.md": "Main technical documentation",
        "IMPLEMENTATION_PLAN.md": "Task roadmap and progress",
        "TIME_FORMAT_ANALYSIS.md": "0:00 mystery investigation",
        "READY_TO_START.md": "Quick reference guide",
        "PRODUCTION_SETUP.md": "Deployment guide"
    }
    
    all_exist = True
    for doc, description in docs.items():
        path = dev_dir / doc
        if path.exists():
            size_kb = path.stat().st_size / 1024
            print(f"✅ {doc} ({size_kb:.1f} KB)")
            print(f"   {description}")
        else:
            print(f"❌ {doc} - NOT FOUND")
            all_exist = False
    
    log_file = dev_dir / "bulk_import.log"
    if log_file.exists():
        size_kb = log_file.stat().st_size / 1024
        print(f"✅ bulk_import.log ({size_kb:.1f} KB)")
    
    return all_exist

def check_implementation_completeness():
    """Check which tasks are complete"""
    print("\n" + "="*60)
    print("IMPLEMENTATION COMPLETENESS")
    print("="*60)
    
    tasks = {
        "Phase 1: Database Foundation": {
            "Production database created": os.path.exists("etlegacy_production.db"),
            "Bulk import tool exists": os.path.exists("dev/bulk_import_stats.py"),
            "Verification tools exist": os.path.exists("dev/verify_zero_import.py"),
        },
        "Phase 2: Discord Commands": {
            "/stats command": False,  # Not implemented
            "/leaderboard command": False,
            "/match command": False,
            "/compare command": False,
            "/link command": False,
        },
        "Phase 3: Automation": {
            "SSH monitoring": False,  # Exists but not tested
            "Auto-processing": False,
            "Auto-posting": False,
        },
        "Phase 4: Documentation": {
            "Technical docs": os.path.exists("dev/PROJECT_COMPREHENSIVE_CONTEXT.md"),
            "User guide": False,
            "Admin guide": False,
        }
    }
    
    total = 0
    completed = 0
    
    for phase, items in tasks.items():
        print(f"\n{phase}:")
        for task, status in items.items():
            total += 1
            if status:
                completed += 1
                print(f"   ✅ {task}")
            else:
                print(f"   ❌ {task}")
    
    percentage = (completed / total * 100) if total > 0 else 0
    print(f"\n{'='*60}")
    print(f"OVERALL PROGRESS: {completed}/{total} tasks ({percentage:.1f}%)")
    print(f"{'='*60}")
    
    return percentage > 50

def main():
    """Main validation"""
    print("\n" + "="*60)
    print("ET:LEGACY DISCORD BOT - IMPLEMENTATION STATUS CHECK")
    print("="*60)
    
    results = {
        "Database": check_database(),
        "Parser": check_parser(),
        "Bot": check_bot(),
        "Documentation": check_documentation(),
        "Completeness": check_implementation_completeness(),
    }
    
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    
    for component, status in results.items():
        icon = "✅" if status else "❌"
        print(f"{icon} {component}: {'READY' if status else 'NEEDS WORK'}")
    
    all_ready = all(results.values())
    
    if all_ready:
        print("\n🎉 ALL SYSTEMS READY!")
        print("\nNext Steps:")
        print("   1. Start Discord bot: python bot/ultimate_bot.py")
        print("   2. Test commands in Discord")
        print("   3. Monitor for errors")
    else:
        print("\n⚠️  SOME COMPONENTS NEED ATTENTION")
        print("\nRecommended Actions:")
        if not results["Database"]:
            print("   • Run: python dev/bulk_import_stats.py --year 2025")
        if not results["Bot"]:
            print("   • Implement Discord commands (/stats, /leaderboard, etc.)")
        if not results["Completeness"]:
            print("   • Continue with Phase 2: Discord Commands")
    
    return 0 if all_ready else 1

if __name__ == "__main__":
    sys.exit(main())
