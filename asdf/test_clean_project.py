#!/usr/bin/env python3
"""
Quick test script to verify the migrated project works correctly.
"""

import sqlite3
import os
from pathlib import Path

def test_database_connection():
    """Test database connectivity and structure"""
    print("🔍 Testing Database Connection")
    print("=" * 50)
    
    # Database path relative to project root
    db_path = Path("database/etlegacy_perfect.db")
    
    if not db_path.exists():
        print(f"❌ Database not found at: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get table list
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"✅ Database connected successfully")
        print(f"📊 Found {len(tables)} tables:")
        for table in tables:
            print(f"   - {table[0]}")
        
        # Check sessions table
        if ('sessions',) in tables:
            cursor.execute("SELECT COUNT(*) FROM sessions")
            session_count = cursor.fetchone()[0]
            print(f"🎮 Sessions in database: {session_count}")
            
            # Show latest session
            cursor.execute("""
                SELECT session_id, round1_datetime, round1_map, round2_map 
                FROM sessions 
                ORDER BY session_id DESC 
                LIMIT 1
            """)
            latest = cursor.fetchone()
            if latest:
                print(f"📅 Latest session: #{latest[0]} - {latest[1]} ({latest[2]}/{latest[3]})")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def test_bot_files():
    """Test bot file structure"""
    print("\n🤖 Testing Bot Files")
    print("=" * 50)
    
    essential_files = {
        'bot/ultimate_bot.py': 'Main production bot',
        'bot/community_stats_parser.py': 'GameStats parser', 
        'database/etlegacy_perfect.db': 'Production database',
        'requirements.txt': 'Python dependencies',
        '.env.example': 'Environment template',
        'README.md': 'Documentation'
    }
    
    all_good = True
    for file_path, description in essential_files.items():
        if Path(file_path).exists():
            file_size = Path(file_path).stat().st_size
            print(f"✅ {file_path} ({description}) - {file_size:,} bytes")
        else:
            print(f"❌ Missing: {file_path} ({description})")
            all_good = False
    
    return all_good

def test_stats_files():
    """Test stats file collection"""
    print("\n📊 Testing Stats Files")
    print("=" * 50)
    
    stats_dirs = ['local_stats', 'test_files']
    
    for stats_dir in stats_dirs:
        stats_path = Path(stats_dir)
        if stats_path.exists():
            txt_files = list(stats_path.glob('*.txt'))
            print(f"✅ {stats_dir}/: {len(txt_files)} GameStats files")
        else:
            print(f"⚠️  {stats_dir}/ not found")

def main():
    """Run all tests"""
    print("🚀 ETLegacy Discord Bot - Clean Project Test")
    print("=" * 70)
    
    # Check current directory
    cwd = Path.cwd()
    print(f"📁 Working directory: {cwd}")
    
    if cwd.name != 'stats':
        print("⚠️  Run this script from the 'stats' project directory")
        print("   cd G:\\VisualStudio\\Python\\stats")
        return
    
    # Run tests
    tests = [
        test_bot_files(),
        test_database_connection(), 
        test_stats_files()
    ]
    
    # Summary
    print("\n" + "=" * 70)
    if all(tests):
        print("🎉 All tests passed! Clean migration successful!")
        print("\n🚀 Ready for deployment:")
        print("1. Copy .env.example to .env and configure")
        print("2. Run: python bot/ultimate_bot.py")
        print("3. Bot will connect to Discord and serve 1,168+ sessions")
    else:
        print("⚠️  Some tests failed - check the output above")

if __name__ == "__main__":
    main()